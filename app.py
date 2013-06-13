#framework
from flask import Flask, url_for

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


@app.route('/')
def index():
    return "url_for('login')"
