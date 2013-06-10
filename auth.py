from app import app, db
from models import CustomAuth, User

auth = CustomAuth(app, db, User, '/member')
