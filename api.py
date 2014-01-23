import uuid
from datetime import datetime, timedelta

from flask import g, jsonify, render_template, request, json, Response
from peewee import DoesNotExist, fn
from flask_peewee.rest import Authentication
from flask_peewee.utils import get_object_or_404

from app import app
from auth import auth
from models import *
from forms import *
from helpers import query_user, upload_file, send_email, \
                    update_mailing_list
from frame_ext import JSONRestAPI, HookedResource, BusinessException, \
                        BaseAuthentication, AdminAuthentication

__all__ = [
    'api',
]


class LoggedRestResource(HookedResource):
    """Resource that have log on basic operations

    Logs will be created on creation, edition, and deletion

    :param log_model:
        The name of model_refer field in Log. Must be set by successor.
    :param validate_form:
        The validate from of creation and edition. Must be set by
        successor.
    """
    log_model = None

    def get_log(self, instance, id):
        """Return the log content of the operation

        Only used in creation, edition, or deletion

        :param instance:
            The instance to be saved
        :param id:
            The id of the instance
        """
        raise NotImplementedError

    def before_save(self, instance):
        """Document in log before saving the instance

        :param instance:
            The instance to be saved
        """
        if self.log_model is None:
            raise NotImplementedError

        ref_id = (self.model.next_primary_key()
                    if g.modify_flag == 'create' else instance.id)
        content = self.get_log(instance, ref_id)

        if g.modify_flag == 'create':
            log = Log.create(
                model=self.log_model, log_type=g.modify_flag,
                model_refer=ref_id, user_affected=None,
                admin_involved=g.user, content=content)
            instance.create_log = log
        elif g.modify_flag == 'delete':
            # delete related logs
            Log.delete().where(Log.model == self.log_model,
                Log.model_refer == ref_id)
            #create delete log
            log = Log.create(
                model=self.log_model, log_type=g.modify_flag,
                model_refer=ref_id, user_affected=None,
                admin_involved=g.user, content=content)
        else:
            log = Log.create(
                model=self.log_model, log_type=g.modify_flag,
                model_refer=ref_id, user_affected=None,
                admin_involved=g.user, content=content)
        return instance


class FileResource(HookedResource):
    """The resource to handle file upload

    The file upload will not be logged in the system
    """
    def check_post(self, obj=None):
        """Edition not allowed through API"""
        return obj is None

    def check_put(self, obj):
        """Edition not allowed through API"""
        return False

    def check_delete(self, obj):
        """Deletion not allowed through API"""
        return False

    def create(self):
        """Create file on upload

        The file will be relayed to FTP server
        The server only keeps a record of the file
        """
        # The file uploaded
        file = request.files['file']
        name = file.filename
        # extract the extension
        ext = ('.' + name.rsplit('.', 1)[1]) if '.' in name else ''

        # Generate a unique random filename
        new_filename = str(uuid.uuid4()) + ext
        while File.select().where(File.url == new_filename).count() > 0:
            new_filename = str(uuid.uuid4()) + ext

        # upload to FTP server
        try:
            upload_file(new_filename, file)
        except Exception:
            return jsonify(errno=500, error="Upload failed")

        # save record
        instance = File.create(name=name, url=new_filename)
        return self.object_detail(instance)


