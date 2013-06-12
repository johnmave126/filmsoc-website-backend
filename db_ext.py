from flask.json import dumps, loads
from peewee import TextField
from string import split, join


class SimpleListField(TextField):
    db_field = 'simplelist'

    def db_value(self, value):
        return join(value, ',')

    def python_value(self, value):
        return split(value, ',')


class JSONField(TextField):
    db_filed = 'json'

    def db_value(self, value):
        return dumps(value)

    def python_value(self, value):
        return loads(value)
