from app import app, db

from helpers import *
from auth import *
from models import *

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5950, debug=True)
