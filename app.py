#framework
from flask import Flask, url_for, redirect

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


@app.after_request
def cros_headers(response):
    h = response.headers
    h['Access-Control-Allow-Origin'] = 'http://ihome.ust.hk'
    h['Access-Control-Allow-Methods'] = h['Allow']
    h['Access-Control-Allow-Headers'] = 'origin, content-type, accept, x-requested-with'
    return response


@app.route('/')
def index():
    return redirect(app.config['FRONT_SERVER'])
