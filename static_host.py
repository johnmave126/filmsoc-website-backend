import socket
from markupsafe import Markup

from flask import Blueprint, g, render_template, request, Response, abort
from peewee import *

from app import app
from models import *
from bbcode import BBCode

__all__ = ['static_host']

static_host = Blueprint('static_host',
                        __name__, template_folder='static_templates')


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
    return (Markup('<p>') + data.replace('\n', Markup('</p><p>')) +
            Markup('</p>'))


@static_host.before_request
def limit_source():
    if request.remote_addr != socket.gethostbyname(
            app.config["FRONT_SERVER_HOST"]):
        abort(403)


@static_host.route('/404')
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


@static_host.route('/news/<news_id>/')
def static_news(news_id):
    try:
        news = News.select().where(News.id == news_id).get()
    except DoesNotExist:
        abort(404)

    return render_template("news.html", news=news)


# register Blueprint
app.register_blueprint(static_host, url_prefix='/static')