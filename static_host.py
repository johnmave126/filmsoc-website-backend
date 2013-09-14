from app import app
from flask import Blueprint, g, render_template, request, Response, abort
from functools import wraps
import socket

def limit_source(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.remote_addr != socket.gethostbyname(app.config["FRONT_SERVER_HOST"]):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

static_host = Blueprint('static_host', __name__, template_folder='static_templates')


@static_host.route('/')
@static_host.route('/home/')
@limit_source
def static_home():
    return "Home"


@static_host.route('/news/<news_id>/')
@limit_source
def static_news(news_id):
    return news_id


@app.route('/news/<news_id>/')
def static_news(news_id):
    return news_id