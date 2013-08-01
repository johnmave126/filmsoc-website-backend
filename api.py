from string import join
import uuid
from datetime import datetime, timedelta, date

from werkzeug.datastructures import MultiDict
from flask import g, jsonify, render_template, request, json
from peewee import DoesNotExist, fn
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

    search = {
        'default': ['full_name', 'student_id', 'itsc']
    }

    def validate_data(self, data, obj=None):
        form = UserForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        data['itsc'] = data['itsc'].lower()
        # validate uniqueness
        if g.modify_flag == 'create':
            user_info = query_user(data.get('itsc', None))
            if not user_info:
                return False, "Wrong ITSC, please check the spelling"
            data['full_name'] = user_info['displayName']
            if User.select().where(User.itsc == data['itsc']).exists():
                return False, "ITSC existed"
            if User.select().where(User.student_id == data['student_id']).exists():
                return False, "Student ID existed"
            if data.get('university_id', None) and User.select().where(User.university_id == data['university_id']).exists():
                return False, "University ID existed"
        elif g.modify_flag == 'edit':
            if obj.itsc != data['itsc']:
                user_info = query_user(data.get('itsc', None))
                if not user_info:
                    return False, "Wrong ITSC, please check the spelling"
                data['full_name'] = user_info['displayName']
                if User.select().where(User.itsc == data['itsc']).exists():
                    return False, "ITSC existed"
            if obj.student_id != data['student_id'] and User.select().where(User.student_id == data['student_id']).exists():
                return False, "Student ID existed"
            if data.get('university_id', None) and obj.university_id != data['university_id'] and User.select().where(User.university_id == data['university_id']).exists():
                return False, "University ID existed"
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'delete':
            ref_id = instance.id
            Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="delete member " + instance.itsc)
        return instance

    def after_save(self, instance=None):
        if instance:
            ref_id = instance.id
            Log.create(model="User", Type=g.modify_flag, model_refer=ref_id, user_affected=instance, admin_involved=g.user, content=("%s member %s") % (g.modify_flag, instance.itsc))
        # update mailing-list
        # update_mailing_list([x.itsc for x in User.select(User.itsc).where(User.member_type != 'Expired')])
        # disable because it is danger

    def get_urls(self):
        return (
            ('/current_user/', self.require_method(self.api_current, ['GET'])),
            ('/relation/', self.require_method(self.api_relation, ['POST'])),
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
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

    def api_relation(self):
        data = request.data or request.form.get('data') or ''

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        if request.method == 'POST':
            try:
                data = json.loads(data)
            except ValueError:
                return self.response_bad_request()
            # do validation first
            form = RelationForm(MultiDict(data))
            if not form.validate():
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
                return jsonify(errno=1, error=error)
            try:
                obj = User.select().where(User.student_id == data['student_id']).get()
            except DoesNotExist:
                return jsonify(errno=3, error="User not found")
            if obj.university_id:
                return jsonify(errno=3, error="Binded before")
            obj.university_id = data['university_id']
            obj.save()
            Log.create(model='User', Type='edit', model_refer=obj.id, user_affected=obj, admin_involved=g.user, content="Bind student ID and University ID for user %s" % obj.itsc)
        return self.response(self.serialize_object(obj))

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'User',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class SimpleUserResource(CustomResource):
    fields = ['id', 'itsc', 'student_id', 'university_id', 'full_name']


class LogResource(CustomResource):
    search = {
        'default': ['content']
    }
    include_resources = {
        'user_affected': SimpleUserResource,
        'admin_involved': SimpleUserResource,
    }

    def check_get(self, obj=None):
        return g.user and g.user.admin


class SimpleLogResource(CustomResource):
    fields = ['created_at']


class DiskResource(CustomResource):
    readonly = ['hold_by', 'reserved_by', 'borrow_cnt', 'rank', 'create_log']

    exclude = ['rank']
    filter_exclude = ['rank', 'hold_by', 'due_at', 'reserved_by', 'create_log']
    search = {
        'default': ['title_en', 'title_ch'],
        'fulltext': ['title_en', 'title_ch', 'desc_en', 'desc_ch', 'director_en', 'director_ch', 'actors'],
        'actor': ['actors'],
        'tag': ['tags'],
        'director': ['director_ch', 'director_en']
    }
    include_resources = {
        'cover_url': FileResource,
        'create_log': SimpleLogResource,
        'hold_by': SimpleUserResource,
        'reserved_by': SimpleUserResource,
    }

    def prepare_data(self, obj, data):
        if g.user and (obj.reserved_by == g.user or obj.hold_by == g.user):
            data['user_held'] = True
        else:
            data['user_held'] = False
        if not (g.user and g.user.admin):
            data.pop('hold_by', None)
            data.pop('reserved_by', None)
        return super(DiskResource, self).prepare_data(obj, data)

    def validate_data(self, data, obj=None):
        form = DiskForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def get_urls(self):
        return (
            ('/<pk>/reservation/', self.require_method(self.api_reserve, ['POST', 'DELETE'])),
            ('/<pk>/borrow/', self.require_method(self.api_borrow, ['POST', 'DELETE'])),
            ('/<pk>/rate/', self.require_method(self.api_rate, ['GET', 'POST'])),
            ('/rand/', self.require_method(self.api_rand, ['GET'])),
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(DiskResource, self).get_urls()

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = Disk.next_primary_key()
            log = Log.create(model="Disk", Type=g.modify_flag, model_refer=ref_id, user_affected=None, admin_involved=g.user, content="create disk %s" % (instance.disk_type + str(ref_id).ljust(4, '0')))
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

    def check_disable(self):
        state = SiteSettings.select().where(SiteSettings.key === 'liba_state').get()
        return state.value != "Open"

    def get_query(self):
        if g.user and g.user.admin:
            return super(DiskResource, self).get_query()
        else:
            return self.model.select().where(self.model.avail_type != "Draft")

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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
                return jsonify(errno=1, error=error)
            if g.user.reserved.count() >= 2:
                return jsonify(errno=3, error="A member can reserve at most 2 disks at the same time")
            if obj.avail_type != 'Available':
                return jsonify(errno=3, error="Disk not reservable")
            if check_disable():
                return jsonify(errno=3, error="VCD/DVD Library Closed")
            obj.reserved_by = g.user
            new_log.user_affected = g.user

            if data['form'] == 'Counter':
                obj.avail_type = 'ReservedCounter'
                new_log.content = "member %s reserves disk %s (counter)" % (g.user.itsc, obj.get_callnumber())
            elif data['form'] == 'Hall':
                obj.avail_type = 'Reserved'
                new_log.content = "member %s reserves disk %s (Hall %d %s). remarks: %s" % (g.user.itsc, obj.get_callnumber(), data.get('hall', ''), data.get('room', ''), data.get('remarks', ''))
                mail_content = render_template('exco_reserve.html', disk=obj, member=g.user, data=data, time=str(datetime.now()))
                sq = Exco.select().where(Exco.hall_allocate % ("%%%d%%" % int(data.get('hall', '*'))))
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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
                return jsonify(errno=1, error=error)
            try:
                req_user = User.select().where(User.id == data['id']).get()
            except DoesNotExist:
                return jsonify(errno=3, error="User not found")
            if obj.avail_type == 'Borrowed':
                if obj.hold_by != req_user:
                    return jsonify(errno=3, error="Disk not borrowed by the user")
                if (not g.user.admin) and req_user != g.user:
                    return self.response_forbidden()
                if obj.due_at < date.today():
                    return jsonify(errno=3, error="Disk is overdue")
                if check_disable():
                    return jsonify(errno=3, error="VCD/DVD Library Closed")
                # renew
                last_log = Log.select().where(Log.model == 'Disk', Log.model_refer == obj.id, Log.Type == 'borrow', Log.user_affected == req_user).order_by(Log.created_at.desc()).get()
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
                if check_disable():
                    return jsonify(errno=3, error="VCD/DVD Library Closed")
                success, error = obj.check_out(req_user)
                if not success:
                    return jsonify(errno=3, error=error)
                try:
                    due_date = SiteSettings.select().where(SiteSettings.key == 'due_date').get().value
                    obj.due_at = datetime.strptime(due_date, '%Y-%m-%d').date()
                except DoesNotExist:
                    obj.due_at = date.today() + timedelta(7)

                obj.borrow_cnt += 1
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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
                return jsonify(errno=1, error=error)
            if check_disable():
                return jsonify(errno=3, error="VCD/DVD Library Closed")
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

    def api_rand(self):
        if request.method == 'GET':
            obj = self.model.select().where(
                self.model.disk_type << ['B']
            ).order_by(fn.Rand()).limit(1).get()

        return self.response(self.serialize_object(obj))

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'Disk',
            (Log.Type == 'edit' | Log.Type == 'reserve' | Log.Type == 'borrow')
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class RegularFilmShowResource(CustomResource):
    readonly = ['vote_cnt_1', 'vote_cnt_2', 'vote_cnt_3', 'participant_list']

    include_resources = {
        'film_1': DiskResource,
        'film_2': DiskResource,
        'film_3': DiskResource,
        'create_log': SimpleLogResource,
    }

    def get_query(self):
        if g.user and g.user.admin:
            return super(RegularFilmShowResource, self).get_query()
        else:
            return self.model.select().where(self.model.state != "Draft")

    def validate_data(self, data, obj=None):
        form = RegularFilmShowForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def prepare_data(self, obj, data):
        if not (g.user and g.user.admin):
            data.pop('participant_list', None)
        return data

    def before_save(self, instance):
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
                for y in ['reserved_by', 'hold_by', 'due_at', 'hold_by']:
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
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
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

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'RegularFilmShow',
            (Log.Type == 'edit' | Log.Type == 'vote')
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class PreviewShowTicketResource(CustomResource):
    readonly = ['create_log']

    include_resources = {
        'create_log': SimpleLogResource,
    }
    search = {
        'default': ['title_en', 'title_ch', 'desc_en', 'desc_ch', 'director_en', 'director_ch', 'actors'],
        'title': ['title_en', 'title_ch'],
    }

    def get_query(self):
        if g.user and g.user.admin:
            return super(PreviewShowTicketResource, self).get_query()
        else:
            return self.model.select().where(self.model.state != "Draft")

    def validate_data(self, data, obj=None):
        form = PreviewShowTicketForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
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
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
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
                error = join([join(x, ', ') for x in form.errors.values()], ' | ')
                return jsonify(errno=1, error=error)
            if obj.state != 'Open':
                return jsonify(errno=3, error="The ticket cannot be applied now")
            mail_content = render_template('ticket_apply.html', ticket=obj, member=g.user, data=data, time=str(datetime.now()))
            sq = Exco.select().where(Exco.position == "External Vice-President")
            send_email(['su_film@ust.hk'] + [x.email for x in sq], [], "Ticket Application", mail_content)
            Log.create(model="PreviewShowTicket", Type='apply', model_refer=obj.id, user_affected=g.user, content="member %s apply for ticket id=%d" % (g.user.itsc, obj.id))

        return self.response({})

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'PreviewShowTicket',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class DiskReviewResource(CustomResource):
    include_resources = {
        'create_log': SimpleLogResource,
        'poster': SimpleUserResource,
    }
    search = {
        'default': ['content']
    }

    def prepare_data(self, obj, data):
        if not (g.user and g.user.admin):
            data.pop('poster', None)
        return data

    def validate_data(self, data, obj=None):
        form = DiskReviewForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = DiskReview.next_primary_key()
            log = Log.create(model="DiskReview", Type=g.modify_flag, model_refer=ref_id, user_affected=g.user, content="create disk review of %s" % instance.disk.get_callnumber())
            instance.create_log = log
            instance.poster = g.user
        else:
            ref_id = instance.id
            Log.create(model="DiskReview", Type=g.modify_flag, model_refer=ref_id, user_affected=instance.poster, admin_involved=g.user, content="%s disk review of %s" % (g.modify_flag, instance.disk.get_callnumber()))
        return instance

    def check_post(self, obj=None):
        return not obj

    def check_put(self, obj):
        return False

    def check_delete(self, obj):
        return g.user.admin


class NewsResource(CustomResource):
    include_resources = {
        'create_log': SimpleLogResource,
    }
    search = {
        'default': ['title', 'content']
    }

    def get_urls(self):
        return (
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(NewsResource, self).get_urls()

    def validate_data(self, data, obj=None):
        form = NewsForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = News.next_primary_key()
            log = Log.create(model="News", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="create news %s" % instance.title)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="News", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="%s news %s" % (g.modify_flag, instance.title))
        return instance

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'News',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class DocumentResource(CustomResource):
    include_resources = {
        'create_log': SimpleLogResource,
        'doc_url': FileResource,
    }
    search = {
        'default': ['title']
    }

    def get_urls(self):
        return (
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(DocumentResource, self).get_urls()

    def validate_data(self, data, obj=None):
        form = DocumentForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = Document.next_primary_key()
            log = Log.create(model="Document", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="create document %s" % instance.title)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="Document", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="%s document %s" % (g.modify_flag, instance.title))
        return instance

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'Document',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class PublicationResource(CustomResource):
    include_resources = {
        'create_log': SimpleLogResource,
        'doc_url': FileResource,
        'cover_url': FileResource,
    }
    search = {
        'default': ['title']
    }

    def get_urls(self):
        return (
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(PublicationResource, self).get_urls()

    def validate_data(self, data, obj=None):
        form = PublicationForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = Publication.next_primary_key()
            log = Log.create(model="Publication", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="create publication %s" % instance.title)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="Publication", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="%s publication %s" % (g.modify_flag, instance.title))
        return instance

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'Publication',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class SponsorResource(CustomResource):
    include_resources = {
        'create_log': SimpleLogResource,
        'img_url': FileResource,
    }
    search = {
        'default': ['name']
    }

    def get_urls(self):
        return (
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(SponsorResource, self).get_urls()

    def validate_data(self, data, obj=None):
        form = SponsorForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = Sponsor.next_primary_key()
            log = Log.create(model="Sponsor", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="create sponsor %s" % instance.title)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="Sponsor", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="%s sponsor %s" % (g.modify_flag, instance.title))
        return instance

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'Sponsor',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class ExcoResource(CustomResource):
    readonly = ['hall_allocate', 'name_en', 'name_ch', 'position']
    include_resources = {
        'img_url': FileResource,
    }

    def get_urls(self):
        return (
            ('/dirty/', self.require_method(self.api_dirty, ['GET'])),
        ) + super(ExcoResource, self).get_urls()

    def validate_data(self, data, obj=None):
        form = ExcoForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def check_post(self, obj=None):
        return obj

    def check_put(self, obj):
        return g.user and g.user.admin

    def check_delete(self, obj):
        return False

    def api_dirty(self):
        dirty_list = []

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()

        for dirty_item in Log.select().where(
            Log.created_at > (datetime.now() - timedelta(minutes=6)),
            Log.model == 'Exco',
            Log.Type == 'edit'
        ):
            dirty_list.append(dirty_item.model_refer)
        return self.response({'dirty': dirty_list})


class SiteSettingsResource(CustomResource):
    readonly = ['key']

    def validate_data(self, data, obj=None):
        form = SiteSettingsForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def check_post(self, obj=None):
        return obj

    def check_put(self, obj):
        return g.user and g.user.admin

    def check_delete(self, obj):
        return False


class OneSentenceResource(CustomResource):
    search = {
        'default': ['film', 'content']
    }
    include_resources = {
        'create_log': SimpleLogResource,
    }

    def validate_data(self, data, obj=None):
        form = OneSentenceForm(MultiDict(data))
        if not form.validate():
            return False, join([join(x, ', ') for x in form.errors.values()], ' | ')
        return True, ""

    def before_save(self, instance):
        if g.modify_flag == 'create':
            ref_id = OneSentence.next_primary_key()
            log = Log.create(model="OneSentence", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="create one sentence id=%d" % ref_id)
            instance.create_log = log
        else:
            ref_id = instance.id
            Log.create(model="OneSentence", Type=g.modify_flag, model_refer=ref_id, admin_involved=g.user, content="%s one sentence id=%d" % (g.modify_flag, instance.id))
        return instance

    def check_get(self):
        return g.user and g.user.admin

    def get_urls(self):
        return (
            ('/rand/', self.require_method(self.api_rand, ['GET'])),
        ) + super(OneSentenceResource, self).get_urls()

    def api_rand(self):
        if request.method == 'GET':
            obj = self.model.select().order_by(fn.Rand()).limit(1).get()

        return self.response(self.serialize_object(obj))

user_auth = CustomAuthentication(auth)
admin_auth = CustomAdminAuthentication(auth)
read_auth = Authentication()

# instantiate api object
api = CustomRestAPI(app, default_auth=admin_auth)

# register resources
api.register(File, FileResource)
api.register(User, UserResource)
api.register(Log, LogResource, auth=read_auth)
api.register(Disk, DiskResource, auth=user_auth)
api.register(RegularFilmShow, RegularFilmShowResource, auth=user_auth)
api.register(PreviewShowTicket, PreviewShowTicketResource, auth=user_auth)
api.register(DiskReview, DiskReviewResource, auth=user_auth)
api.register(News, NewsResource)
api.register(Document, DocumentResource)
api.register(Publication, PublicationResource)
api.register(Sponsor, SponsorResource)
api.register(Exco, ExcoResource)
api.register(SiteSettings, SiteSettingsResource)
api.register(OneSentence, OneSentenceResource)
