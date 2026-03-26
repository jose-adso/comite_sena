from config import app, db, bcrypt
from models.usuario import Usuario
from models.falla import Falla
from models.reclamo import Reclamo
from routes import auth_bp
import os
import secrets

# Registrar Blueprint de rutas
app.register_blueprint(auth_bp)

# Inicializar base de datos
def init_db():
    with app.app_context():
        db.create_all()
        
        # Crear usuario admin si no existe
        admin_username = 'joserojas'
        admin_email = 'jhoset40@gmail.com'
        
        # Solo crear el usuario admin si no existe
        admin_user = Usuario.query.filter_by(username=admin_username).first()
        if not admin_user:
            # Leer contraseña desde variable de entorno o generar una aleatoria
            admin_password = os.getenv('ADMIN_PASSWORD')
            if not admin_password:
                admin_password = secrets.token_urlsafe(16)
                print(f"\n🔐 Contraseña admin generada: {admin_password}")
                print(f"   Guárdala en la variable ADMIN_PASSWORD\n")
            
            # Hashear la contraseña con bcrypt
            admin_password_hash = bcrypt.generate_password_hash(admin_password).decode('utf-8')
            
            admin_user = Usuario(
                username=admin_username,
                password_hash=admin_password_hash,
                nombre='Jose Rojas',
                email=admin_email,
                rol='super admin',
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
