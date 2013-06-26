# Python modules
import datetime

# framework related
from peewee import *

# custom related
from frame_ext import CustomBaseModel
from db_ext import JSONField, SimpleListField

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


class File(CustomBaseModel):
    id = PrimaryKeyField()

    name = CharField()
    url = CharField(unique=True)


# user model
class User(CustomBaseModel):
    id = PrimaryKeyField()

    itsc = CharField(unique=True)
    student_id = CharField(max_length=8, unique=True)  # max length is 8
    university_id = CharField(max_length=9, null=True, unique=True)
    mobile = CharField(max_length=8, null=True)
    full_name = CharField()

    member_type = CharField(max_length=16)  # Full, OneSem, OneYear, TwoYear, ThreeYear, Honour, Assoc
    join_at = DateField(default=datetime.datetime.now)
    expire_at = DateField()
    expired = BooleanField(default=False)
    pennalized = BooleanField(default=False)

    last_login = DateTimeField(null=True, default=None)
    this_login = DateTimeField(null=True, default=None)
    login_count = IntegerField(default=0)

    rfs_count = IntegerField(default=0)  # for regular film show

    admin = BooleanField(default=False)

    class Meta:
        indexes = (
            (('full_name',), False),
        )
        order_by = ('full_name', 'itsc',)

    def rfs_vote(self):
        active_rfs = RegularFilmShow.getRecent()
        return Log.select().where(
            Log.model == 'RegularFilmShow',
            Log.type == 'vote',
            Log.model_refer == active_rfs.id,
            Log.user_affected == self
        )

    def rfs_vote_count(self):
        active_rfs = RegularFilmShow.getRecent()
        return Log.select().where(
            Log.model == 'RegularFilmShow',
            Log.type == 'vote',
            Log.model_refer == active_rfs.id,
            Log.user_affected == self
        ).count()


#log model
class Log(CustomBaseModel):
    id = PrimaryKeyField()

    model = CharField(max_length=16)
    Type = CharField(max_length=16)
    model_refer = IntegerField()
    user_affected = ForeignKeyField(User, null=True)
    admin_involved = ForeignKeyField(User, null=True)
    content = TextField(null=True)

    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        indexes = (
            (('model',), False),
            (('model', 'Type'), False),
        )
        order_by = ('-created_at', '-id')


class Disk(CustomBaseModel):
    id = PrimaryKeyField()
    disk_type = CharField(max_length=1)  # A for VCD, B for DVD, maybe C for Blueray

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField(null=True)
    desc_ch = TextField(null=True)
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = SimpleListField(null=True)  # actors, simmple list

    show_year = IntegerField()
    cover_url = ForeignKeyField(File, null=True)
    tags = SimpleListField(null=True)  # tags, json
    imdb_url = CharField(null=True)
    length = IntegerField(null=True)
    category = CharField(max_length=8, null=True)

    hold_by = ForeignKeyField(User, related_name='borrowed', null=True)
    due_at = DateField(null=True)
    reserved_by = ForeignKeyField(User, related_name='reserved', null=True)
    avail_type = CharField(max_length=16)  # Draft, Available, Borrowed, Reserved, ReservedCounter, Voting, Onshow

    borrow_cnt = IntegerField(default=0)
    rank = DecimalField(default=0)

    create_log = ForeignKeyField(Log)

    class Meta:
        order_by = ('-id',)

    def get_callnumber(self):
        return self.disk_type + str(self.id)

    def check_out(self, user):
        if self.avail_type not in ["Available", 'Reserved', 'ReservedCounter']:
            return (False, "The disk is not borrowable")

        if self.reserved_by is not None:
            self.reserved_by = None

        self.avail_type = "Borrowed"
        self.hold_by = user
        return (True, "")

    def check_in(self):
        if self.avail_type != "Borrowed":
            return (False, "The disk is not borrowed")

        self.avail_type = "Available"
        self.hold_by = None

        return (True, "")

    def get_rate(self):
        return (
            Log.select().where(Log.model == 'Disk', Log.model_refer == self.id, Log.Type == 'rate', Log.content ** "member % rate +1 for disk %").count(),
            Log.select().where(Log.model == 'Disk', Log.model_refer == self.id, Log.Type == 'rate', Log.content ** "member % rate -1 for disk %").count(),
        )


