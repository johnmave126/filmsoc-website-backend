from app import app, db
from models import *

auth = CustomAuth(app, db, user_model=User, prefix='/member')
