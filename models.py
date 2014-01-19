from datetime import date, datetime, timedelta

from flask import render_template
from peewee import *

from frame_ext import IterableModel, BusinessException
from db_ext import SimpleListField
from helpers import send_email

__all__ = [
    'File',
    'User',
    'Log',
    'Disk',
    'RegularFilmShow',
    'PreviewShowTicket',
    'DiskReview',
    'News',
    'Document',
    'Publication',
    'Sponsor',
    'Exco',
    'SiteSettings',
    'OneSentence',
    'create_tables',
]


class File(IterableModel):
    """Contain files uploaded to FTP server

    :param id:
        A unique ID of the file
    :param name:
        The display name of the file
    :param url:
        The storage path of the file
    """
    id = PrimaryKeyField()

    name = CharField()
    url = CharField(unique=True)


class User(IterableModel):
    """Model of users/members

    This is the user system basis of the website

    :param id:
        A unique ID of the member
    :param itsc:
        The ITSC account name of the member (required)
    :param student_id:
        The Student ID of the member. (required)
        The length should be exactly 8
        In fact not essential as *Student* ID since staff also have ID
    :param university_id:
        The university ID of the member.
        Used to scan ID card.
    :param mobile:
        The mobile number of the member
    :param full_name:
        The official display name of the member

    :param member_type:
        The type of the member. Can only be one of the following:
        Full, OneSem, OneYear, TwoYear, ThreeYear, Honour, Assoc, Expired
    :param join_at:
        The date of the member joining society
    :param expire_at:
        The date of the membership expiry
    :param pennalized:
        A member may be pennalized for not returning disk.
        Upon set of this flag, he/she will not be able to borrow
        disk from VCD/DVD Library for a period of time

    :param last_login:
        The date and time last time the member logged in
    :param this_login:
        The date and time this time the member logged in
    :param login_count:
        The times of the member log in to the website

    :param rfs_count:
        The times of the member participate in regular film show

    :param admin:
        Whether the member is admin
    """
    id = PrimaryKeyField()

    itsc = CharField(unique=True)
    student_id = CharField(max_length=8, unique=True)
    university_id = CharField(max_length=9, null=True, unique=True)
    mobile = CharField(max_length=8, null=True)
    full_name = CharField()

    member_type = CharField(max_length=16)
    join_at = DateField(default=datetime.now)
    expire_at = DateField()
    pennalized = BooleanField(default=False)

    last_login = DateTimeField(null=True, default=None)
    this_login = DateTimeField(null=True, default=None)
    login_count = IntegerField(default=0)

    rfs_count = IntegerField(default=0)

    admin = BooleanField(default=False)

    class Meta:
        indexes = (
            (('full_name',), False),
        )
        order_by = ('full_name', 'itsc',)


class Log(IterableModel):
    """Model to store logs of all the business

    This records all the business going through the website. It is a
    core part to understand the visitors statistically.

    :param id:
        A unique ID of a log

    :param model:
        The model name the log refers to
    :param log_type:
        The business type of the logged event
    :param model_refer:
        The ID of the instance referred to
    :param user_affected:
        The user affected in this event
    :param admin_involved:
        The admin involved in this event
    :param content:
        A concrete discription of the event

    :param created_at:
        The date and time the log created
    """

    id = PrimaryKeyField()

    model = CharField(max_length=32)
    log_type = CharField(max_length=16)
    model_refer = IntegerField()
    user_affected = ForeignKeyField(User, related_name='actions', null=True)
    admin_involved = ForeignKeyField(User, null=True)
    content = TextField(null=True)

    created_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = (
            (('model',), False),
            (('model', 'log_type'), False),
            (('model', 'model_refer'), False),
        )
        order_by = ('-created_at', '-id')


class LogModel(IterableModel):
    """Model that has a foreign key to the log of creation

    :param create_log:
        The log of creation.
    """
    create_log = ForeignKeyField(Log)


