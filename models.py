# Python modules
import functools
import flask_cas

# framework related
from flask import request, abort, url_for, redirect
from peewee import *
from flask_peewee.auth import Auth, BaseUser

# custom related
from app import app, db
from settings import Settings
from helpers import after_this_request


#custom auth model
class CustomAuth(Auth):
    def get_user_model(self):
        return User

    def test_user(self, test_fn):
        def decorator(fn):
            @functools.wraps(fn)
            def inner(*args, **kwargs):
                user = self.get_logged_in_user()

                if not user or not test_fn(user):
                    abort(403)
                return fn(*args, **kwargs)
            return inner
        return decorator

    def login(self):
        if request.method == 'GET':
            next_url = request.args.get('next') or ""
            login_url = 'http://' + Settings.SERVER_NAME + url_for('%s.login' % self.blueprint.name)
            status, username, cookie = flask_cas.login(Settings.AUTH_SERVER, login_url)
            if status == flask_cas.CAS_OK:
                try:
                    #user = User.get(User.itsc == username)
                    #self.login_user(user)
                    # set cookie for cas auth
                    if cookie:
                        @after_this_request
                        def store_cookie(response):
                            print url_for('index')
                            response.set_cookie(flask_cas.FLASK_CAS_NAME, cookie, path=url_for('index'), httponly=True)

                    # redirect to front server
                    return redirect(Settings.FRONT_SERVER + '/#!' + next_url)
                except User.DoesNotExist:
                    pass

            # not authorized
            abort(403)
        else:

            # method not allowed
            abort(405)

    def logout(self):
        self.logout_user(self.get_logged_in_user())
        return redirect(Settings.FRONT_SERVER + '/#!' + request.args.get('next'))


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

    is_draft = BooleanField()

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


class RegularFilmShow(db.Model):
    state = CharField()  # Draft, Closed, Open, Pending, Passed

    film_1 = ForeignKeyField(Disk, related_name='onshow_1', null=True)
