from string import join
import uuid
from datetime import datetime, timedelta, date

from werkzeug.datastructures import MultiDict
from flask import g, jsonify, render_template, request, json
from peewee import DoesNotExist
from flask_peewee.rest import Authentication
from flask_peewee.utils import get_object_or_404

from frame_ext import CustomRestAPI, CustomResource, CustomAuthentication, CustomAdminAuthentication
from app import app
from auth import auth
from models import *
from forms import *
from helpers import query_user, update_mailing_list, upload_file, send_email


__all__ = [
    'api',
]


class FileResource(CustomResource):
    def check_post(self, obj=None):
        return obj is None

    def check_put(self, obj):
        return False

    def check_delete(self, obj):
        return False

    def create(self):
        file = request.files['file']
        name = file.filename
        if '.' in name:
            ext = '.' + name.rsplit('.', 1)[1]

        new_filename = str(uuid.uuid4()) + (ext or '')
        while File.select().where(File.url == new_filename).count() > 0:
            new_filename = str(uuid.uuid4()) + (ext or '')

        try:
            upload_file(new_filename, file)
        except Exception:
            return jsonify(errno=500, error="Upload failed")

        instance = File.create(name=name, url=new_filename)
        return self.response(self.serialize_object(instance))


class UserResource(CustomResource):
    readonly = ['join_at', 'last_login', 'this_login', 'login_count', 'rfs_count']
    delete_recursive = False

    list_fields = ['id', 'full_name', 'student_id', 'itsc', 'pennalized', 'member_type']

    search = {
        'default': ['full_name', 'student_id', 'itsc']
    }

    def validate_data(self, data):
        form = UserForm(MultiDict(data))
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
        # update_mailing_list([x.itsc for x in User.select(User.itsc).where(User.expired == False)])
        # disable because it is danger

    def get_urls(self):
        return (
            ('/current_user/', self.require_method(self.api_current, ['GET'])),
        ) + super(UserResource, self).get_urls()

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
    search = {
        'default': ['content']
    }

    def check_get(self, obj=None):
        return g.user and g.user.admin


class SimpleLogResource(CustomResource):
    fields = ['created_at']


