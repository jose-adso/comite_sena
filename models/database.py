from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

def init_db(app):
    """Inicializa la base de datos con la aplicación Flask"""
    db.init_app(app)
    bcrypt.init_app(app)
