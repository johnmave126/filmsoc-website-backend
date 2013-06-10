#framework
from flask import Flask

#database
from flask_peewee.db import Database

#app and database
app = Flask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


def create_tables():
    pass

if __name__ == '__main__':
    app.run()
