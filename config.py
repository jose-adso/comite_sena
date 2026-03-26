from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)  # Clave secreta segura
database_url = os.getenv('DATABASE_URL')
if not database_url:
	db_host = os.getenv('DB_HOST', '75.119.147.138')
	db_port = os.getenv('DB_PORT', '5430')
	db_name = os.getenv('DB_NAME', 'postgres')
	db_user = os.getenv('DB_USER', 'postgres')
	db_password = os.getenv('DB_PASSWORD', 'H3U15P0LeCr0vTwsCoZNyaG1PLCR9FtMfbQFyaE9ea6VbvbkUtAfWeacxYjfPUTl')
	database_url = f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Importar db y bcrypt desde models.database
from models.database import db, bcrypt

# Inicializar extensiones con la aplicación
db.init_app(app)
bcrypt.init_app(app)
