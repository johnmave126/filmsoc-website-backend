import datetime

from wtforms.form import Form
from wtforms import fields as f
from wtforms.validators import AnyOf, NumberRange, Regexp, Required, Optional
from wtfpeewee.orm import model_form

from models import *
from db_ext import *
from frame_ext import CustomConverter

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
    'ReserveForm',
    'BorrowForm',
]


UserForm = model_form(User, field_args={
    'itsc': dict(validators=[
        Required(message="ITSC required")
    ]),
    'student_id': dict(validators=[
        Required(message="Student ID required"),
        Regexp("\d{8}", message="Invalid Student ID")
    ]),
    'university_id': dict(validators=[
        Regexp("\d{9}", message="Invalid University ID")
    ]),
    'mobile': dict(validators=[
        Regexp("\d{8}", message="Invalid Mobile Phone")
    ]),
    'member_type': dict(validators=[
        Required(message="Member Type required"),
        AnyOf(['Full', 'OneSem', 'OneYear', 'TwoYear', 'ThreeYear', 'Honor', 'Assoc'], message="Invalid Member Type")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count', 'full_name',
), converter=CustomConverter())


DiskForm = model_form(Disk, field_args={
    'disk_type': dict(validators=[
        Required(message="Disk Type missing"),
        AnyOf(['A', 'B'], message="Invalid Disk Type")
    ]),
    'show_year': dict(validators=[
        NumberRange(max=datetime.date.today().year, message="Invalid Show Year")
    ]),
    'imdb_url': dict(validators=[
        Regexp('tt\d{7}', message="Invalid IMDB Link")
    ]),
    'avail_type': dict(validators=[
        AnyOf(['Draft', 'Available'], message="Invalid Available Type")
    ]),
    'title_en': dict(validators=[
        Required(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        Required(message="Chinese Title missing")
    ]),
    'category': dict(validators=[
        AnyOf(['I', 'II A', 'II B', 'III'], message="Invalid Category")
    ])
}, exclude=(
    'hold_by', 'reserved_by', 'borrow_cnt', 'rank', 'create_log',
), converter=CustomConverter())


RegularFilmShowForm = model_form(RegularFilmShow, field_args={
    'state': dict(validators=[
        Required(message="Show state Missing"),
        AnyOf(['Draft', 'Closed', 'Open', 'Pending', 'Passed'], message="Invalid Show State")
    ])
}, exclude=(
    'participant_list', 'create_log', 'vote_cnt_1', 'vote_cnt_2', 'vote_cnt_3',
), converter=CustomConverter())


PreviewShowTicketForm = model_form(PreviewShowTicket, field_args={
    'state': dict(validators=[
        Required(message="Ticket state Missing"),
        AnyOf(['Draft', 'Open', 'Closed'], message="Invalid Ticket State")
    ]),
    'title_en': dict(validators=[
        Required(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        Required(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        Required(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        Required(message="Chinese Title missing")
    ]),
    'apply_deadline': dict(validators=[
        Required(message="Apply Deadline missing")
    ])
}, exclude=(
    'applicant', 'create_log',
), converter=CustomConverter())


DiskReviewForm = model_form(DiskReview, field_args={
    'content': dict(validators=[
        Required(message="Content cannot be null")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count'
), converter=CustomConverter())


NewsForm = model_form(News, field_args={
    'title': dict(validators=[
        Required(message="Title Missing")
    ]),
    'content': dict(validators=[
        Required(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


DocumentForm = model_form(Document, field_args={
    'title': dict(validators=[
        Required(message="Title Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


PublicationForm = model_form(Publication, field_args={
    'title': dict(validators=[
        Required(message="Title Missing")
    ]),
    'Type': dict(validators=[
        Required(message="Type Missing"),
        AnyOf(['Magazine', 'MicroMagazine'], "Invalid Type")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


SponsorForm = model_form(Sponsor, field_args={
    'name': dict(validators=[
        Required(message="Name Missing")
    ]),
    'x': dict(validators=[
        Required(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'y': dict(validators=[
        Required(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'w': dict(validators=[
        Required(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'h': dict(validators=[
        Required(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


OneSentenceForm = model_form(OneSentence, field_args={
    'film': dict(validators=[
        Required(message="Origin Film Missing")
    ]),
    'content': dict(validators=[
        Required(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


ExcoForm = model_form(Exco, field_args={
    'hall_allocate': dict(validators=[
        NumberRange(min=1, max=9, message="Hall must be 1-9")
    ])
}, converter=CustomConverter())


# extra forms
class ReserveForm(Form):
    form = f.TextField(u'form', [
        Required(message="Reserve type missing"),
        AnyOf(['Hall', 'Counter'], message="Unsupported reserve type")
    ])
    hall = f.IntegerField(u'hall', [
        Optional(),
        NumberRange(min=1, max=9, message="Hall must be 1-9")
    ])
    room = f.TextField(u'room', [
        Optional(),
        Regexp('\d{3}[ULRulr]{0,1}', message="Invalid room number")
    ])
    remarks = f.TextField(u'remarks', [
        Optional()
    ])


class BorrowForm(Form):
    user_id = f.HiddenField(u'user_id', [
        Required(message="User missing"),
    ])
