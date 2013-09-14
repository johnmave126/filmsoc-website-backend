import datetime
import functools
import flask_cas
import re
import operator
from urlparse import urlparse

from werkzeug.datastructures import MultiDict
from peewee import *
from wtfpeewee.fields import WPDateField
from wtfpeewee.fields import WPDateTimeField
from wtfpeewee.fields import WPTimeField
from wtforms import fields as f
from wtforms import validators
from wtforms.validators import StopValidation, ValidationError
from wtforms.compat import string_types
from wtfpeewee.orm import ModelConverter, FieldInfo, handle_null_filter
from flask import request, g, json, jsonify, abort, url_for, redirect, session, Response
from peewee import QueryResultWrapper
from flask_peewee.auth import Auth
from flask_peewee.rest import RestAPI, RestResource, Authentication
from flask_peewee.filters import make_field_tree
from flask_peewee.serializer import Serializer

from app import app, db
from helpers import after_this_request
from db_ext import JSONField, SimpleListField

__all__ = [
    'CustomAuth',
    'CustomBaseModel',
    'CustomRestAPI',
    'CustomAuthentication',
    'CustomAdminAuthentication',
    'CustomResource',
    'CustomConverter',
]


#custom auth model
class CustomAuth(Auth):
    def test_user(self, test_fn):
        def decorator(fn):
            @functools.wraps(fn)
            def inner(*args, **kwargs):
                user = self.get_logged_in_user()

                if not user or not test_fn(user):
                    abort(403)
                return fn(*args, **kwargs)
            return inner
        return decorator

    def get_logged_in_user(self):
        if session.get('logged_in'):
            if getattr(g, 'user', None):
                return g.user

            try:
                return self.User.select().where(
                    self.User.member_type != 'Expired',
                    self.User.id == session.get('user_pk')
                ).get()
            except self.User.DoesNotExist:
                pass

    def login(self):
        if request.method == 'GET':
            next_url = request.args.get('next') or ""
            login_url = request.url.rpartition('ticket=')[0].rstrip('?&')
            status, username, cookie = flask_cas.login(self.app.config['AUTH_SERVER'], login_url)
            if status == flask_cas.CAS_OK:
                try:
                    user = self.User.select().where(
                        self.User.member_type != 'Expired',
                        self.User.itsc == username
                    ).get()
                    self.login_user(user)
                    user.last_login = user.this_login
                    user.this_login = datetime.datetime.now()
                    user.login_count = user.login_count + 1
                    user.save()
                    # set cookie for cas auth
                    if cookie:
                        @after_this_request
                        def store_cookie(response):
                            response.set_cookie(flask_cas.FLASK_CAS_NAME, cookie, path=url_for('index'), httponly=True)
                            return response

                    # redirect to front server
                    return redirect(self.app.config['FRONT_SERVER'] + '#' + next_url)
                except self.User.DoesNotExist:
                    pass

            # not authorized
            abort(403)
        else:

            # method not allowed
            abort(405)

    def logout(self):
        next_url = request.args.get('next') or ""
        next_url = self.app.config['FRONT_SERVER'] + '#' + next_url
        self.logout_user(self.get_logged_in_user())
        return redirect(flask_cas.logout(self.app.config['AUTH_SERVER'], next_url))

    def login_user(self, user):
        session['logged_in'] = True
        session['user_pk'] = user.get_id()
        session.permanent = True
        g.user = user


class CustomBaseModel(db.Model):
    @classmethod
    def next_primary_key(cls):
        tb_name = cls._meta.db_table
        cls_db = cls._meta.database
        cursor = cls_db.execute_sql("SELECT  `AUTO_INCREMENT` AS `next` "
                                    "FROM information_schema.`TABLES` "
                                    "WHERE TABLE_SCHEMA = %s"
                                    "AND TABLE_NAME = %s", (cls_db.database, tb_name,))
        row = cursor.fetchone()
        cursor.close()
        return row[0]