class Disk(LogModel):
    """Model to store disks of VCD/DVD Library

    TODO: migrate to NoSQL. Fields of a disk have high tendancy to be
    extended.

    :param id:
        A unique ID of a disk, consisting of the call number of a disk
    :param disk_type:
        The type of a disk, A for VCD, B for DVD, maybe C for Blueray

    <call number> ::= <disk_type><id>
    <id> is padded to 4 digits by now

    :param title_en:
        The English title of the disk
    :param title_cn:
        The Chinese title of the disk, should be in traditional Chinese
    :param desc_en:
        The English description of the disk
    :param desc_ch:
        The Chinese description of the disk
    :param director_en:
        The English name of the director of the disk
    :param director_ch:
        The Chinese name of the director of the disk
    :param actors:
        A list of leading stars cast in the disk

    :param show_year:
        The year of the disk on display
    :param cover_url:
        The image file of the disk cover
    :param tags:
        A list of tags on the disk, similar to genre
    :param imdb_url:
        The URL to the page of the disk on IMDB
    :param length:
        The length of the disk, in minutes
    :param category:
        The classification in HK, can be one of the following:
        I, II A, II B, III, (null)(indicating unknown)

    :param hold_by:
        The person who borrowed the disk
    :param due_at:
        The due date of the rent
    :param reserved_by:
        The person who reserve the disk
    :param avail_type:
        The available state of the disk, can be one of the following:
        Draft(editing, not visible to non admin),
        Available(available to be reserved or borrowed),
        Borrowed(as its name),
        Reserved(reserved and quest delivery),
        ReservedCounter(reserved and will be retrieved at counter),
        OnDelivery(checked out by exco for delivery),
        Voting(being voted for regular film show),
        Onshow(will be put on show on next regular film show)

    :param borrow_cnt:
        The total times the disk being borrowed
    :param rank:
        An internal quantity calculated by ups and downs the disk
        gets. Higher is better. View :file disk_evaluate.py: for more
        information
    """
    id = PrimaryKeyField()
    disk_type = CharField(max_length=1)

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField(null=True)
    desc_ch = TextField(null=True)
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = SimpleListField(null=True)

    show_year = IntegerField()
    cover_url = ForeignKeyField(File, related_name='disk_usage', null=True)
    tags = SimpleListField(null=True)
    imdb_url = CharField(null=True)
    length = IntegerField(null=True)
    category = CharField(max_length=8, null=True)

    hold_by = ForeignKeyField(User, related_name='borrowed', null=True)
    due_at = DateField(null=True)
    reserved_by = ForeignKeyField(User, related_name='reserved', null=True)
    avail_type = CharField(max_length=16)

    borrow_cnt = IntegerField(default=0)
    rank = DecimalField(default=0)

    class Meta:
        order_by = ('-id',)

    @staticmethod
    def construct_callnumber(disk_type, disk_id):
        """Return the callnumber from type and id

        :param disk_type:
            The type of the disk
        :param disk_id:
            The id of the disk
        """
        return disk_type + str(disk_id).rjust(4, '0')

    @staticmethod
    def check_enable():
        """Return the availability of VCD/DVD Library"""
        return SiteSettings.get('liba_state') == "Open"

    @staticmethod
    def get_borrow_limit():
        """Return the limit of disk one user can borrow"""
        return int(SiteSettings.get('liba_borrow'))

    @staticmethod
    def get_reserve_limit():
        """Return the limit of disk one user can borrow"""
        return int(SiteSettings.get('liba_reserve'))

    def get_callnumber(self):
        """Return the call number of the disk
        Format: <disk_type><length 4 padded ID>
        """
        return self.construct_callnumber(self.disk_type, self.id)

    def reserve(self, user, reserve_type):
        """Reserve the disk

        Check the state of the disk and reserve it for the user

        :param user:
            The user that tries to reserve the disk
        :param reserve_type:
            The type of the reservation
        """
        # go through checks
        reserve_limit = self.get_borrow_limit()
        if user.reserved.count() >= reserve_limit:
            raise BusinessException(
                ("A member can reserve at most %d disks"
                " at the same time" % reserve_limit), 
                3)
        if self.avail_type != 'Available':
            raise BusinessException("Disk not reservable", 3)
        if not self.check_enable():
            raise BusinessException("VCD/DVD Library Closed", 3)

        self.reserved_by = g.user
        self.avail_type = "Reserve" + reserve_type

    def clear_reservation(self):
        """Clear the reservation of the disk"""
        if self.avail_type not in [
                'Reserved', 'ReservedCounter', 'OnDelivery']:
            raise BusinessException("The disk is not reserved", 3)

        self.reserved_by = None
        self.avail_type = 'Available'

    def deliver(self):
        """Deliver the disk"""
        borrow_limit = self.get_borrow_limit()
        if self.reserved_by.borrowed.count() >= borrow_limit:
            raise BusinessException(
                ("A member can borrow at most %d disks"
                " at the same time" % borrow_limit),
                3)
        if not self.check_enable():
            raise BusinessException("VCD/DVD Library Closed", 3)

        self.avail_type = 'OnDelivery'

    def check_out(self, user):
        """Check out the disk

        Check the state of the disk and then set essential fields of
        the disk. Note that this method will not save the instance.

        :param user:
            The user that tries to borrow the disk
        """
        borrow_limit = self.get_borrow_limit()
        if self.reserved_by.borrowed.count() >= borrow_limit:
            raise BusinessException(
                ("A member can borrow at most %d disks"
                " at the same time" % borrow_limit),
                3)
        if not self.check_enable():
            raise BusinessException("VCD/DVD Library Closed", 3)
        if self.avail_type not in [
                "Available", 'Reserved',
                'ReservedCounter', 'OnDelivery']:
            raise BusinessException("The disk is not borrowable", 3)
        
        self.reserved_by = None
        self.avail_type = "Borrowed"
        self.hold_by = user

        # set due date
        due_date = SiteSettings.get('due_date')
        self.due_at = datetime.strptime(due_date, '%Y-%m-%d').date() \
                        if due_date else date.today() + timedelta(7)

        # set borrow count
        self.borrow_cnt += 1

    def renew(self):
        """Renew the disk"""
        if self.due_at < date.today():
            raise BusinessException("Disk is overdue", 3)
        if not self.check_enable():
            raise BusinessException("VCD/DVD Library Closed", 3)
        
        # check renew times
        last_log = Log.select().where(
                Log.model == 'Disk', Log.model_refer == self.id,
                Log.log_type == 'borrow', Log.user_affected == req_user
            ).order_by(Log.created_at.desc()).get()
        if 'renew' in last_log.content:
            # renewed before
            raise BusinessException(
                "The disk can only be renewed once", 3)
        # renew it
        self.due_at = date.today() + timedelta(7)

    def check_in(self):
        """Check in the disk

        Check the state of the disk and then set essential fields of
        the disk. Note that this method will not save the instance.
        """
        if self.avail_type != "Borrowed":
           raise BusinessException("The disk is not borrowed", 3)

        self.avail_type = "Available"
        self.hold_by = None
        self.due_at = None

    def get_rate(self):
        """Return the ups and downs this disk receive

        A tuple (ups, downs) is returned

        TODO: I believe there is better way to implement this
        Maybe it is possible to query the two value in one SQL
        """
        return (
            Log.select().where(
                Log.model == 'Disk',
                Log.model_refer == self.id,
                Log.log_type == 'rate',
                Log.content ** "member % rate +1 for disk %").count(),
            Log.select().where(
                Log.model == 'Disk',
                Log.model_refer == self.id,
                Log.log_type == 'rate',
                Log.content ** "member % rate -1 for disk %").count(),
        )

    def add_rate(self, user, rate='up'):
        """Add rate to the disk

        :param user:
            The user who cast the rate
        :param rate:
            'up' or 'down' indicating the user's preference
        """
        if self.check_enable():
            raise BusinessException("VCD/DVD Library Closed", 3)
        if Log.select().where(
                Log.model == 'Disk', Log.model_refer == self.id,
                Log.log_type == 'rate', Log.user_affected == user).exists():
            raise BusinessException("You have rated this disk before", 3)
        new_log = Log(model='Disk', model_refer=obj.id,
                        log_type='rate', user_affected=g.user)
        if rate == 'up':
            new_log.content = ("member %s rate +1 for disk %s" % 
                                (g.user.itsc, obj.get_callnumber()))
        else:
            new_log.content = ("member %s rate -1 for disk %s" % 
                                (g.user.itsc, obj.get_callnumber()))

        new_log.save()