class UserResource(HookedResource):
    """The API to manage member/user of the society
    """

    # These fields are handled by system
    readonly = [
                'join_at', 'last_login',
                'this_login', 'login_count', 'rfs_count'
                ]
    search = {
        'default': ['full_name', 'student_id', 'itsc']
    }

    @staticmethod
    def disk_wrapper(disk):
        """Wrap disk information a little bit"""
        if isinstance(disk, int):
            disk = Disk.select().where(Disk.id == disk).get()
        return {
            "id": disk.id,
            "cover_url": disk.cover_url.url,
            "title_en": disk.title_en,
            "title_ch": disk.title_ch
        }

    def prepare_data(self, obj, data):
        """Adding extra information of disk holding information
        """
        data['borrowed'] = map(self.disk_wrapper, obj.borrowed)
        data['reserved'] = map(self.disk_wrapper, obj.reserved)

        history_sq = Log.select().where(
            Log.log_type == 'borrow',
            Log.model == 'Disk',
            Log.user_affected == obj,
            Log.content % "check out%").group_by(Log.model_refer).limit(10)
        data['borrow_history'] = map(self.disk_wrapper, history_sq)
        return super(UserResource, self).prepare_data(obj, data)

    def validate_data(self, data, obj=None):
        """Check the validity of member information
        """
        data = self.data_precheck(data, UserForm)
        
        data['itsc'] = data['itsc'].lower()
        # validate uniqueness
        if g.modify_flag == 'create':
            # There should be no other member that has the same student ID
            # or the same university ID with this new member

            # Validate itsc account, and fill the display name
            user_info = query_user(data.get('itsc', None))
            if not user_info:
                raise BusinessException(
                    "Wrong ITSC, please check the spelling")
            data['full_name'] = user_info['displayName']

            # Check the uniqueness of ITSC account
            if User.select().where(User.itsc == data['itsc']).exists():
                raise BusinessException("ITSC existed")
            # Check the uniqueness of student ID
            if User.select().where(User.student_id == data['student_id']).exists():
                raise BusinessException("Student ID existed")
            # Check the uniqueness of University ID
            if data.get('university_id', None) and \
                    User.select().where(
                        User.university_id == data['university_id']).exists():
                raise BusinessException("University ID existed")
        elif g.modify_flag == 'edit':
            # If the unique fields are changed, we must go through a check

            if obj.itsc != data['itsc']:
                # validate the existence first
                user_info = query_user(data.get('itsc', None))
                if not user_info:
                    raise BusinessException(
                        "Wrong ITSC, please check the spelling")
                data['full_name'] = user_info['displayName']

                # check the uniqueness then
                if User.select().where(User.itsc == data['itsc']).exists():
                    raise BusinessException("ITSC existed")
            # Check the student ID
            if obj.student_id != data['student_id'] and \
                    User.select().where(
                        User.student_id == data['student_id']).exists():
                raise BusinessException("Student ID existed")
            # Check the university ID
            if data.get('university_id', None) and \
                    obj.university_id != data['university_id'] and \
                    User.select().where(
                        User.university_id == data['university_id']).exists():
                raise BusinessException("University ID existed")
        return data

    def before_save(self, instance):
        """Create Log and update mailing list on deletion
        """
        if g.modify_flag == 'delete':
            ref_id = instance.id
            # delete related logs
            Log.delete.where(Log.user_affected == instance)
            # insert deletion log
            Log.create(
                model="User", log_type=g.modify_flag,
                model_refer=ref_id, admin_involved=g.user,
                content="delete member " + instance.itsc)
        else:
            # create or edit
            ref_id = instance.id
            Log.create(
                model="User", log_type=g.modify_flag,
                model_refer=ref_id, user_affected=instance,
                admin_involved=g.user,
                content=("%s member %s") % (g.modify_flag, instance.itsc))

        return instance

    def after_save(self, instance=None):
        """update mailing list after any edition
        """
        query = User.select(User.itsc)
        update_mailing_list(
            [x.itsc for x in query.where(User.member_type != 'Expired')])

    def get_urls(self):
        return (
            ('/current_user/', self.require_method(self.api_current, ['GET'])),
            ('/relation/', self.require_method(self.api_relation, ['POST'])),
        ) + super(UserResource, self).get_urls()

    def check_get(self, obj=None):
        """only visible to self or admins"""
        if g.user and g.user.admin:
            return True
        if obj is None:
            return False
        return g.user == obj

    def api_current(self):
        """API to acquire the current logged in user information
        """
        obj = auth.get_logged_in_user()

        if obj is None:
            raise BusinessException("Not logged in", 2)

        return self.object_detail(obj)

    def api_relation(self):
        """API to bind student ID and university ID

        For back compatibility since member before 2013 may not have
        university ID recorded
        """
        data = request.data or request.form.get('data') or ''

        if not getattr(self, 'check_%s' % request.method.lower())():
            return self.response_forbidden()
        data = self.data_precheck(data, RelationForm)

        try:
            obj = User.select().where(User.student_id == data['student_id']).get()
        except DoesNotExist:
            return jsonify(errno=3, error="User not found")

        # although bound before, return it
        if obj.university_id and obj.university_id == data['university_id']:
            return self.object_detail(obj)

        # university id should be unique
        if User.select().where(User.university_id == data['university_id']).exists():
            return jsonify(errno=3, error="Duplicate University ID of other member")
        
        # apply change
        obj.university_id = data['university_id']
        obj.save()
        Log.create(
            model='User', log_type='edit', model_refer=obj.id,
            user_affected=obj, admin_involved=g.user,
            content="Bind student ID and University ID for user %s" % obj.itsc)
        return self.object_detail(obj)


