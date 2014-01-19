from app import app, db
from frame_ext import CASAuth
from models import User

auth = CASAuth(app, db, user_model=User, prefix='/member')
