# Python modules
import datetime

# framework related
from peewee import *

# custom related
from frame_ext import CustomBaseModel
from db_ext import JSONField, SimpleListField


class File(CustomBaseModel):
    id = PrimaryKeyField()

    name = CharField()
    url = CharField()


# user model
class User(CustomBaseModel):
    id = PrimaryKeyField()

    itsc = CharField(unique=True)
    student_id = CharField(max_length=8, unique=True)  # max length is 8
    university_id = CharField(max_length=9, null=True, unique=True)
    mobile = CharField(max_length=8, null=True)
    full_name = CharField()

    member_type = CharField()  # Full, OneSem, OneYear, TwoYear, ThreeYear, Honor, Assoc
    join_at = DateField(default=datetime.datetime.now)
    expire_at = DateField()
    expired = BooleanField(default=False)
    pennalized = BooleanField(default=False)

    last_login = DateTimeField(null=True, default=None)
    this_login = DateTimeField(null=True, default=None)
    login_count = IntegerField(default=0)

    rfs_count = IntegerField(default=0)  # for regular film show

    admin = BooleanField(default=False)

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

    model = CharField()
    Type = CharField()
    model_refer = IntegerField()
    user_affected = ForeignKeyField(User)
    admin_involved = ForeignKeyField(User)
    content = TextField(null=True)

    created_at = DateTimeField(default=datetime.datetime.now)


class Disk(CustomBaseModel):
    id = PrimaryKeyField(primary_key=True)
    disk_type = CharField(max_length=1)  # A for VCD, B for DVD, maybe C for Blueray

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField(null=True)
    desc_ch = TextField(null=True)
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = SimpleListField(null=True)  # actors, simmple list

    show_year = IntegerField()
    cover_url = ForeignKeyField(File)
    tags = SimpleListField(null=True)  # tags, json
    imdb_url = CharField(null=True)
    length = IntegerField(null=True)

    hold_by = ForeignKeyField(User, related_name='borrowed', null=True)
    reserved_by = ForeignKeyField(User, related_name='reserved', null=True)
    avail_type = CharField()  # Draft, Available, Borrowed, Reserved, Voting

    borrow_cnt = IntegerField(default=0)
    rank = DecimalField(default=0)

    create_log = ForeignKeyField(Log)

    def callNumber(self):
        return self.disk_type + str(self.id)

    def check_out(self, user):
        if self.avail_type == "Borrowed":
            return (False, "The disk has been borrowed")
        if self.avail_type == "Voting":
            return (False, "The disk is on voting")

        if self.reserved_by is not None:
            self.reserved_by = None

        self.avail_type = "Borrowed"
        self.hold_by = user

        # save the change
        self.save()

    def check_in(self):
        if self.avail_type != "Borrowed":
            return (False, "The disk is not borrowed")

        self.avail_type = "Available"
        self.hold_by = None

        # save the change
        self.save()


class RegularFilmShow(CustomBaseModel):
    id = PrimaryKeyField()

    state = CharField()  # Draft, Closed, Open, Pending, Passed

    film_1 = ForeignKeyField(Disk, null=True)
    film_2 = ForeignKeyField(Disk, null=True)
    film_3 = ForeignKeyField(Disk, null=True)

    vote_cnt_1 = IntegerField(default=0)
    vote_cnt_2 = IntegerField(default=0)
    vote_cnt_3 = IntegerField(default=0)

    participant_list = SimpleListField(null=True)

    create_log = ForeignKeyField(Log)

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

    applicant = SimpleListField(null=True)
    successful_applicant = SimpleListField(null=True)

    create_log = ForeignKeyField(Log)


class DiskReview(CustomBaseModel):
    id = PrimaryKeyField()

    poster = ForeignKeyField(User)
    disk = ForeignKeyField(Disk, related_name='reviews')

    create_log = ForeignKeyField(Log)
    content = TextField()


class News(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    content = TextField()
    create_log = ForeignKeyField(Log)


class Document(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File)

    create_log = ForeignKeyField(Log)


class Publication(CustomBaseModel):
    id = PrimaryKeyField()

    title = TextField()
    doc_url = ForeignKeyField(File)
    cover_url = ForeignKeyField(File)

    create_log = ForeignKeyField(Log)
    Type = CharField()  # Magazine, MicroMagazine


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
    desc = TextField(null=True)

    img_url = ForeignKeyField(File)
    email = CharField()

    hall_allocate = IntegerField(null=True)


class SiteSettings(CustomBaseModel):
    key = CharField()
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
