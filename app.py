#framework
from flask import Flask, url_for, redirect

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


@app.route('/')
def index():
    return redirect(app.config['FRONT_SERVER'])