class DiskResource(CustomResource):
    readonly = ['hold_by', 'reserved_by', 'borrow_cnt', 'rank', 'create_log']
    delete_recursive = False

    exclude = ['rank']
    list_fields = ['id', 'disk_type', 'title_en', 'title_ch', 'director_en', 'director_ch', 'actors', 'cover_url', 'avail_type']

    search = {
        'default': ['title_en', 'title_ch', 'desc_en', 'desc_ch', 'director_en', 'director_ch', 'actors'],
        'title': ['title_en', 'title_ch'],
        'actor': ['actors'],
        'tag': ['tags'],
        'director': ['director_ch', 'director_en']
    }
    include_resources = {
        'cover_url': FileResource,
        'create_log': SimpleLogResource,
    }

    def prepare_data(self, obj, data):
        if g.user and (obj.reserved_by == g.user or obj.hold_by == g.user):
            data['user_held'] = True
        else:
            data['user_held'] = False
        return super(DiskResource, self).prepare_data(obj, data)

    def validate_data(self, data):
        form = DiskForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, '\n') for x in form.errors.values()], '\n')
        return True, ""

    def get_urls(self):
        return (
            ('/<pk>/reservation/', self.require_method(self.api_reserve, ['POST', 'DELETE'])),
            ('/<pk>/borrow/', self.require_method(self.api_borrow, ['POST', 'DELETE'])),
            ('/<pk>/rate/', self.require_method(self.api_rate, ['GET', 'POST'])),
        ) + super(DiskResource, self).get_urls()

    def before_save(self, instance, data):
        if g.modify_flag == 'create':
            ref_id = Disk.next_primary_key()
            log = Log.create(model="Disk", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="create disk %s" % instance.get_callnumber())
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="Disk", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="%s disk %s" % (g.modify_flag, instance.get_callnumber()))
        return instance

    def check_post(self, obj=None):
        return g.user.admin

    def check_put(self, obj):
        return g.user.admin

    def check_delete(self, obj):
        return g.user.admin

    def api_reserve(self, pk):
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get('data') or ''

        new_log = Log(model='Disk', Type='reserve', model_refer=obj.id)

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = ReserveForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            if g.user.reserved.count() >= 2:
                return jsonify(errno=3, error="A member can reserve at most 2 disks at the same time")
            if obj.avail_type != 'Available':
                return jsonify(errno=3, error="Disk not reservable")
            obj.reserved_by = g.user
            new_log.user_affected = g.user

            if data['form'] == 'Counter':
                obj.avail_type = 'ReservedCounter'
                new_log.content = "member %s reserves disk %s (counter)" % (g.user.itsc, obj.get_callnumber())
            elif data['form'] == 'Hall':
                obj.avail_type = 'Reserved'
                new_log.content = "member %s reserves disk %s (Hall %d %s). remarks: %s" % (g.user.itsc, obj.get_callnumber(), data.get('hall', ''), data.get('room', ''), data.get('remarks', ''))
                mail_content = render_template('exco_reserve.html', disk=obj, member=g.user, data=data, time=str(datetime.now()))
                sq = Exco.select().where(Exco.hall_allocate % ("%%%d%%" % int(data.get('hall', '8'))))
                send_email(['su_film@ust.hk'] + [x.email for x in sq], [], "Delivery Request", mail_content)

        elif request.method == 'DELETE':
            if not g.user.admin:
                return self.response_forbidden()
            if obj.avail_type not in ['Reserved', 'ReservedCounter']:
                return jsonify(errno=3, error="Disk is not reserved")

            new_log.content = "clear reservation for disk %s" % obj.get_callnumber()
            new_log.admin_involved = g.user
            new_log.user_affected = obj.reserved_by

            obj.reserved_by = None
            obj.avail_type = 'Available'

        obj.save()
        new_log.save()
        return self.response(self.serialize_object(obj))

    def api_borrow(self, pk):
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get('data') or ''

        new_log = Log(model='Disk', Type='borrow', model_refer=obj.id)

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = SubmitUserForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            try:
                req_user = User.select().where(User.id == data['id']).get()
            except DoesNotExist:
                return jsonify(errno=3, error="User not found")
            if obj.avail_type == 'Borrowed':
                if obj.borrowed_by != req_user:
                    return jsonify(errno=3, error="Disk not borrowed by the user")
                if (not g.user.admin) and req_user != g.user:
                    return self.response_forbidden()
                # renew
                last_log_q = Log.select().where(Log.model == 'Disk', Log.model_refer == obj.id, Log.Type == 'borrow', Log.user_affected == req_user).limit(1)
                last_log = [x for x in last_log_q][0]
                if 'renew' in last_log.content:
                    # renewed before
                    return jsonify(errno=3, error="The disk can only be renewed once")
                # renew it
                obj.due_at = obj.due_at + timedelta(7)
                new_log.content = "member %s renews disk %s" % (req_user.itsc, obj.get_callnumber())
                new_log.user_affected = req_user
            else:
                # checkout
                if not g.user.admin:
                    return self.response_forbidden()
                if req_user.borrowed.count() >= 2:
                    return jsonify(errno=3, error="A member can borrow at most 2 disks at the same time")
                success, error = obj.check_out(req_user)
                if not success:
                    return jsonify(errno=3, error=error)
                try:
                    due_date = SiteSettings.select().where(SiteSettings.key == 'due_date').get().value
                    obj.due_at = datetime.strptime(due_date, '%Y-%m-%d').date()
                except DoesNotExist:
                    obj.due_at = date.today() + timedelta(7)

                new_log.content = "check out disk %s for member %s" % (obj.get_callnumber(), req_user.itsc)
                new_log.user_affected = req_user
                new_log.admin_involved = g.user

        elif request.method == 'DELETE':
            if not g.user.admin:
                return self.response_forbidden()

            success, error = obj.check_in()
            if not success:
                return jsonify(errno=3, error=error)

            new_log.content = "check in disk %s" % obj.get_callnumber()
            new_log.admin_involved = g.user

        obj.save()
        new_log.save()
        return self.response(self.serialize_object(obj))

    def api_rate(self, pk):
        data = request.data or request.form.get('data') or ''
        obj = get_object_or_404(self.get_query(), self.pk == pk)

        if request.method == 'GET':
            ups, downs = obj.get_rate()
            rated = g.user and Log.select().where(Log.model == 'Disk', Log.model_refer == obj.id, Log.Type == 'rate', Log.user_affected == g.user).count() > 0
        elif request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = RateForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            rate = data['rate']
            rated = Log.select().where(Log.model == 'Disk', Log.model_refer == obj.id, Log.Type == 'rate', Log.user_affected == g.user).count() > 0
            if rated:
                return jsonify(errno=3, error="You have rated this disk before")
            new_log = Log(model='Disk', model_refer=obj.id, Type='rate', user_affected=g.user)
            if rate == 'up':
                new_log.content = "member %s rate +1 for disk %s" % (g.user.itsc, obj.get_callnumber())
            elif rate == 'down':
                new_log.content = "member %s rate -1 for disk %s" % (g.user.itsc, obj.get_callnumber())

            rated = True
            new_log.save()
            ups, downs = obj.get_rate()

        return self.response({
            'ups': ups,
            'downs': downs,
            'rated': rated
        })