class RegularFilmShow(LogModel):
    """Model to store Regular Film Show information

    :param id:
        A unique ID of a show

    :param state:
        The state of a show, can only be one of the following:
        Draft(editing, not visible to non-admins),
        Open(visible to everyone, not able to vote),
        Pending(member able to vote, admin able to sign in),
        Passed(only visible)

    TODO: make film_1, film_2, film_3, ... more general
    :param film_1:
        One of the 3 candidate movie of a show
    :param film_2:
        One of the 3 candidate movie of a show
    :param film_3:
        One of the 3 candidate movie of a show

    :param vote_cnt_1:
        The vote for film_1
    :param vote_cnt_2:
        The vote for film_2
    :param vote_cnt_3:
        The vote for film_3

    :param remarks:
        The remarks for this show
    :param participant_list:
        A list of participants who attend this show
    """
        
    id = PrimaryKeyField()
  
    state = CharField(max_length=16)

    film_1 = ForeignKeyField(Disk, related_name='dummy_1', null=True)
    film_2 = ForeignKeyField(Disk, related_name='dummy_2', null=True)
    film_3 = ForeignKeyField(Disk, related_name='dummy_3', null=True)

    vote_cnt_1 = IntegerField(default=0)
    vote_cnt_2 = IntegerField(default=0)
    vote_cnt_3 = IntegerField(default=0)

    remarks = TextField(null=True)
    participant_list = SimpleListField(null=True)

    class Meta:
        order_by = ('-id',)

    @classmethod
    def get_recent(cls):
        """Return the latest regular film show"""
        return cls.select().where(
            cls.state << ['Open', 'Pending']
        ).order_by(cls.id.desc()).limit(1)

    def add_vote(self, user, vote):
        """Add a user vote to the show

        :param user:
            The user who casts the vote
        :param vote:
            The film id voted for
            can be 1, 2, or 3
        """
        if self.state != 'Open':
            raise BusinessException("The show cannot be voted now", 3)
        vote_log = [x.content[-1] for x in
            Log.select().where(
                Log.model == "RegularFilmShow",
                Log.model_refer == self.id,
                Log.log_type == "vote", Log.user_affected == user)]
        if len(vote_log) >= 2:
            raise BusinessException("A member can vote at most twice", 3)
        if vote in vote_log:
            raise BusinessException("You have voted before", 3)
        # add vote count
        setattr(self,
                "vote_cnt_%s" % vote, getattr(obj, "vote_cnt_%s" % vote) + 1)
        # add log
        Log.create(
            model="RegularFilmShow", model_refer=obj.id,
            log_type="vote", user_affected=g.user,
            content="member %s vote for film No. %s" % (user.itsc, vote))

    def signin_user(self, user):
        """Sign in a participant

        :param user:
            The user to be signed in
        """
        if self.state != 'Pending':
            raise BusinessException("The show is not in Pending mode", 3)
        if user.id in self.participant_list:
            raise BusinessException("Recorded before", 3)
        user.rfs_count += 1
        self.participant_list.append(user.id)


