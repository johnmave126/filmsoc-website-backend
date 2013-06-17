from string import join

from flask import request, g, json, make_response, jsonify
from flask_peewee.rest import RestAPI, RestResource, RestrictOwnerResource, Authentication

from app import app
from auth import auth
from models import *
from forms import *
from helpers import query_user


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

    def __init__(self, *args, **kwargs):
        self._readonly = self.readonly or []

        super(CustomResource, self).__init__(*args, **kwargs)

    def prepare_data(self, obj, data):
        data['errno'] = 0
        data['error'] = ''
        return data

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
        self.after_save(obj)

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


class FileResource(CustomResource):
    pass


class UserResource(CustomResource):
    readonly = ['join_at', 'last_login', 'this_login', 'login_count', 'rfs_count']
    delete_recursive = False

    def validate_data(self, data):
        form = UserForm(**data)
        if not form.validate():
            return False, join(form.error.keys(), '\n')
        user_info = query_user(instance.itsc)
        if not user_info:
            return False, "Wrong ITSC, please check the spelling"
        data['full_name'] = user_info['displayName']
        return True, ""

    def before_save(self, instance, data):
        if g.modify_flag == 'delete':
            ref_id = instance.id
            Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, user_affected=instance, admin_involved=g.user, content="delete member " + instance.itsc)
        return instance

    def after_save(self, instance):
        ref_id = instance.id
        Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, user_affected=instance, admin_involved=g.user, content=("%s member %s") % (g.modify_flag, instance.itsc))

    def get_urls(self):
        return (
            ('/', self.require_method(self.api_list, ['GET', 'POST'])),
            ('/<pk>/', self.require_method(self.api_detail, ['GET', 'POST', 'PUT', 'DELETE'])),
            ('/<pk>/delete/', self.require_method(self.post_delete, ['POST', 'DELETE'])),
            ('/current_user/', self.require_method(self.api_current, ['GET'])),
        )

    def check_get(self, obj=None):
        if g.user and g.user.admin:
            return True
        if obj is None:
            return False
        return g.user == obj

    def api_current(self):
        obj = auth.get_logged_in_user()

        if obj is None:
            return self.response(self.prepare_data({'login': False}))

        return object_detail(obj)


class LogResource(CustomResource):
    def check_get(self, obj=None):
        return g.user and g.user.admin


user_auth = CustomAuthentication(auth)
admin_auth = CustomAdminAuthentication(auth)

# instantiate api object
api = CustomRestAPI(app, default_auth=admin_auth)

# register resources
api.register(File, FileResource, auth=Authentication)
api.register(User, UserResource)
api.register(Log, LogResource, auth=Authentication)
