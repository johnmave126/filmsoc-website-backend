import datetime

from wtforms.form import Form
from wtforms import fields as f
from wtforms.validators import AnyOf, NumberRange, Regexp, InputRequired, Optional
from wtfpeewee.orm import model_form

from models import *
from db_ext import *
from frame_ext import CustomConverter, InstanceExist

__all__ = [
    'UserForm',
    'DiskForm',
    'RegularFilmShowForm',
    'PreviewShowTicketForm',
    'DiskReviewForm',
    'NewsForm',
    'DocumentForm',
    'PublicationForm',
    'SponsorForm',
    'OneSentenceForm',
    'ExcoForm',
    'SiteSettingsForm',
    'ReserveForm',
    'SubmitUserForm',
    'RateForm',
    'VoteForm',
    'ApplyTicketForm',
    'RelationForm',
]


UserForm = model_form(User, field_args={
    'itsc': dict(validators=[
        InputRequired(message="ITSC required")
    ]),
    'student_id': dict(validators=[
        InputRequired(message="Student ID required"),
        Regexp("^\d{8}$", message="Invalid Student ID")
    ]),
    'university_id': dict(validators=[
        Regexp("^\d{9}$", message="Invalid University ID")
    ]),
    'mobile': dict(validators=[
        Regexp("^\d{8}$", message="Invalid Mobile Phone")
    ]),
    'member_type': dict(validators=[
        InputRequired(message="Member Type required"),
        AnyOf(['Full', 'OneSem', 'OneYear', 'TwoYear', 'ThreeYear', 'Honour', 'Assoc', 'Expired'], message="Invalid Member Type")
    ]),
    'expire_at': dict(validators=[
        InputRequired(message="Expire date required")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count', 'full_name',
), converter=CustomConverter())


DiskForm = model_form(Disk, field_args={
    'disk_type': dict(validators=[
        InputRequired(message="Disk Type missing"),
        AnyOf(['A', 'B'], message="Invalid Disk Type")
    ]),
    'show_year': dict(validators=[
        InputRequired(message="Missing show year"),
        NumberRange(max=datetime.date.today().year, message="Invalid Show Year")
    ]),
    'imdb_url': dict(validators=[
        Regexp('^tt\d{7}$', message="Invalid IMDB Link")
    ]),
    'avail_type': dict(validators=[
        Optional(),
        AnyOf(['Draft', 'Available'], message="Invalid Available Type")
    ]),
    'title_en': dict(validators=[
        InputRequired(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        InputRequired(message="Chinese Title missing")
    ]),
    'category': dict(validators=[
        AnyOf(['I', 'II A', 'II B', 'III'], message="Invalid Category")
    ]),
    'cover_url': dict(validators=[
        Optional(),
        InstanceExist(File, message="Non exist cover")
    ]),
}, exclude=(
    'hold_by', 'reserved_by', 'borrow_cnt', 'rank', 'create_log',
), converter=CustomConverter())


RegularFilmShowForm = model_form(RegularFilmShow, field_args={
    'state': dict(validators=[
        InputRequired(message="Show state Missing"),
        AnyOf(['Draft', 'Open', 'Pending', 'Passed'], message="Invalid Show State")
    ]),
    'film_1': dict(validators=[
        InstanceExist(Disk, message="Non exist Film #1")
    ]),
    'film_2': dict(validators=[
        Optional(),
        InstanceExist(Disk, message="Non exist Film #2")
    ]),
    'film_3': dict(validators=[
        Optional(),
        InstanceExist(Disk, message="Non exist Film #3")
    ]),
}, exclude=(
    'participant_list', 'create_log', 'vote_cnt_1', 'vote_cnt_2', 'vote_cnt_3',
), converter=CustomConverter())


PreviewShowTicketForm = model_form(PreviewShowTicket, field_args={
    'state': dict(validators=[
        InputRequired(message="Ticket state Missing"),
        AnyOf(['Draft', 'Open', 'Closed'], message="Invalid Ticket State")
    ]),
    'title_en': dict(validators=[
        InputRequired(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        InputRequired(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        InputRequired(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        InputRequired(message="Chinese Title missing")
    ]),
    'apply_deadline': dict(validators=[
        InputRequired(message="Apply Deadline missing")
    ]),
    'cover_url': dict(validators=[
        Optional(),
        InstanceExist(File, message="Non exist cover")
    ]),
}, exclude=(
    'create_log',
), converter=CustomConverter())


DiskReviewForm = model_form(DiskReview, field_args={
    'disk': dict(validators=[
        InputRequired(message="The disk to review missing"),
        InstanceExist(Disk, message="Non exist Disk")
    ]),
    'content': dict(validators=[
        InputRequired(message="Content cannot be null")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count'
), converter=CustomConverter())


NewsForm = model_form(News, field_args={
    'title': dict(validators=[
        InputRequired(message="Title Missing")
    ]),
    'content': dict(validators=[
        InputRequired(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


DocumentForm = model_form(Document, field_args={
    'title': dict(validators=[
        InputRequired(message="Title Missing")
    ]),
    'doc_url': dict(validators=[
        InputRequired(message="File Missing"),
        InstanceExist(File, message="File not exist")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


PublicationForm = model_form(Publication, field_args={
    'title': dict(validators=[
        InputRequired(message="Title Missing")
    ]),
    'Type': dict(validators=[
        InputRequired(message="Type Missing"),
        AnyOf(['Magazine', 'MicroMagazine', 'Podcast'], "Invalid Type")
    ]),
    'doc_url': dict(validators=[
        InstanceExist(File, message="File not exist")
    ]),
    'cover_url': dict(validators=[
        InputRequired(message="Cover image Missing"),
        InstanceExist(File, message="Cover not exist")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


SponsorForm = model_form(Sponsor, field_args={
    'name': dict(validators=[
        InputRequired(message="Name Missing")
    ]),
    'img_url': dict(validators=[
        InputRequired(message="Image Missing"),
        InstanceExist(File, message="Image not exist")
    ]),
    'x': dict(validators=[
        InputRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'y': dict(validators=[
        InputRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'w': dict(validators=[
        InputRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'h': dict(validators=[
        InputRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


ExcoForm = model_form(Exco, field_args={
    'hall_allocate': dict(validators=[
        Regexp('^[\d*]*$', message="Invalid hall number")
    ]),
    'img_url': dict(validators=[
        InputRequired(message="Image Missing"),
        InstanceExist(File, message="Image not exist")
    ]),
}, converter=CustomConverter())


SiteSettingsForm = model_form(SiteSettings, field_args={
    'value': dict(validators=[
        InputRequired(message="Missing value")
    ])
}, exclude=(
    'key',
), converter=CustomConverter())


OneSentenceForm = model_form(OneSentence, field_args={
    'film': dict(validators=[
        InputRequired(message="Origin Film Missing")
    ]),
    'content': dict(validators=[
        InputRequired(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


# extra forms
class ReserveForm(Form):
    form = f.TextField(u'form', [
        InputRequired(message="Reserve type missing"),
        AnyOf(['Hall', 'Counter'], message="Unsupported reserve type")
    ])
    hall = f.IntegerField(u'hall', [
        Optional(),
        NumberRange(min=1, max=9, message="Hall must be 1-9")
    ])
    room = f.TextField(u'room', [
        Optional(),
        Regexp('^\d{3}[ULRulr]?$', message="Invalid room number")
    ])
    remarks = f.TextField(u'remarks', [
        Optional()
    ])


class SubmitUserForm(Form):
    id = f.IntegerField(u'id', [
        InputRequired(message="User missing"),
        InstanceExist(User, message="User not exist")
    ])


class RateForm(Form):
    rate = f.TextField(u'rate', [
        InputRequired(message="Rate missing"),
        AnyOf(['up', 'down'], message="Invalid rate")
    ])


class VoteForm(Form):
    film_id = f.IntegerField(u'rfs_id', [
        InputRequired(message="The film to vote missing"),
        AnyOf([1, 2, 3], message="Invalid Choice")
    ])


class ApplyTicketForm(Form):
    number = f.IntegerField(u'number', [
        InputRequired(message="Number of ticket missing"),
        AnyOf([1, 2], message="Invalid choice of number")
    ])


class RelationForm(Form):
    student_id = f.TextField(u'student_id', [
        InputRequired(message="Student ID required"),
        Regexp("^\d{8}$", message="Invalid Student ID")
    ])
    university_id = f.TextField(u'student_id', [
        InputRequired(message="University ID required"),
        Regexp("^\d{9}$", message="Invalid University ID")
    ])
