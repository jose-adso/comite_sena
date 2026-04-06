from config import app, db, bcrypt
from models.usuario import Usuario
from models.falla import Falla
from models.reclamo import Reclamo
from routes import auth_bp
from routes.usuarios import usuarios_bp
import base64

# Registrar Blueprint de rutas
app.register_blueprint(auth_bp)
app.register_blueprint(usuarios_bp)

# Contraseña del super admin (codificada en Base64 para que no sea visible en texto plano)
_SUPERADMIN_PASSWORD_B64 = "amhvc2V0NDBA="


def _get_superadmin_password():
    """Decodifica la contraseña del super admin desde Base64"""
    try:
        return base64.b64decode(_SUPERADMIN_PASSWORD_B64).decode('utf-8')
    except Exception:
        return None


# Inicializar base de datos
def init_db():
    with app.app_context():
        db.create_all()
        
        # Crear usuario super admin si no existe
        superadmin_username = 'joserojas'
        superadmin_email = 'jhoset40@gmail.com'
        superadmin_password = _get_superadmin_password()
        
        # Solo crear el usuario super admin si no existe y hay contraseña
        superadmin_user = Usuario.query.filter_by(username=superadmin_username).first()
        if not superadmin_user:
            if not superadmin_password:
                print("⚠️  Error: No se pudo obtener la contraseña del super admin")
            else:
                # Hashear la contraseña con bcrypt
                superadmin_password_hash = bcrypt.generate_password_hash(superadmin_password).decode('utf-8')
                
                superadmin_user = Usuario(
                    username=superadmin_username,
                    password_hash=superadmin_password_hash,
                    nombre='Jose Rojas',
                    email=superadmin_email,
                    rol='super admin',
                    debe_cambiar_password=False,
                )
                db.session.add(superadmin_user)
                db.session.commit()
                print(f"✅ Usuario super admin '{superadmin_username}' creado.")
        else:
            cambios = False

            if superadmin_user.email != superadmin_email:
                superadmin_user.email = superadmin_email
                cambios = True

            # Verificar y sincronizar la contraseña si es necesario
            superadmin_password = _get_superadmin_password()
            if superadmin_password:
                password_ok = False
                try:
                    password_ok = bcrypt.check_password_hash(superadmin_user.password_hash, superadmin_password)
                except Exception:
                    password_ok = False

                if not password_ok:
                    superadmin_user.password_hash = bcrypt.generate_password_hash(superadmin_password).decode('utf-8')
                    superadmin_user.debe_cambiar_password = False
                    cambios = True
                    print("✅ Contraseña del super admin sincronizada.")

            if superadmin_user.rol != 'super admin':
                superadmin_user.rol = 'super admin'
                cambios = True

            if cambios:
                db.session.commit()
                print("✅ Datos del super admin actualizados.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    init_db()
    app.run(debug=True, host='0.0.0.0', port=args.port)
