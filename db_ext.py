from string import split, join

from flask import json
from peewee import TextField

__all__ = [
    'SimpleListField',
    'JSONField',
]


class SimpleListField(TextField):
    """A simulated list field in Database

    It is in fact a long text. ',' perfoms as delimiter.
    """
    def to_str(self, x):
        """Convert a value to string form"""
        if isinstance(x, unicode) or isinstance(x, str):
            return x
        return unicode(x)

    def db_value(self, value):
        """Convert a value to be used to construct SQL"""
        if value is None:
            return ''
        return join(map(self.to_str, value), ',') if isinstance(value, list) else value

    def python_value(self, value):
        """Parse and use in Python"""
        if value is None or len(value.strip()) == 0:
            return []
        return map(lambda x: x.strip(), split(value, ','))


class JSONField(TextField):
    """A simulated JSON field in Database

    It is in fact a long text storing a JSON text.
    """
    def db_value(self, value):
        """Convert a value to be used to construct SQL"""
        return json.dumps(value)

    def python_value(self, value):
        """Parse and use in Python"""
        return json.loads(value)