class CustomRestAPI(RestAPI):
    def auth_wrapper(self, func, provider):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            if not provider.authorize():
                return self.response_auth_failed()
            referrer = request.referrer or ''
            if not referrer.startswith(self.app.config['FRONT_SERVER']):
                return jsonify(errno=403, error="Not Authorized")
            return func(*args, **kwargs)
        return inner

    def response_auth_failed(self):
        return jsonify(errno=403, error="User not login")


class CustomAuthentication(Authentication):
    def __init__(self, auth, protected_methods=None):
        super(CustomAuthentication, self).__init__(protected_methods)
        self.auth = auth

    def authorize(self):
        if request.method not in self.protected_methods:
            return True

        user = self.auth.get_logged_in_user()

        if user is None:
            return False
        return user


class CustomAdminAuthentication(CustomAuthentication):
    def verify_user(self, user):
        return user.admin

    def authorize(self):
        res = super(CustomAdminAuthentication, self).authorize()

        if (not res) and g.user:
            return self.verify_user(g.user)
        return res


class CustomSerializer(Serializer):
    def clean_data(self, data):
        if not isinstance(data, dict):
            return data
        for key, value in data.items():
            if isinstance(value, dict):
                self.clean_data(value)
            elif isinstance(value, (list, tuple)):
                data[key] = map(self.clean_data, value)
            else:
                data[key] = self.convert_value(value)
        return data


