import datetime
import functools
import flask_cas

from flask import request, g, json, jsonify, abort, url_for, redirect, session, Response
from peewee import QueryResultWrapper
from flask_peewee.auth import Auth
from flask_peewee.rest import RestAPI, RestResource, Authentication
from flask_peewee.filters import make_field_tree

from app import db
from helpers import after_this_request


__all__ = [
    'CustomAuth',
    'CustomBaseModel',
    'CustomRestAPI',
    'CustomAuthentication',
    'CustomAdminAuthentication',
    'CustomResource',
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
                    self.User.expired == False,
                    self.User.id == session.get('user_pk')
                ).get()
            except self.User.DoesNotExist:
                pass

    def login(self):
        if request.method == 'GET':
            next_url = request.args.get('next') or ""
            login_url = 'http://' + self.app.config['SERVER_NAME'] + url_for('%s.login' % self.blueprint.name)
            status, username, cookie = flask_cas.login(self.app.config['AUTH_SERVER'], login_url)
            if status == flask_cas.CAS_OK:
                try:
                    user = self.User.select().where(
                        self.User.expired == False,
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

                    # redirect to front server
                    return redirect(self.app.config['FRONT_SERVER'] + '/#!' + next_url)
                except self.User.DoesNotExist:
                    pass

            # not authorized
            abort(403)
        else:

            # method not allowed
            abort(405)

    def logout(self):
        next_url = request.args.get('next') or ""
        self.logout_user(self.get_logged_in_user())
        return redirect(self.app.config['FRONT_SERVER'] + '/#!' + next_url)

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
        cursor = cls_db.execute_sql("SELECT  `AUTO_INCREMENT` "
                                    "FROM information_schema.`TABLES` "
                                    "WHERE TABLE_SCHEMA =  '" + cls_db.database + "' "
                                    "AND TABLE_NAME =  '" + tb_name + "'")
        sq = QueryResultWrapper(None, cursor)
        return next(sq)[0]


class CustomRestAPI(RestAPI):
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

        if res and g.user:
            return self.verify_user(g.user)
        return res


class CustomResource(RestResource):
    #  readonly means only can be set on create
    readonly = None

    # serializing: dictionary of model -> field names to restrict output in list mode
    list_fields = None
    list_exclude = None

    # override all
    def __init__(self, rest_api, model, authentication, allowed_methods=None):
        self.api = rest_api
        self.model = model
        self.pk = model._meta.primary_key

        self.authentication = authentication
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE']

        # merge normal fields and exclude in list mode
        if self.fields:
            self.list_fields = list(set(self.fields) & set(self.list_fields or self.model._meta.get_field_names()))
        if self.exclude:
            self.list_exclude = list(set(self.exclude + (self.list_exclude or [])))

        self._fields = {self.model: self.fields or self.model._meta.get_field_names()}
        self._list_fields = {self.model: self.list_fields or self.model._meta.get_field_names()}
        if self.exclude:
            self._exclude = {self.model: self.exclude}
        else:
            self._exclude = {}

        if self.list_exclude:
            self._list_exclude = {self.model: self.list_exclude}
        else:
            self._list_exclude = {}

        self._filter_fields = self.filter_fields or self.model._meta.get_field_names()
        self._filter_exclude = self.filter_exclude or []

        self._resources = {}

        self._readonly = self.readonly or []

        # recurse into nested resources
        if self.include_resources:
            for field_name, resource in self.include_resources.items():
                field_obj = self.model._meta.fields[field_name]
                resource_obj = resource(self.api, field_obj.rel_model, self.authentication, self.allowed_methods)
                self._resources[field_name] = resource_obj
                self._fields.update(resource_obj._fields)
                self._exclude.update(resource_obj._exclude)
                self._list_fields.update(resource_obj._list_fields)
                self._list_exclude.update(resource_obj._list_exclude)

                self._filter_fields.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_fields])
                self._filter_exclude.extend(['%s__%s' % (field_name, ff) for ff in resource_obj._filter_exclude])

            self._include_foreign_keys = False
        else:
            self._include_foreign_keys = True

        self._field_tree = make_field_tree(self.model, self._filter_fields, self._filter_exclude, self.filter_recursive)

    def before_send(self, data):
        data['errno'] = 0
        data['error'] = ''
        return data

    def response(self, data):
        kwargs = {} if request.is_xhr else {'indent': 2}
        return Response(json.dumps(self.before_send(data), **kwargs), mimetype='application/json')

    def serialize_query(self, query):
        s = self.get_serializer()
        return [
            self.prepare_data(obj, s.serialize_object(obj, self._list_fields, self._list_exclude)) \
                for obj in query
        ]

    def check_post(self, obj=None):
        return (g.user and g.user.admin)

    def check_put(self, obj):
        return (g.user and g.user.admin)

    def check_delete(self, obj):
        return (g.user and g.user.admin)

    def response_forbidden(self):
        return jsonify(errno=403, error="Authorization Forbidden")

    def response_bad_method(self):
        return jsonify(errno=403, error='Unsupported method "%s"' % (request.method))

    def response_bad_request(self):
        return jsonify(errno=400, error='Bad request')

    def validate_data(self, data):
        return True, ""

    def before_save(self, instance, data=None):
        return instance

    def after_save(self, instance):
        pass

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

        instance = self.before_save(instance, data)
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
        valid, error = self.validate_data(data)
        if not valid:
            return jsonify(errno=1, error=error)

        for key in self._readonly:
            data.pop(key, None)

        obj, models = self.deserialize_object(data, obj)

        obj = self.before_save(obj, data)
        self.save_related_objects(obj, data)
        obj = self.save_object(obj, data)
        self.after_save(obj)

        return self.response(self.serialize_object(obj))

    def delete(self, obj):
        g.modify_flag = 'delete'

        obj = self.before_save(obj)
        res = obj.delete_instance(recursive=self.delete_recursive)
        return self.response({'deleted': res})
