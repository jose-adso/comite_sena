from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)  # Clave secreta segura
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///usuarios.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SMTP_EMAIL'] = os.getenv('SMTP_EMAIL', '')
app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD', '')
app.config['SMTP_SERVER'] = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', '587'))

# Importar configuración de base de datos desde models
from models.database import db, bcrypt
from models.usuario import Usuario
from models.falla import Falla
from models.reclamo import Reclamo
from routes import auth_bp

# Inicializar extensiones
db.init_app(app)
bcrypt.init_app(app)

# Registrar Blueprint de rutas
app.register_blueprint(auth_bp)

# Inicializar base de datos
def init_db():
    with app.app_context():
        db.create_all()
        
        # Crear usuario admin si no existe
        admin_username = 'joserojas'
        admin_email = 'jhoset40@gmail.com'
        admin_password_hash = os.getenv('ADMIN_PASSWORD_HASH')
        
        if not admin_password_hash:
            print("❌ Error: ADMIN_PASSWORD_HASH no está definido en .env")
            return
        
        admin_user = Usuario.query.filter_by(username=admin_username).first()
        if not admin_user:
            admin_user = Usuario(
                username=admin_username,
                password_hash=admin_password_hash,
                nombre='Jose Rojas',
                email=admin_email,
                rol='admin',
                debe_cambiar_password=False,
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Usuario admin 'joserojas' creado.")
        elif admin_user.email != admin_email:
            admin_user.email = admin_email
            db.session.commit()
            print("✅ Email del admin actualizado.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    init_db()
    app.run(debug=True, host='0.0.0.0', port=args.port)