class CustomResource(RestResource):
    # more to display
    paginate_by = 40

    #  readonly means only can be set on create
    readonly = None

    # search: dictionary of search_engine -> field
    search = {
        'default': []
    }

    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.pk = model._meta.primary_key

        self.authentication = authentication
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE']

        self._fields = {self.model: self.fields or self.model._meta.get_field_names()}
        if self.exclude:
            self._exclude = {self.model: self.exclude}
        else:
            self._exclude = {}

        self._filter_fields = self.filter_fields or self.model._meta.get_field_names()
        self._filter_exclude = self.filter_exclude or []

        self._resources = {}

        self._readonly = self.readonly or []
        self._search = self.search or {'default': []}
        self._search['default'] = self._search['default'] or []

        # recurse into nested resources
        if self.include_resources:
            for field_name, resource in self.include_resources.items():
                field_obj = self.model._meta.fields[field_name]
                resource_obj = resource(self.api, field_obj.rel_model, self.authentication, self.allowed_methods)
                self._resources[field_name] = resource_obj
                self._fields.update(resource_obj._fields)
                self._exclude.update(resource_obj._exclude)

                self._filter_fields.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_fields])
                self._filter_exclude.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_exclude])

            self._include_foreign_keys = False
        else:
            self._include_foreign_keys = True

        self._field_tree = make_field_tree(self.model, self._filter_fields, self._filter_exclude, self.filter_recursive)

    def require_method(self, func, methods):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            if request.method not in methods:
                resp = self.response_bad_method()
                resp.allow.update(methods + ['HEAD', 'OPTIONS'])
                return resp
            resp = func(*args, **kwargs)
            resp.allow.update(methods + ['HEAD', 'OPTIONS'])
            return resp
        return inner

    def apply_filter(self, query, expr, op, arg_list):
        query_expr = '%s__%s' % (expr, op)
        if op == 'in':
            return query.filter(**{query_expr: reduce(lambda x, y: x.extend(y) or x, [x.split(',') for x in arg_list])})
        elif len(arg_list) == 1:
            return query.filter(**{query_expr: arg_list[0]})
        else:
            query_clauses = [DQ(**{query_expr: val}) for val in arg_list]
            return query.filter(reduce(operator.or_, query_clauses))

    def apply_ordering(self, query):
        ordering = request.args.get('ordering') or ''
        if ordering:
            order_list = []
            for keyword in ordering.split(','):
                desc, column = keyword.startswith('-'), keyword.lstrip('-')
                if column in self.model._meta.fields:
                    field = self.model._meta.fields[column]
                    order_list.append(field.asc() if not desc else field.desc())
            query = query.order_by(*order_list)

        return query

    def get_serializer(self):
        return CustomSerializer()

    def before_send(self, data):
        data['errno'] = 0
        data['error'] = ''
        return data

    def response(self, data):
        kwargs = {'separators': (',', ':')} if request.is_xhr else {'indent': 2}
        return Response(json.dumps(self.before_send(data), **kwargs), mimetype='application/json')

    def get_urls(self):
        return (
            ('/search/', self.require_method(self.api_search, ['GET'])),
        ) + super(CustomResource, self).get_urls()

    def check_post(self, obj=None):
        return (g.user and g.user.admin)

    def check_put(self, obj):
        return (g.user and g.user.admin)

    def check_delete(self, obj):
        return (g.user and g.user.admin)

    def validate_data(self, data, obj=None):
        return True, ""

    def before_save(self, instance):
        return instance

    def after_save(self, instance=None):
        pass

    def get_request_metadata(self, paginated_query):
        var = paginated_query.page_var
        request_arguments = request.args.copy()

        current_page = paginated_query.get_page()
        total_page = paginated_query.get_pages()
        next = previous = ''

        regex = re.compile('^.*?/%s' % self.get_api_name())
        if current_page > 1:
            request_arguments[var] = current_page - 1
            previous = url_for(self.get_url_name(g.list_callback), **request_arguments)
            previous = regex.sub('', previous)
        if current_page < total_page:
            request_arguments[var] = current_page + 1
            next = url_for(self.get_url_name(g.list_callback), **request_arguments)
            next = regex.sub('', next)

        return {
            'model': self.get_api_name(),
            'page': current_page,
            'total': total_page,
            'previous': previous,
            'next': next,
        }

    def create(self):
        data = request.data or request.form.get('data') or ''

        try:
            data = json.loads(data)
        except ValueError:
            return self.response_bad_request()

        g.modify_flag = 'create'
        valid, error = self.validate_data(data)
        if not valid:
            return jsonify(errno=1, error=error)

        instance, models = self.deserialize_object(data, self.model())

        instance = self.before_save(instance)
        self.save_related_objects(instance, data)
        instance = self.save_object(instance, data)
        self.after_save(instance)

        return self.response(self.serialize_object(instance))

    def edit(self, obj):
        data = request.data or request.form.get('data') or ''
        try:
            data = json.loads(data)
        except ValueError:
            return self.response_bad_request()

        g.modify_flag = 'edit'
        valid, error = self.validate_data(data, obj)
        if not valid:
            return jsonify(errno=1, error=error)

        for key in self._readonly:
            data.pop(key, None)

        obj, models = self.deserialize_object(data, obj)

        obj = self.before_save(obj)
        self.save_related_objects(obj, data)
        obj = self.save_object(obj, data)
        self.after_save(obj)

        return self.response(self.serialize_object(obj))

    def delete(self, obj):
        g.modify_flag = 'delete'

        obj = self.before_save(obj)
        res = obj.delete_instance(recursive=self.delete_recursive)
        self.after_save()
        return self.response({'deleted': res})

    def apply_search_query(self, query, terms, fields):
        query_clauses = [reduce(operator.or_, [DQ(**{"%s__ilike" % y: z}) for y in fields]) for z in ("%%%s%%" % x for x in terms)]
        return query.filter(reduce(operator.and_, query_clauses))

    def api_list(self):
        g.list_callback = 'api_list'
        return super(CustomResource, self).api_list()

    def api_search(self):
        g.list_callback = 'api_search'

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        search_term = request.args.get('query') or ''
        engine = request.args.get('engine') or ''

        query = self.get_query()
        query = self.apply_ordering(query)

        if engine == 'default':
            kw_set = set(re.split(r'\s+', search_term, re.U))
            kw_set.discard('')
            if len(kw_set) > 0 and len(self._search.get('default', [])) > 0:
                query = self.apply_search_query(query, list(kw_set), self._search['default'])
        else:
            regex = re.compile('((?:\w+:\([^)]*\))|(?:\w+:[^()\s]+)|[^:\s]+)', re.U)
            kw_split_list = regex.findall(search_term)
            search_kw = MultiDict()
            for kw in kw_split_list:
                try:
                    sp = kw.index(':')
                    key = kw[0:sp]
                    val = kw[sp + 1:]
                    if val[0] == '(' and val[len(val) - 1] == ')':
                        # expand
                        for x in re.split(r'\s+', val[1:len(val)-1], re.U):
                            x and search_kw.add(key, x)
                    else:
                        search_kw.add(key, val)

                except ValueError:
                    # single word
                    search_kw.add('default', kw)

            for engine, kws in search_kw.iterlists():
                kw_set = set(kws)
                kw_set.discard('')
                if len(kw_set) > 0 and len(self._search.get(engine, [])) > 0:
                    query = self.apply_search_query(query, list(kw_set), self._search[engine])

        if self.paginate_by or 'limit' in request.args:
            return self.paginated_object_list(query)

        return self.response(self.serialize_query(query))


