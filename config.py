from flask import Flask
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)  # Clave secreta segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Importar db y bcrypt desde models.database
from models.database import db, bcrypt

# Inicializar extensiones con la aplicación
db.init_app(app)
bcrypt.init_app(app)