class PreviewShowTicket(LogModel):
    """Model to store preview show tickets

    TODO: migrate to NoSQL. Fields of a ticket have high tendancy to be
    extended.

    :param id:
        A unique ID of a ticket
    :param state:
        The state of a ticket, can only be one of the following:
        Draft(editing, not visible to non-admins),
        Open(open to apply),
        Closed(application period passed)

    :param title_en:
        The English title of the movie
    :param title_cn:
        The Chinese title of the movie, should be in traditional Chinese
    :param desc_en:
        The English description of the movie
    :param desc_ch:
        The Chinese description of the movie
    :param director_en:
        The English name of the director of the movie
    :param director_ch:
        The Chinese name of the director of the movie
    :param actors:
        A list of leading stars cast in the movie

    :param cover_url:
        The image file of the disk cover
    :param length:
        The length of the disk, in minutes
    :param language:
        The speaking language in the film
    :param subtitle:
        The display subtitle in the film
    :param quantity:
        The quantity of the tickets available
    :param venue:
        The venue of the film on display

    :param apply_deadline:
        The time of the deadline of the application
    :param show_time:
        The time of the film to be shown
    :param remarks:
        The remarks of the ticket

    :param successful_applicant:
        A list of successfully applied applicants
    """
    id = PrimaryKeyField()
    state = CharField()

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField(null=True)
    desc_ch = TextField(null=True)
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = SimpleListField(null=True)

    cover_url = ForeignKeyField(File, related_name='ticket_usage')
    length = IntegerField(null=True)
    language = CharField(null=True)
    subtitle = CharField(null=True)
    quantity = TextField(null=True)
    venue = TextField(null=True)

    apply_deadline = DateTimeField()
    show_time = DateTimeField(null=True)
    remarks = TextField(null=True)

    successful_applicant = TextField(null=True)

    class Meta:
        order_by = ('-apply_deadline', '-id',)

    def add_application(self, user, data):
        """Add an applicant to the ticket

        :param user:
            The applicant
        :param data:
            The JSON format application
        """
        if self.state != 'Open':
            raise BusinessException("The ticket cannot be applied now", 3)
        if Log.select().where(
                Log.model == "PreviewShowTicket",
                Log.log_type == 'apply',
                Log.model_refer == self.id,
                Log.user_affected == user).exists():
            raise BusinessException("", 0)

        # send email to EVP
        mail_content = render_template(
            'ticket_apply.html', ticket=self, member=user,
            data=data, time=str(datetime.now())
        )
        sq = Exco.select().where(Exco.position == "External Vice-President")
        send_email(
            ['su_film@ust.hk'] + [x.email for x in sq], [],
            "Ticket Application", mail_content
        )

    def to_show(self):
        """Return the film that wins the Movote
        """
        return max([1, 2, 3],key=lambda o: getattr(self, "vote_cnt_%d" % o))



