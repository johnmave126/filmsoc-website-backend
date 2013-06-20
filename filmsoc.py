from repoze.profile.profiler import AccumulatingProfileMiddleware
from app import app, db

from auth import *
from models import *
from api import api


# setup urls
api.setup()

if __name__ == '__main__':
    wsgi_app = app.wsgi_app
    wrapped = AccumulatingProfileMiddleware(
        wsgi_app,
        log_filename='wsgi.prof',
        discard_first_request=True,
        flush_at_shutdown=True,
        path='/__profile__'
        )
    app.wsgi_app = wrapped
    #serve(app)
    app.run(host='0.0.0.0', port=5950, debug=True)
