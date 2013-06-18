import datetime

from wtforms.validators import AnyOf, NumberRange, Regexp, DataRequired
from wtfpeewee.orm import model_form

from models import *
from db_ext import *
from frame_ext import CustomConverter


UserForm = model_form(User, field_args={
    'itsc': dict(validators=[
        DataRequired(message="ITSC required")
    ]),
    'student_id': dict(validators=[
        DataRequired(message="Student ID required"),
        Regexp("\d{8}", message="Invalid Student ID")
    ]),
    'university_id': dict(validators=[
        Regexp("\d{9}", message="Invalid University ID")
    ]),
    'mobile': dict(validators=[
        Regexp("\d{8}", message="Invalid Mobile Phone")
    ]),
    'member_type': dict(validators=[
        DataRequired(message="Member Type required"),
        AnyOf(['Full', 'OneSem', 'OneYear', 'TwoYear', 'ThreeYear', 'Honor', 'Assoc'], message="Invalid Member Type")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count',
), converter=CustomConverter())


DiskForm = model_form(Disk, field_args={
    'disk_type': dict(validators=[
        DataRequired(message="Disk Type missing"),
        AnyOf(['A', 'B'], message="Invalid Disk Type")
    ]),
    'show_year': dict(validators=[
        NumberRange(max=datetime.datetime.now().year, message="Invalid Show Year")
    ]),
    'imdb_url': dict(validators=[
        Regexp('tt\d{7}', message="Invalid IMDB Link")
    ]),
    'avail_type': dict(validators=[
        AnyOf(['Draft', 'Available'], message="Invalid Available Type")
    ]),
    'title_en': dict(validators=[
        DataRequired(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        DataRequired(message="Chinese Title missing")
    ])
}, exclude=(
    'hold_by', 'reserved_by', 'borrow_cnt', 'rank', 'create_log',
), converter=CustomConverter())


RegularFilmShowForm = model_form(RegularFilmShow, field_args={
    'state': dict(validators=[
        DataRequired(message="Show state Missing"),
        AnyOf(['Draft', 'Closed', 'Open', 'Pending', 'Passed'], message="Invalid Show State")
    ])
}, exclude=(
    'participant_list', 'create_log', 'vote_cnt_1', 'vote_cnt_2', 'vote_cnt_3',
), converter=CustomConverter())


PreviewShowTicketForm = model_form(PreviewShowTicket, field_args={
    'state': dict(validators=[
        DataRequired(message="Ticket state Missing"),
        AnyOf(['Draft', 'Open', 'Closed'], message="Invalid Ticket State")
    ]),
    'title_en': dict(validators=[
        DataRequired(message="English Title missing")
    ]),
    'title_ch': dict(validators=[
        DataRequired(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        DataRequired(message="Chinese Title missing")
    ]),
    'title_ch': dict(validators=[
        DataRequired(message="Chinese Title missing")
    ]),
    'apply_deadline': dict(validators=[
        DataRequired(message="Apply Deadline missing")
    ])
}, exclude=(
    'applicant', 'create_log',
), converter=CustomConverter())


DiskReviewForm = model_form(DiskReview, field_args={
    'content': dict(validators=[
        DataRequired(message="Content cannot be null")
    ])
}, exclude=(
    'last_login', 'this_login', 'login_count', 'rfs_count'
), converter=CustomConverter())


NewsForm = model_form(News, field_args={
    'title': dict(validators=[
        DataRequired(message="Title Missing")
    ]),
    'content': dict(validators=[
        DataRequired(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


DocumentForm = model_form(Document, field_args={
    'title': dict(validators=[
        DataRequired(message="Title Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


PublicationForm = model_form(Publication, field_args={
    'title': dict(validators=[
        DataRequired(message="Title Missing")
    ]),
    'Type': dict(validators=[
        DataRequired(message="Type Missing"),
        AnyOf(['Magazine', 'MicroMagazine'], "Invalid Type")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


SponsorForm = model_form(Sponsor, field_args={
    'name': dict(validators=[
        DataRequired(message="Name Missing")
    ]),
    'x': dict(validators=[
        DataRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'y': dict(validators=[
        DataRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'w': dict(validators=[
        DataRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ]),
    'h': dict(validators=[
        DataRequired(message="Location Missing"),
        NumberRange(min=0, max=100, message="Out of Range")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


OneSentenceForm = model_form(OneSentence, field_args={
    'film': dict(validators=[
        DataRequired(message="Origin Film Missing")
    ]),
    'content': dict(validators=[
        DataRequired(message="Content Missing")
    ])
}, exclude=(
    'create_log',
), converter=CustomConverter())


ExcoForm = model_form(Exco, field_args={
    'hall_allocate': dict(validators=[
        IntegerField(min=1, max=9, message="Hall must be 1-9")
    ])
}, converter=CustomConverter())
