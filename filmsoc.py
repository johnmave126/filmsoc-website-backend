from app import app, db

from auth import *
from models import *
from api import api


# setup urls
api.setup()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5950, debug=True)