class DiskReview(LogModel):
    """Model of reviews by members on a disk in VCD/DVD Library

    :param id:
        A unique ID of a review

    :param poster:
        The user who post the review
    :param disk:
        The disk which the review is on
    :param content:
        The content of the review
    """
    id = PrimaryKeyField()

    poster = ForeignKeyField(User, related_name='posted_reviews', null=True)
    disk = ForeignKeyField(Disk, related_name='reviews')
    content = TextField()

    class Meta:
        order_by = ('-id',)


class News(LogModel):
    """Model of news on homepage

    :param id:
        A unique ID of a news

    :param title:
        The title of the news
    :param content:
        The content of the news
    """
    id = PrimaryKeyField()

    title = TextField()
    content = TextField()

    class Meta:
        order_by = ('-id',)


class Document(LogModel):
    """Model of documents of the society

    :param id:
        A unique ID of a document

    :param title:
        The name of the document
    :param doc_url:
        The file of the document
    """
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File, related_name='doc_usage')

    class Meta:
        order_by = ('id',)


class Publication(LogModel):
    """Model of publications

    :param id:
        A unique ID of a publication

    :param title:
        The title of the publication
    :param doc_url:
        The file of the publication
    :param ext_doc_url:
        If the publication is not stored on FTP server, this field
        may be used. Currently, Micro Magazine relies on this.
    :param cover_url:
        The cover of the publication
    :param pub_type:
        The type of the publication. Can only be one of the following:
        Magazine, MicroMagazine, Podcast
    """
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File, related_name='pub_usage_doc', null=True)
    ext_doc_url = TextField(null=True)
    cover_url = ForeignKeyField(File, related_name='pub_usage_cover')
    pub_type = CharField(max_length=16)

    class Meta:
        indexes = (
            (('pub_type',), False),
        )
        order_by = ('-id',)


class Sponsor(LogModel):
    """Model of sponsor

    :param id:
        A unique ID of a sponsor
    :param name:
        The name of a sponsor
    :param img_url:
        The image of the sponsor trademark
    """
    id = PrimaryKeyField()

    name = TextField()
    img_url = ForeignKeyField(File, related_name='sponsor_usage')


class Exco(IterableModel):
    """Model of Executive-Committees

    :param id:
        A unique ID of each exco

    :param name_en:
        The English name of the exco
    :param name_ch:
        The Chinese name of the exco
    :param position:
        The position this exco holds
    :param descript:
        The personal information an exco may write about
        himself/herself

    :param img_url:
        The photo of the exco
    :param email:
        The email address of the exco

    :param hall_allocate:
        The hall that an exco responsible for delivering disks
        Can only be 1-9(Hall) or *(send to this on error) or (null)
    """
    id = PrimaryKeyField()

    name_en = CharField()
    name_ch = CharField()
    position = CharField()
    descript = TextField(null=True)

    img_url = ForeignKeyField(File)
    email = CharField()

    hall_allocate = CharField(max_length=10, null=True)


class SiteSettings(IterableModel):
    """Model of some common settings of website

    The settings are stroed in key-value pair

    :param key:
        The key of a setting
    :param value:
        The value of a setting
    """
    key = CharField(max_length=16, unique=True)
    value = CharField()

    @classmethod
    def get(cls, key):
        """Return the value of a setting

        :param key:
            The key of the setting
        """
        try:
            return cls.select().where(cls.key == key).get().value
        except DoesNotExist:
            return None


class OneSentence(LogModel):
    """Model of quotes in film displayed on website

    :param id:
        A unique ID of the quote
    :param film:
        The film from with cthe quote came
    :param content:
        The quote
    """
    id = PrimaryKeyField()
    film = TextField()
    content = TextField()


def create_tables():
    # used when setting up database for the first time
    File.create_table()
    User.create_table()
    Log.create_table()
    Disk.create_table()
    RegularFilmShow.create_table()
    PreviewShowTicket.create_table()
    DiskReview.create_table()
    News.create_table()
    Document.create_table()
    Publication.create_table()
    Sponsor.create_table()
    Exco.create_table()
    SiteSettings.create_table()
    OneSentence.create_table()
