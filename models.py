
#framework related
from flask_peewee.auth import Auth, BaseUser
from peewee import *

from filmsoc import db


#custom auth model
class CustomAuth(Auth):
    def login(self):
        error = None

        if request.method == 'POST':
            pass


# user model
class User(db.Model, BaseUser):
    itsc = CharField(unique=True, primary_key=True)
    student_id = CharField(max_length=8, unique=True)  # max length is 8
    university_id = CharField(max_length=9, null=True, unique=True)
    mobile = CharField(max_length=8, null=True)
    full_name = CharField()

    member_type = CharField()
    join_at = DateField()
    expire_at = DateField()
    expired = BooleanField()
    pennalized = BooleanField()

    last_login = DateTimeField()
    login_count = IntegerField()

    rfs_count = IntegerField()  # for regular film show

    admin = BooleanField()

    def __unicode__(self):
        return self.full_name

    def dvd_borrowed(self):
        return self.borrowed

    def dvd_borrow_count(self):
        return self.borrowed.count()

    def dvd_reserved(self):
        return self.reserved

    def dvd_reserved_count(self):
        return self.reserved.count()

    def rfs_vote(self):
        active_rfs = RegularFilmShow.getRecent()
        return Log.select().where(
            Log.model == 'RegularFilmShow',
            Log.type == 'vote',
            Log.model_refer == active_rfs,
            Log.user_affected == self
        )

    def rfs_vote_count(self):
        active_rfs = RegularFilmShow.getRecent()
        return Log.select().where(
            Log.model == 'RegularFilmShow',
            Log.type == 'vote',
            Log.model_refer == active_rfs,
            Log.user_affected == self
        ).count()


class Disk(db.Model):
    diskID = PrimaryKeyField(primary_key=True)
    diskType = CharField(max_length=1)  # A for VCD, B for DVD, maybe C for Blueray

    title_en = TextField()
    title_ch = TextField()
    desc_en = TextField()
    desc_ch = TextField()
    director_en = TextField(null=True)
    director_ch = TextField(null=True)
    actors = TextField(null=True)  # actors, json

    show_year = IntegerField()
    cover_url = CharField()
    tags = TextField()  # tags, json
    imdb_url = CharField(null=True)
    length = IntegerField(null=True)

    hold_by = ForeignKeyField(User, related_name='borrowed', null=True)
    reserved_by = ForeignKeyField(User, related_name='reserved', null=True)
    avail_type = CharField()  # Available, Borrowed, Reserved, Voting

    def callNumber(self):
        return self.diskType + str(self.diskID)

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
