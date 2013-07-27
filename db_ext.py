from flask import json
from peewee import TextField
from string import split, join

__all__ = [
    'SimpleListField',
    'JSONField',
]


class SimpleListField(TextField):
    def db_value(self, value):
        if value is None:
            return ''
        return join(value, ',') if isinstance(value, list) else value

    def python_value(self, value):
        if value is None:
            return []
        return map(lambda x: x.strip(), split(value, ','))


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)
