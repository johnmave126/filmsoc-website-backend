#framework
from flask import Flask, redirect

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)

if not app.debug:
    # Set up debug logging after production
    import logging
    from logging import Formatter
    file_handler = logging.FileHandler(filename='/tmp/film.log')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(file_handler)


@app.route('/')
def index():
    return redirect(app.config['FRONT_SERVER'])
