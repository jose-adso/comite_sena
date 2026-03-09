from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)  # Clave secreta segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Importar configuración de base de datos desde models
from models.database import db, bcrypt
from models.usuario import Usuario
from routes.auth import auth_bp

# Inicializar extensiones
db.init_app(app)
bcrypt.init_app(app)

# Registrar Blueprint de rutas
app.register_blueprint(auth_bp)

# Inicializar base de datos y crear usuario admin por defecto
def init_db():
    with app.app_context():
        db.create_all()
        
        # Contraseña hasheada con bcrypt (12 rondas) - jhoset40@
        password_hash = '$2b$12$yadSYSCbrymExAMoHYcVle2T4cCGTwlKixJN/XZnlkcoEsxHKJ9Ku'
        
        # Verificar si ya existe el usuario admin
        admin_existe = Usuario.query.filter_by(username='joserojas').first()
        
        if not admin_existe:
            admin = Usuario(
                username='joserojas',
                password_hash=password_hash,
                rol='admin',
                email='joserojas201890@gmail.com',
                nombre='Admin',
                apellido='Principal',
                telefono='3123678307',
                debe_cambiar_password=False
            )
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin 'joserojas' creado exitosamente")
        else:
            print("El usuario admin 'joserojas' ya existe")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    init_db()
    app.run(debug=False, host='0.0.0.0', port=args.port)
