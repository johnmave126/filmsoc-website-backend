from string import join

from flask import g
from flask_peewee.rest import Authentication

from frame_ext import CustomRestAPI, CustomResource, CustomAuthentication, CustomAdminAuthentication
from app import app
from auth import auth
from models import *
from forms import *
from helpers import query_user


class FileResource(CustomResource):
    pass


class UserResource(CustomResource):
    readonly = ['join_at', 'last_login', 'this_login', 'login_count', 'rfs_count']
    delete_recursive = False

    list_fields = ['id', 'full_name', 'student_id', 'itsc', 'pennalized', 'member_type']

    def validate_data(self, data):
        form = UserForm(**data)
        if not form.validate():
            return False, join(form.errors.values(), '\n')
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