class RegularFilmShowResource(CustomResource):
    readonly = ['vote_cnt_1', 'vote_cnt_2', 'vote_cnt_3', 'participant_list']
    delete_recursive = False

    include_resources = {
        'film_1': DiskResource,
        'film_2': DiskResource,
        'film_3': DiskResource,
        'create_log': SimpleLogResource,
    }

    def validate_data(self, data):
        form = RegularFilmShowForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, '\n') for x in form.errors.values()], '\n')
        return True, ""

    def prepare_data(self, obj, data):
        if not (g.user and g.user.admin):
            data.discard('participant_list')
        return data

    def before_save(self, instance, data):
        if g.modify_flag == 'create':
            ref_id = RegularFilmShow.next_primary_key()
            log = Log.create(model="RegularFilmShow", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="create rfs id=%d" % ref_id)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="RegularFilmShow", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="%s rfs id=%d" % (g.modify_flag, instance.id))
        if instance.state == 'Open':
            for x in [1, 2, 3]:
                disk = getattr(instance, "film_%d" % x)
                disk.avail_type = 'Voting'
                for y in ['reserved_by', 'borrowed_by', 'due_at', 'hold_by']:
                    setattr(disk, y, None)
                disk.save()
        elif instance.state == 'Pending':
            largest = max([1, 2, 3], key=lambda o: getattr(instance, "vote_cnt_%d" % o))
            for x in [1, 2, 3]:
                disk = getattr(instance, "film_%d" % x)
                disk.avail_type = 'Available'
                disk.save()
            disk = getattr(instance, "film_%d" % largest)
            disk.avail_type = 'Onshow'
            disk.save()
        elif instance.state == 'Passed':
            disk = next((x for x in (getattr(instance, "film_%d" % y) for y in [1, 2, 3]) if x.avail_type == 'Onshow'))
            disk.save()
        return instance

    def check_post(self, obj=None):
        return g.user.admin

    def check_put(self, obj):
        return g.user.admin

    def check_delete(self, obj):
        return g.user.admin

    def get_urls(self):
        return (
            ('/<pk>/vote/', self.require_method(self.api_vote, ['POST'])),
            ('/<pk>/participant/', self.require_method(self.api_particip, ['POST'])),
        ) + super(RegularFilmShowResource, self).get_urls()

    def api_vote(self, pk):
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = VoteForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            if obj.state != 'Open':
                return jsonify(errno=3, error="The show cannot be voted now")
            vote_log = [int(x.content[len(x.content) - 1]) for x in Log.select().where(model="RegularFilmShow", model_refer=obj.id, Type="vote", user_affected=g.user)]
            if len(vote_log) >= 2:
                return jsonify(errno=3, error="A member can vote at most twice")
            if data['film_id'] in vote_log:
                return jsonify(errno=3, error="You have voted before")
            setattr(obj, "vote_cnt_%d" % data['film_id'], getattr(obj, "vote_cnt_%d" % data['film_id']) + 1)
            obj.save()
            Log.create(model="RegularFilmShow", model_refer=obj.id, Type="vote", user_affected=g.user, content="member %s vote for film No. %d" % data['film_id'])

        return self.response(self.serialize_object(obj))

    def api_particip(self, pk):
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        if not getattr(self, 'check_%s' % request.method.lower())(obj):
            return self.response_forbidden()

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = SubmitUserForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            if obj.state != 'Pending':
                return jsonify(errno=3, error="The show is not in entry mode")
            if data['id'] in obj.participant_list:
                return jsonify(errno=3, error="Recorded before")
            try:
                user = User.select().where(User.id == data['id']).get()
            except DoesNotExist:
                return jsonify(errno=3, error="User not found")
            user.rfs_count += 1
            obj.participant_list.append(data['id'])
            user.save()
            obj.save()
            Log.create(model="RegularFilmShow", model_refer=obj.id, Type="entry", user_affected=user, admin_involved=g.user, content="member %s enter RFS" % user.itsc)

        return self.response(self.serialize_object(obj))


