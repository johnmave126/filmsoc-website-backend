#framework
from flask import Flask, url_for, redirect

#database
from flask_peewee.db import Database
from db_ext import JSONField, SimpleListField


class cFlask(Flask):
    def make_default_options_response(self):
        rv = super(cFlask, self).make_default_options_response()
        h = rv.headers
        h['Access-Control-Allow-Origin'] = 'http://ihome.ust.hk'
        h['Access-Control-Allow-Methods'] = str(rv.allow)
        self.logger.notice(str(rv.allow))
        return rv

#app and database
app = cFlask(__name__)
app.config.from_object('settings.Settings')

db = Database(app)


@app.route('/')
def index():
    return redirect(app.config['FRONT_SERVER'])
