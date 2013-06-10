#framework
from flask import Flask, url_for

#database
from flask_peewee.db import Database

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


def create_tables():
    pass


@app.route('/')
def only_test():
    print url_for('login')