class SimpleUserResource(HookedResource):
    """Simple resource that will be used by other resources"""
    fields = ['id', 'itsc', 'student_id', 'university_id', 'full_name']


class LogResource(HookedResource):
    """API to acquire logs"""
    search = {
        'default': ['content']
    }
    include_resources = {
        'user_affected': SimpleUserResource,
        'admin_involved': SimpleUserResource,
    }

    def check_get(self, obj=None):
        return g.user and g.user.admin


class SimpleLogResource(HookedResource):
    """For those only need create date and time"""
    fields = ['created_at']


class DiskResource(LoggedRestResource):
    """API of VCD/DVD Library

    Features include borrow, reserve
    """
    log_model = "Disk"
    validate_form = DiskForm

    readonly = [
        'hold_by', 'reserved_by',
        'borrow_cnt', 'rank', 'create_log'
    ]
    # Internal use, not visible to anyone
    exclude = ['rank']

    filter_exclude = [
        'rank', 'hold_by', 'due_at', 'reserved_by', 'create_log'
    ]
    search = {
        'default': ['title_en', 'title_ch'],
        'fulltext': [
            'title_en', 'title_ch', 'desc_en',
            'desc_ch', 'director_en', 'director_ch', 'actors'
        ],
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
        """Adding extra information of holder and filter information
        from common members
        """
        if g.user and (obj.reserved_by == g.user or obj.hold_by == g.user):
            data['user_held'] = True
        else:
            data['user_held'] = False
        if not (g.user and g.user.admin):
            data.pop('hold_by', None)
            data.pop('reserved_by', None)
        return super(DiskResource, self).prepare_data(obj, data)

    def get_urls(self):
        return (
            ('/<pk>/reservation/',
                self.require_method(self.api_reserve, ['POST', 'DELETE'])),
            ('/<pk>/borrow/',
                self.require_method(self.api_borrow, ['POST', 'DELETE'])),
            ('/<pk>/rate/',
                self.require_method(self.api_rate, ['GET', 'POST'])),
            ('/rand/', self.require_method(self.api_rand, ['GET'])),
        ) + super(DiskResource, self).get_urls()

    def get_log(self, instance, id):
        callnumber = Disk.construct_callnumber(instance.disk_type, id)
        return "%s disk %s" % (g.modify_flag, callnumber)

    def get_query(self):
        """Hide drafts to common member"""
        if g.user and g.user.admin:
            return super(DiskResource, self).get_query()
        else:
            return self.model.select().where(self.model.avail_type != "Draft")

    def api_reserve(self, pk):
        """API to reserve a disk"""
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get('data') or ''

        new_log = Log(model='Disk', log_type='reserve', model_refer=obj.id)

        if request.method == 'POST':
            data = self.data_precheck(data, ReserveForm)

            # reserve the disk
            obj.reserve(g.user, data['form'])
            new_log.user_affected = g.user

            if data['form'] == 'Counter':
                new_log.content = ("member %s reserves disk"
                                    " %s (counter)") % \
                                    (g.user.itsc, obj.get_callnumber())
            elif data['form'] == 'Hall':
                new_log.content = ("member %s reserves disk"
                                    " %s (Hall %d %s). remarks: %s") %\
                                    (
                                        g.user.itsc,
                                        obj.get_callnumber(),
                                        data.get('hall', ''),
                                        data.get('room', ''),
                                        data.get('remarks', '')
                                    )

                # send email to reminder exco to deliver disk
                mail_content = render_template(
                    'exco_reserve.html', disk=obj, member=g.user,
                    data=data, time=str(datetime.now()))
                sq = Exco.select().where(
                    Exco.hall_allocate % ("%%%d%%" % int(data.get('hall', '*'))))
                send_email(
                    ['su_film@ust.hk'] + [x.email for x in sq], [],
                    "Delivery Request", mail_content)

        elif request.method == 'DELETE':
            # clear reservation
            if not self.check_delete(obj):
                return self.response_forbidden()

            new_log.content = "clear reservation for disk %s" % obj.get_callnumber()
            new_log.admin_involved = g.user
            new_log.user_affected = obj.reserved_by
            obj.clear_reservation()

        obj.save()
        new_log.save()
        return self.response({})

    def api_borrow(self, pk):
        """API to borrow disk"""
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get('data') or ''

        new_log = Log(model='Disk', log_type='borrow', model_refer=obj.id)

        if request.method == 'POST':
            data = self.data_precheck(data, SubmitUserForm)

            # existence has been checked by SubmitUserForm
            req_user = User.select().where(User.id == data['id']).get()
            if obj.avail_type == 'Borrowed':
                # renew
                # only admin or holder can renew
                if obj.hold_by != req_user:
                    return jsonify(errno=3, error="Disk not borrowed by the user")
                if not self.check_post(obj) and req_user != g.user:
                    return self.response_forbidden()
                
                # renew it
                obj.renew()
                new_log.content = ("member %s renews disk %s" %
                                (req_user.itsc, obj.get_callnumber()))
                new_log.user_affected = req_user
                if g.user.admin:
                    new_log.admin_involved = g.user
            elif obj.avail_type == 'Reserved':
                # taken to deliver
                if not self.check_post(obj):
                    return self.response_forbidden()

                obj.deliver()
                new_log.content = ("take out disk %s for delivery" % 
                                    obj.get_callnumber())
                new_log.user_affected = req_user
                new_log.admin_involved = g.user

            else:
                # checkout
                if not self.check_post(obj):
                    return self.response_forbidden()

                obj.check_out(req_user)
                new_log.content = ("check out disk %s for member %s" %
                                (obj.get_callnumber(), req_user.itsc))
                new_log.user_affected = req_user
                new_log.admin_involved = g.user

        elif request.method == 'DELETE':
            if not self.check_delete(obj):
                return self.response_forbidden()

            obj.check_in()
            new_log.content = "check in disk %s" % obj.get_callnumber()
            new_log.admin_involved = g.user

        obj.save()
        new_log.save()
        return self.response({})

    def api_rate(self, pk):
        """API to acquire the ups and downs of a disk"""
        data = request.data or request.form.get('data') or ''
        obj = get_object_or_404(self.get_query(), self.pk == pk)

        if request.method == 'GET':
            """Return the rates and whether a user has rated before"""
            ups, downs = obj.get_rate()
            rated = g.user and Log.select().where(
                Log.model == 'Disk', Log.model_refer == obj.id,
                Log.log_type == 'rate', Log.user_affected == g.user).exists()
        elif request.method == 'POST':
            data = self.data_precheck(data, RateForm)
            if not g.user:
                return self.response_forbidden()

            obj.add_rate(data['rate'])
            rated = True
            ups, downs = obj.get_rate()

        return self.response({
            'ups': ups,
            'downs': downs,
            'rated': rated
        })

    def api_rand(self):
        """API to return a random disk"""
        obj = self.model.select().where(
            self.model.disk_type << ['B']
        ).order_by(fn.Rand()).limit(1).get()

        return self.object_detail(obj)


class RegularFilmShowResource(LoggedRestResource):
    """API of Regular Film Show

    Voting system is handled by this API
    """
    log_model = "RegularFilmShow"
    validate_form = RegularFilmShowForm

    readonly = [
        'vote_cnt_1', 'vote_cnt_2',
        'vote_cnt_3', 'participant_list'
    ]

    include_resources = {
        'film_1': DiskResource,
        'film_2': DiskResource,
        'film_3': DiskResource,
        'create_log': SimpleLogResource,
    }

    def get_query(self):
        """Hide drafts to member"""
        if g.user and g.user.admin:
            return super(RegularFilmShowResource, self).get_query()
        else:
            return self.model.select().where(self.model.state != "Draft")

    def validate_data(self, data, obj=None):
        data = super(RegularFilmShowResource, self).validate_data(data, obj)
        if g.modify_flag == 'edit':
            if obj.state != 'Draft':
                # Published show
                if data.get('film_1', obj.film_1.id) != obj.film_1.id or \
                        data.get('film_2', obj.film_2.id) != obj.film_2.id or \
                        data.get('film_3', obj.film_3.id) != obj.film_3.id:
                    raise BusinessException(
                        "Cannot modify candidate film if not Draft")
                if data['state'] == 'Draft':
                    # Forbid such behaviour
                    raise BusinessException("Cannot turn back to Draft")
            if obj.state != 'Open' and data['state'] == 'Open':
                # settting a show to open
                # there can only be one open show at any time
                if RegularFilmShow.select().where(
                            RegularFilmShow.state == 'Open'
                        ).exists():
                    raise BusinessException("There can be one Open show"
                                            " at a time")

        return data

    def prepare_data(self, obj, data):
        if not (g.user and g.user.admin):
            data.pop('participant_list', None)
        return data

    def get_log(self, instance, id):
        return "%s rfs id=%d" % (g.modify_flag, id)

    def before_save(self, instance):
        instance = super(RegularFilmShowResource, self).before_save(instance)

        if instance.state == 'Open':
            # clear other voting or onshow disk
            sq = Disk.select().where(Disk.avail_type << ['Voting', 'OnShow'])
            for disk in sq:
                disk.avail_type = 'Available'
                disk.save()
            # put disk on voting
            for x in [1, 2, 3]:
                disk = getattr(instance, "film_%d" % x)
                disk.avail_type = 'Voting'
                for y in ['reserved_by', 'hold_by', 'due_at']:
                    setattr(disk, y, None)
                disk.save()

        # set availability of corresponding disks
        if instance.id == RegularFilmShow.get_recent().id:
            # editing previous rfs will not change availability of disks
            if instance.state == 'Pending':
                # disk has the most vote
                largest = instance.to_show()

                # clear other disk
                sq = Disk.select().where(Disk.avail_type << ['Voting', 'OnShow'])
                for disk in sq:
                    disk.avail_type = 'Available'
                    disk.save()

                # set disk on show
                largest.avail_type = 'Onshow'
                largest.save()
            elif instance.state == 'Passed':
                for x in [1, 2, 3]:
                    disk = getattr(instance, "film_%d" % x)
                    if disk.avail_type == 'Voting' or disk.avail_type == 'Onshow':
                        disk.avail_type = 'Available'
                        disk.save()
        return instance

    def get_urls(self):
        return (
            ('/<pk>/vote/', self.require_method(self.api_vote, ['POST'])),
            ('/<pk>/participant/', self.require_method(self.api_particip, ['POST'])),
        ) + super(RegularFilmShowResource, self).get_urls()

    def api_vote(self, pk):
        """API for Movote"""
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        data = self.data_precheck(data, VoteForm)
        if not g.user:
            return self.response_forbidden()

        obj.add_vote(g.user, data['film_id'])
        obj.save()
        return self.response({})

    def api_particip(self, pk):
        """API to note down participants of a regular film show"""
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        if not self.check_post(obj):
            return self.response_forbidden()

        data = self.data_precheck(data, SubmitUserForm)
        # existence has been verified
        user = User.select().where(User.id == data['id']).get()

        obj.signin_user(user)
        user.save()
        obj.save()
        Log.create(
            model="RegularFilmShow", model_refer=obj.id,
            log_type="entry", user_affected=user, admin_involved=g.user,
            content="member %s enter RFS" % user.itsc)

        return self.response({})


class PreviewShowTicketResource(LoggedRestResource):
    """API of Preview Show Tickets

    Features include apply
    """
    log_model = "PreviewShowTicket"
    validate_form = PreviewShowTicketForm

    readonly = ['create_log']

    include_resources = {
        'cover_url': FileResource,
        'create_log': SimpleLogResource,
    }
    search = {
        'default': [
            'title_en', 'title_ch', 'desc_en',
            'desc_ch', 'director_en', 'director_ch', 'actors'
        ],
        'title': ['title_en', 'title_ch'],
    }

    def get_query(self):
        if g.user and g.user.admin:
            return super(PreviewShowTicketResource, self).get_query()
        else:
            return self.model.select().where(self.model.state != "Draft")

    def get_log(self, instance, id):
        return "%s ticket id=%d" % (g.modify_flag, id)

    def get_urls(self):
        return (
            ('/<pk>/application/', self.require_method(self.api_apply, ['POST'])),
        ) + super(PreviewShowTicketResource, self).get_urls()

    def api_apply(self, pk):
        """API to apply for a ticket"""
        obj = get_object_or_404(self.get_query(), self.pk == pk)
        data = request.data or request.form.get("data") or ''

        if not g.user:
            return self.response_forbidden()
        data = self.data_precheck(data, ApplyTicketForm)

        obj.add_application(g.user, data)
        Log.create(
            model="PreviewShowTicket", log_type='apply',
            model_refer=obj.id, user_affected=g.user,
            content=("member %s apply for ticket id=%d" % 
                (g.user.itsc, obj.id))
        )

        return self.response({})


class DiskReviewResource(LoggedRestResource):
    """API of reviews on disks
    """
    log_model = "DiskReview"
    validate_form = DiskReviewForm

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

    def get_log(self, instance, id):
        return ("%s disk review of %s" %
                (g.modify_flag, instance.disk.get_callnumber()))

    def before_save(self, instance):
        """Document in log before saving the instance

        :param instance:
            The instance to be saved
        """
        ref_id = (self.model.next_primary_key()
                    if g.modify_flag == 'create' else instance.id)
        content = self.get_log(instance, ref_id)

        if g.modify_flag == 'create':
            log = Log.create(
                model=self.log_model, log_type=g.modify_flag,
                model_refer=ref_id, user_affected=g.user,
                admin_involved=None, content=content)
            instance.create_log = log
            instance.poster = g.user
        else:
            ref_id = instance.id
            # delete related logs
            Log.delete().where(Log.model == self.log_model,
                Log.model_refer == ref_id)
            #create delete log
            log = Log.create(
                model=self.log_model, log_type=g.modify_flag,
                model_refer=ref_id, user_affected=instance.poster,
                admin_involved=g.user, content=content)
        return instance

    def check_post(self, obj=None):
        return g.user and not obj

    def check_put(self, obj):
        return False


class NewsResource(LoggedRestResource):
    """API of posting news
    """
    log_model = "News"
    validate_form = NewsForm

    include_resources = {
        'create_log': SimpleLogResource,
    }
    search = {
        'default': ['title', 'content']
    }

    def get_log(self, instance, id):
        return "%s news %s" % (g.modify_flag, instance.title)


class DocumentResource(LoggedRestResource):
    """API of posting documet
    """
    log_model = "Document"
    validate_form = DocumentForm

    include_resources = {
        'create_log': SimpleLogResource,
        'doc_url': FileResource,
    }
    search = {
        'default': ['title']
    }

    def get_log(self, instance, id):
        return "%s document %s" % (g.modify_flag, instance.title)


class PublicationResource(LoggedRestResource):
    """API of posting publications
    """
    log_model = "Publication"
    validate_form = PublicationForm

    include_resources = {
        'create_log': SimpleLogResource,
        'doc_url': FileResource,
        'cover_url': FileResource,
    }
    search = {
        'default': ['title']
    }

    def get_log(self, instance, id):
        return "%s publication %s" % (g.modify_flag, instance.title)

    def before_save(self, instance):
        instance = super(PublicationResource, self).before_save(instance)
        if instance.pub_type == 'MicroMagazine':
            instance.doc_url = None
        else:
            instance.ext_doc_url = None
        return instance


class SponsorResource(LoggedRestResource):
    """API of posting sponsors
    """
    log_model = "Sponsor"
    validate_form = SponsorForm

    include_resources = {
        'create_log': SimpleLogResource,
        'img_url': FileResource,
    }
    search = {
        'default': ['name']
    }

    def get_log(self, instance, id):
        return "%s sponsor %s" % (g.modify_flag, instance.name)


class ExcoResource(HookedResource):
    """API of exco information
    """
    validate_form = ExcoForm

    readonly = ['position']
    include_resources = {
        'img_url': FileResource,
    }

    def check_post(self, obj=None):
        return g.user and g.user.admin and obj

    def check_delete(self, obj):
        return False


class SiteSettingsResource(HookedResource):
    """API of site settings
    """
    validate_form = SiteSettingsForm
    readonly = ['key']

    def check_post(self, obj=None):
        return g.user and g.admin and obj

    def check_delete(self, obj):
        return False


class OneSentenceResource(LoggedRestResource):
    """API of quotes from films
    """
    log_model = "OneSentence"
    validate_form = OneSentenceForm

    search = {
        'default': ['film', 'content']
    }
    include_resources = {
        'create_log': SimpleLogResource,
    }

    def get_log(self, instance, id):
        return "%s one sentence id=%d" % (g.modify_flag, id)

    def check_get(self):
        return g.user and g.user.admin

    def get_urls(self):
        return (
            ('/rand/', self.require_method(self.api_rand, ['GET'])),
        ) + super(OneSentenceResource, self).get_urls()

    def api_rand(self):
        """API of a rand quote"""
        obj = self.model.select().order_by(fn.Rand()).limit(1).get()

        return self.object_detail(obj)

# use a centered dirty generator
# dirty map
dirty_map = [
#    guest, Model, actions
    (False, "User", ['edit']),
    (True, "Disk", ['edit', 'reserve', 'borrow']),
    (True, "RegularFilmShow", ['edit', 'vote']),
    (True, "PreviewShowTicket", ['edit']),
    (True, "News", ['edit']),
    (True, "Document", ['edit']),
    (True, "Publication", ['edit']),
    (True, "Exco", ['edit']),
    (True, "Sponsor", ['edit']),
]
# return a list of modified items within a certain interval
@app.route('/api/dirty/')
def dirty():
    result = {}
    referrer = request.referrer or ''
    if not referrer.startswith(app.config['FRONT_SERVER']):
        return jsonify(errno=403, error="Not Authorized")
    for x in dirty_map:
        if x[0] or (g.user and g.user.admin):
            sq = Log.select().where(
                Log.model == x[1],
                Log.created_at > (datetime.now() - timedelta(minutes=6)),
                Log.log_type << x[2]
            )
            result[x[1].lower()] = [y.model_refer for y in sq]
    # response
    result['errno'] = 0
    result['error'] = ''
    kwargs = {'separators': (',', ':')} if request.is_xhr else {'indent': 2}
    return Response(json.dumps(result, **kwargs), mimetype='application/json')


# fit for common users
user_auth = BaseAuthentication(auth)

# fit for admin involved models
admin_auth = AdminAuthentication(auth)

# fit for system manipulated models
read_auth = Authentication()

# instantiate api object
api = JSONRestAPI(app, default_auth=admin_auth)

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
