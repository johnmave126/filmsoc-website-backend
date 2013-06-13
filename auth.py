from app import app, db
from models import CustomAuth, User

auth = CustomAuth(app, db, user_model=User, prefix='/member')
