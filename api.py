from string import join

from flask import g, jsonify
from flask_peewee.rest import Authentication

from frame_ext import CustomRestAPI, CustomResource, CustomAuthentication, CustomAdminAuthentication
from app import app
from auth import auth
from models import *
from forms import *
from helpers import query_user, update_mailing_list


class FileResource(CustomResource):
    pass


class UserResource(CustomResource):
    readonly = ['join_at', 'last_login', 'this_login', 'login_count', 'rfs_count']
    delete_recursive = False

    list_fields = ['id', 'full_name', 'student_id', 'itsc', 'pennalized', 'member_type']

    def validate_data(self, data):
        form = UserForm(**data)
        if not form.validate():
            return False, join([join(x, '\n') for x in form.errors.values()], '\n')
        user_info = query_user(data.get('itsc', None))
        if not user_info:
            return False, "Wrong ITSC, please check the spelling"
        data['full_name'] = user_info['displayName']
        # validate uniqueness
        if g.modify_flag == 'create':
            if User.select().where(User.itsc == data['itsc']).count() != 0:
                return False, "ITSC existed"
            if User.select().where(User.student_id == data['student_id']).count() != 0:
                return False, "Student ID existed"
            if User.select().where(User.university_id == data['university_id']).count() != 0:
                return False, "University ID existed"
        elif g.modify_flag == 'edit':
            sq = User.select().where(User.itsc == data['itsc'])
            if sq.count() != 0 and next(sq).id != data['id']:
                return False, "ITSC existed"
            sq = User.select().where(User.student_id == data['student_id'])
            if sq.count() != 0 and next(sq).id != data['id']:
                return False, "Student existed"
            sq = User.select().where(User.university_id == data['university_id'])
            if sq.count() != 0 and next(sq).id != data['id']:
                return False, "University ID existed"
        return True, ""

    def before_save(self, instance, data):
        if g.modify_flag == 'delete':
            ref_id = instance.id
            Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, user_affected=instance, admin_involved=g.user, content="delete member " + instance.itsc)
        return instance

    def after_save(self, instance=None):
        if instance:
            ref_id = instance.id
            Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, user_affected=instance, admin_involved=g.user, content=("%s member %s") % (g.modify_flag, instance.itsc))
        # update mailing-list
        # update_mailing_list([x.itsc for x in User.select(User.itsc)])
        # disable because it is danger

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
            return jsonify(errno=2, error="Not logged in")

        return self.object_detail(obj)


class LogResource(CustomResource):
    def check_get(self, obj=None):
        return g.user and g.user.admin


user_auth = CustomAuthentication(auth)
admin_auth = CustomAdminAuthentication(auth)
read_auth = Authentication()

# instantiate api object
api = CustomRestAPI(app, default_auth=admin_auth)

# register resources
api.register(File, FileResource, auth=read_auth)
api.register(User, UserResource)
api.register(Log, LogResource, auth=read_auth)
