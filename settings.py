#settings for flask


class Settings(object):
    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }
    DEBUG = True
    SECRET_KEY = 'ssshhhh'
