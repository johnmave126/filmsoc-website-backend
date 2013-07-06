#framework
from flask import Flask, url_for, redirect
import logging

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)

file_handler = logging.FileHandler(filename='/var/log/apache2/film.log')
file_handler.setLevel(logging.WARNING)
app.logger.addHandler(file_handler)


@app.route('/')
def index():
    return redirect(app.config['FRONT_SERVER'])
