import math
import socket
from markupsafe import Markup, escape

from flask import Blueprint, g, render_template, request, Response, abort
from peewee import *

from app import app
from models import *
from bbcode import BBCode

__all__ = ['static_host']

static_host = Blueprint('static_host',
                        __name__, template_folder='static_templates')


@static_host.app_template_filter('file_location')
def file_location(file_):
    return "http://ihome.ust.hk/~su_film/asset/upload/%s" % file_.url

@static_host.app_template_filter('todate')
def todatestring(data, format=""):
    return data.strftime(format)

@static_host.app_template_filter('bbcode')
def tobbcode(data):
    return BBCode().parse(data)

@static_host.app_template_filter('wrap')
def towrap(data):
    return (Markup('<p>') + escape(data).replace('\n', Markup('</p><p>')) +
            Markup('</p>'))


@static_host.before_request
def limit_source():
    if request.remote_addr != socket.gethostbyname(
            app.config["FRONT_SERVER_HOST"]):
        abort(403)


@static_host.errorhandler(404)
def static_404():
    return render_template("error_page.html",
                            error_title="404 Page Not Found",
                            error_text="Oops... 404 Page Not Found.")


@static_host.route('/')
@static_host.route('/home/')
def static_home():
    cover_id = int(SiteSettings.get('header_image'))
    cover_url = file_location(
        File.select().where(File.id == cover_id).get())
    news_sq = News.select().limit(15)
    return render_template("home.html",
                            cover_url=cover_url, news_sq = news_sq)


@static_host.route('/news/<int:news_id>/')
def static_news(news_id):
    try:
        news = News.select().where(News.id == news_id).get()
    except DoesNotExist:
        abort(404)

    return render_template("news.html", news=news)

@static_host.route('/show/')
def static_show():
    show = RegularFilmShow.get_recent()
    return render_template("rfs.html", show=show, getattr=getattr)

@static_host.route('/library/')
def static_library():
    page = int(request.args.get("page", "1"))
    mode = request.args.get("mode", "")

    disk_sq = Disk.select()
    if mode == "popular":
        disk_sq = disk_sq.order_by(Disk.borrow_cnt.desc())
        title = "Top Popular"
    elif mode == "rank":
        disk_sq = disk_sq.order_by(Disk.rank.desc())
        title = "Top Ranked"
    else:
        disk_sq = disk_sq.order_by(Disk.id.desc())
        title = "VCD/DVD Library"

    disk_sq = disk_sq.paginate(page, 6)
    total_page = int(math.ceil(float(disk_sq.count()) / 6))

    prev_component = ["page=%d" % (page - 1)] if page > 1 else []
    if mode in ["popular", "rank"]:
        prev_component.append("mode=%s" % mode)
    prev_url = ('#!library/?' +
                '&'.join(prev_component)).rstrip('?')

    next_component = ["page=%d" % (page + 1)] if page < total_page else []
    if mode in ["popular", "rank"]:
        next_component.append("mode=%s" % mode)
    next_url = ('#!library/?' +
                '&'.join(next_component)).rstrip('?')

    return render_template("library_list.html",
                            disk_sq=disk_sq, title=title,
                            prev_url=prev_url, next_url=next_url,
                            page=page, total=total_page)

@static_host.route('/library/<int:disk_id>/')
def static_disk(disk_id):
    try:
        disk = Disk.select().where(Disk.id == disk_id).get()
    except DoesNotExist:
        abort(404)

    ups, downs = disk.get_rate()
    reviews = disk.reviews.limit(20)

    return render_template("library_disk.html", 
                            disk=disk, ups=ups, downs=downs,
                            reviews=reviews)


@static_host.route('/ticket/')
def static_tickets():
    ticket_sq = PreviewShowTicket.select().limit(20)
    display_ticket = ticket_sq.get()

    return render_template("ticket.html",
                            ticket_sq=ticket_sq, display_ticket=display_ticket)


@static_host.route('/document/')
def static_document():
    doc_sq = Document.select()
    display_doc = doc_sq.get()

    return render_template("document.html",
                            doc_sq=doc_sq, display_doc=display_doc)

# register Blueprint
app.register_blueprint(static_host, url_prefix='/static')