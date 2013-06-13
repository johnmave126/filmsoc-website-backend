from flask import json
from peewee import TextField
from string import split, join


class SimpleListField(TextField):
    def db_value(self, value):
        return join(value, ',')

    def python_value(self, value):
        return split(value, ',')


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)
