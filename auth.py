from app import app, db
from frame_ext import CustomAuth
from models import User

auth = CustomAuth(app, db, user_model=User, prefix='/member')
