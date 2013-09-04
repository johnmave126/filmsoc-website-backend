from flask import json
from peewee import TextField
from string import split, join

__all__ = [
    'SimpleListField',
    'JSONField',
]


class SimpleListField(TextField):
    def to_str(self, x):
        if isinstance(x, unicode) or isinstance(x, str):
            return x
        return unicode(x)

    def db_value(self, value):
        if value is None:
            return ''
        return join(map(self.to_str, value), ',') if isinstance(value, list) else value

    def python_value(self, value):
        if value is None or len(value.strip()) == 0:
            return []
        return map(lambda x: x.strip(), split(value, ','))


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)
