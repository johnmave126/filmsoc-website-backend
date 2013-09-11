from app import app, db

from auth import *
from models import *
from api import api
import static_host


# setup urls
api.setup()

if __name__ == '__main__':
    app.run()
