from app import app
from flask import g, render_template, request, Response, abort
from functools import wraps
import socket

def limit_source(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.remote_addr != socket.gethostbyname(app.config["FRONT_SERVER_HOST"]):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/static/')
@app.route('/static/home/')
def static_home():
    return "Home"

