#settings for flask


class Settings(object):
    DATABASE = {
        'name': 'example.db',
        'engine': 'peewee.SqliteDatabase',
    }
    DEBUG = True
    SECRET_KEY = 'ssshhhh'
    AUTH_SERVER = 'https://cas.ust.hk'
    FRONT_SERVER = 'http://ihome.ust.hk/~su_film'