class RegularFilmShow(CustomBaseModel):
    id = PrimaryKeyField()

    state = CharField(max_length=16)  # Draft, Open, Pending, Passed

    film_1 = ForeignKeyField(Disk, null=True)
    film_2 = ForeignKeyField(Disk, null=True)
    film_3 = ForeignKeyField(Disk, null=True)

    vote_cnt_1 = IntegerField(default=0)
    vote_cnt_2 = IntegerField(default=0)
    vote_cnt_3 = IntegerField(default=0)

    participant_list = SimpleListField(null=True)

    create_log = ForeignKeyField(Log)

    class Meta:
        order_by = ('-id',)

    @classmethod
    def getRecent(cls):
        return cls.select().where(
            RegularFilmShow.state == 'Open'
        ).order_by(RegularFilmShow.created_at.desc()).limit(1)


class PreviewShowTicket(CustomBaseModel):
    id = PrimaryKeyField()
    state = CharField()  # Draft, Open, Closed

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField(null=True)
    desc_ch = TextField(null=True)
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = SimpleListField(null=True)  # actors, simmple list

    cover_url = ForeignKeyField(File)
    length = IntegerField(null=True)
    language = CharField(null=True)
    subtitle = CharField(null=True)
    quantity = TextField(null=True)
    venue = TextField(null=True)

    apply_deadline = DateTimeField()
    show_time = DateTimeField(null=True)
    remarks = TextField(null=True)

    successful_applicant = SimpleListField(null=True)

    create_log = ForeignKeyField(Log)

    class Meta:
        order_by = ('-id',)


class DiskReview(CustomBaseModel):
    id = PrimaryKeyField()

    poster = ForeignKeyField(User)
    disk = ForeignKeyField(Disk, related_name='reviews')

    create_log = ForeignKeyField(Log)
    content = TextField()

    class Meta:
        order_by = ('id',)


class News(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    content = TextField()
    create_log = ForeignKeyField(Log)

    class Meta:
        order_by = ('-id',)


class Document(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File)

    create_log = ForeignKeyField(Log)

    class Meta:
        order_by = ('-id',)


class Publication(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File)
    cover_url = ForeignKeyField(File)

    create_log = ForeignKeyField(Log)
    Type = CharField(max_length=16)  # Magazine, MicroMagazine

    class Meta:
        indexes = (
            (('Type'), False),
        )
        order_by = ('-id',)


class Sponsor(CustomBaseModel):
    id = PrimaryKeyField()

    name = TextField()
    img_url = ForeignKeyField(File)

    x = DecimalField()
    y = DecimalField()
    w = DecimalField()
    h = DecimalField()

    create_log = ForeignKeyField(Log)


class Exco(CustomBaseModel):
    id = PrimaryKeyField()

    name_en = CharField()
    name_ch = CharField()
    position = CharField()
    descript = TextField(null=True)

    img_url = ForeignKeyField(File)
    email = CharField()

    hall_allocate = CharField(max_length=10, null=True)


class SiteSettings(CustomBaseModel):
    key = CharField(max_length=16, unique=True)
    value = CharField()


class OneSentence(CustomBaseModel):
    id = PrimaryKeyField()

    film = TextField()
    content = TextField()

    create_log = ForeignKeyField(Log)


def create_tables():
    File.create_table()
    User.create_table()
    Log.create_table()
    Disk.create_table()
    RegularFilmShow.create_table()
    PreviewShowTicket.create_table()
    DiskReview.create_table()
    News.create_table()
    Document.create_table()
    Sponsor.create_table()
    Exco.create_table()
    SiteSettings.create_table()
    OneSentence.create_table()