class CustomOptional(validators.Optional):
    def __call__(self, form, field):
        if not field.raw_data or field.raw_data[0] is None or isinstance(field.raw_data[0], string_types) and not self.string_check(field.raw_data[0]):
            field.errors[:] = []
            raise StopValidation()


class InstanceExist(object):
    """
    Check the existence of a foreignkey field.

    :param model:
        The model to check.
    :param message:
        Error message to raise in case of a validation error.
    """
    def __init__(self, model, message=None):
        self.model = model
        self.pk = model._meta.primary_key
        self.message = message

    def __call__(self, form, field):
        if not self.model.select().where(self.pk == field.data).exists():
            if self.message is None:
                self.message = field.gettext('The instance referred to not exist')

            raise ValidationError(self.message)


class CustomInteger(f.IntegerField):
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = int(valuelist[0])
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid integer value'))
            except TypeError:
                self.data = None
                raise ValueError(self.gettext('Not a valid integer'))


class CustomConverter(ModelConverter):
    defaults = {
        BlobField: f.TextAreaField,
        BooleanField: f.BooleanField,
        CharField: f.TextField,
        DateField: f.DateField,
        DateTimeField: f.DateTimeField,
        DecimalField: f.DecimalField,
        DoubleField: f.FloatField,
        FloatField: f.FloatField,
        IntegerField: CustomInteger,
        PrimaryKeyField: f.HiddenField,
        TextField: f.TextAreaField,
        TimeField: WPTimeField,
        SimpleListField: f.TextField,
        JSONField: f.TextAreaField,
    }
    coerce_defaults = {
        IntegerField: int,
        FloatField: float,
        CharField: unicode,
        TextField: unicode,
        SimpleListField: unicode,
        JSONField: unicode,
    }

    def convert(self, model, field, field_args):
        kwargs = {
            'label': field.verbose_name,
            'validators': [],
            'filters': [],
            'default': field.default,
            'description': field.help_text}
        if field_args:
            kwargs.update(field_args)

        if field.null:
            # Treat empty string as None when converting.
            kwargs['filters'].append(handle_null_filter)

        if (field.null or (field.default is not None) or (field_args is None)) and not field.choices:
            # If the field can be empty, or has a default value, do not require
            # it when submitting a form.
            kwargs['validators'].append(CustomOptional())
        else:
            if isinstance(field, self.required):
                kwargs['validators'].append(validators.InputRequired())

        field_class = type(field)
        if field_class in self.converters:
            return self.converters[field_class](model, field, **kwargs)
        elif field_class in self.defaults:
            if issubclass(self.defaults[field_class], f.FormField):
                # FormField fields (i.e. for nested forms) do not support
                # filters.
                kwargs.pop('filters')
            if field.choices or 'choices' in kwargs:
                choices = kwargs.pop('choices', field.choices)
                if field_class in self.coerce_settings or 'coerce' in kwargs:
                    coerce_fn = kwargs.pop('coerce',
                                           self.coerce_settings[field_class])
                    allow_blank = kwargs.pop('allow_blank', field.null)
                    kwargs.update({
                        'choices': choices,
                        'coerce': coerce_fn,
                        'allow_blank': allow_blank})

                    return FieldInfo(field.name, SelectChoicesField(**kwargs))

            return FieldInfo(field.name, self.defaults[field_class](**kwargs))

        raise AttributeError("There is not possible conversion "
                             "for '%s'" % field_class)