class PreviewShowTicketResource(CustomResource):
    readonly = ['create_log']
    delete_recursive = False

    include_resources = {
        'create_log': SimpleLogResource,
    }

    def validate_data(self, data):
        form = PreviewShowTicketForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, '\n') for x in form.errors.values()], '\n')
        return True, ""

    def before_save(self, instance, data):
        if g.modify_flag == 'create':
            ref_id = PreviewShowTicket.next_primary_key()
            log = Log.create(model="PreviewShowTicket", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="create ticket id=%d" % ref_id)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="PreviewShowTicket", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="%s ticket id=%d" % (g.modify_flag, instance.id))
        return instance

    def check_post(self, obj=None):
        return g.user.admin

    def check_put(self, obj):
        return g.user.admin

    def check_delete(self, obj):
        return g.user.admin

    def get_urls(self):
        return (
            ('/<pk>/application/', self.require_method(self.api_apply, ['POST'])),
        ) + super(PreviewShowTicketResource, self).get_urls()

    def api_apply(self, pk):
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = ApplyTicketForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, '\n') for x in form.errors.values()], '\n')
                return jsonify(errno=1, error=error)
            if obj.state != 'Open':
                return jsonify(errno=3, error="The ticket cannot be applied now")
            mail_content = render_template('ticket_apply.html', ticket=obj, member=g.user, data=data, time=str(datetime.now()))
            sq = Exco.select().where(Exco.position == "External Vice-President")
            send_email(['su_film@ust.hk'] + [x.email for x in sq], [], "Ticket Application", mail_content)
            Log.create(model="PreviewShowTicket", Type='apply', model_refer=obj.id, user_affected=g.user, content="member %s apply for ticket id=%d" % (g.user.itsc, obj.id))

        return self.response({})


class DiskReviewResource(CustomResource):
    delete_recursive = False
    include_resources = {
        'create_log': SimpleLogResource,
    }

    def validate_data(self, data):
        form = DiskReviewForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, '\n') for x in form.errors.values()], '\n')
        return True, ""

    def before_save(self, instance, data):
        if g.modify_flag == 'create':
            ref_id = DiskReview.next_primary_key()
            log = Log.create(model="DiskReview", Type=g.modify_flag, model_refer=ref_id, user_affected=g.user, content="create disk review of %s" % instance.disk.get_callnumber())
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="DiskReview", Type=g.modify_flag, model_refer=ref_id, user_affected=g.user, content="%s disk review of %s" % (g.modify_flag, instance.disk.get_callnumber()))
        return instance

    def check_post(self, obj=None):
        return not obj

    def check_put(self, obj):
        return False

    def check_delete(self, obj):
        return g.user.admin

user_auth = CustomAuthentication(auth)
admin_auth = CustomAdminAuthentication(auth)
read_auth = Authentication()

# instantiate api object
api = CustomRestAPI(app, default_auth=admin_auth)

# register resources
api.register(File, FileResource, auth=read_auth)
api.register(User, UserResource)
api.register(Log, LogResource, auth=read_auth)
api.register(Disk, DiskResource, auth=user_auth)
api.register(RegularFilmShow, RegularFilmShowResource, auth=user_auth)
api.register(PreviewShowTicket, PreviewShowTicketResource, auth=user_auth)
api.register(DiskReview, DiskReviewResource, auth=user_auth)
