from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os
import smtplib
import secrets
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32)  # Clave secreta segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de email SMTP
SMTP_EMAIL = 'jhoset40@gmail.com'
SMTP_PASSWORD = 'nocgkncmnwxpzbhi'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

def enviar_email(destinatario, asunto, cuerpo):
    """Envía un email usando Gmail SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False

def validar_password(password):
    """
    Valida que la contraseña cumpla con los requisitos mínimos:
    - Mínimo 8 caracteres
    - Al menos una letra mayúscula
    - Al menos una letra minúscula
    - Al menos un número
    - Al menos un carácter especial
    
    Retorna: (es_valida, mensaje_error)
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    
    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe contener al menos una letra mayúscula"
    
    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe contener al menos una letra minúscula"
    
    if not re.search(r'\d', password):
        return False, "La contraseña debe contener al menos un número"
    
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>_~\-]', password):
        return False, "La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?\":{}|<>_-)"
    
    return True, ""

# Modelo de Usuario
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    rol = db.Column(db.String(20), default='usuario')
    nombre = db.Column(db.String(100), nullable=True)
    apellido = db.Column(db.String(100), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    debe_cambiar_password = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    token_recuperacion = db.Column(db.String(32), nullable=True)
    token_expiracion = db.Column(db.DateTime, nullable=True)

# Crear base de datos y usuario admin por defecto
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

# Rutas
@app.route('/')
def index():
    mostrar_registro = False
    if 'usuario_id' in session and session.get('rol') == 'admin':
        mostrar_registro = True
    # Obtener intentos fallidos
    intentos = session.get('intentos_fallidos', 0)
    mostrar_recuperar = intentos >= 3
    
    return render_template('index.html', mostrar_registro=mostrar_registro, 
                           intentos=intentos, mostrar_recuperar=mostrar_recuperar)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    usuario = Usuario.query.filter_by(username=username).first()
    
    if usuario and bcrypt.check_password_hash(usuario.password_hash, password):
        # Login exitoso - resetear intentos
        session['intentos_fallidos'] = 0
        session['usuario_id'] = usuario.id
        session['username'] = usuario.username
        session['rol'] = usuario.rol
        
        # Verificar si debe cambiar la contraseña
        if usuario.debe_cambiar_password:
            flash('Debe cambiar su contraseña temporal', 'warning')
            return redirect(url_for('cambiar_password'))
        
        flash(f'Bienvenido, {usuario.username}!', 'success')
        return redirect(url_for('dashboard'))
    else:
        # Login fallido - incrementar intentos
        intentos = session.get('intentos_fallidos', 0) + 1
        session['intentos_fallidos'] = intentos
        
        if intentos >= 3:
            flash(f'Usuario o contraseña incorrectos. Ha alcanzado el límite de 3 intentos.', 'error')
        else:
            flash(f'Usuario o contraseña incorrectos. Intentos: {intentos}/3', 'error')
        return redirect(url_for('index'))

@app.route('/registro', methods=['POST'])
def registro():
    # Solo el admin puede registrar nuevos usuarios
    if 'usuario_id' not in session or session.get('rol') != 'admin':
        flash('No tiene permisos para registrar usuarios', 'error')
        return redirect(url_for('index'))
    
    username = request.form.get('reg_username')
    nombre = request.form.get('reg_nombre')
    apellido = request.form.get('reg_apellido')
    telefono = request.form.get('reg_telefono')
    email = request.form.get('reg_email')
    
    # Verificar si el usuario ya existe
    if Usuario.query.filter_by(username=username).first():
        flash('El usuario ya existe', 'error')
        return redirect(url_for('dashboard'))
    
    if email and Usuario.query.filter_by(email=email).first():
        flash('El email ya está registrado', 'error')
        return redirect(url_for('dashboard'))
    
    # Generar contraseña aleatoria
    import random
    import string
    password_aleatoria = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # Hashear la contraseña
    password_hash = bcrypt.generate_password_hash(password_aleatoria, rounds=12).decode('utf-8')
    
    nuevo_usuario = Usuario(
        username=username,
        password_hash=password_hash,
        rol='usuario',
        nombre=nombre,
        apellido=apellido,
        telefono=telefono,
        email=email,
        debe_cambiar_password=True
    )
    
    db.session.add(nuevo_usuario)
    db.session.commit()
    
    # Enviar email con la contraseña
    asunto = "Credenciales de Acceso - Sistema Macro Sena"
    cuerpo = f"""
    <html>
    <body>
        <h2>Bienvenido al Sistema Macro Sena</h2>
        <p>Se han creado sus credenciales de acceso:</p>
        <ul>
            <li><strong>Usuario:</strong> {username}</li>
            <li><strong>Contraseña temporal:</strong> {password_aleatoria}</li>
        </ul>
        <p><strong>Importante:</strong> Debe cambiar su contraseña al iniciar sesión.</p>
        <p>Acceso al sistema: <a href='http://127.0.0.1:5000'>http://127.0.0.1:5000</a></p>
    </body>
    </html>
    """
    
    email_enviado = enviar_email(email, asunto, cuerpo)
    
    if email_enviado:
        flash(f'Usuario {username} registrado. Las credenciales fueron enviadas a {email}', 'success')
    else:
        # Si falla el email, mostrar la contraseña en consola
        print(f"===== EMAIL ENVIADO =====")
        print(f"Para: {email}")
        print(f"Usuario: {username}")
        print(f"Contraseña temporal: {password_aleatoria}")
        print(f"=========================")
        flash(f'Usuario {username} registrado. Error al enviar email, credenciales en consola.', 'warning')
    
    return redirect(url_for('dashboard'))

@app.route('/recuperar', methods=['POST'])
def recuperar():
    email = request.form.get('rec_email')
    
    usuario = Usuario.query.filter_by(email=email).first()
    
    if usuario:
        # Generar token único
        token = secrets.token_hex(16)
        expiracion = datetime.now() + timedelta(hours=1)
        
        # Guardar token en la base de datos
        usuario.token_recuperacion = token
        usuario.token_expiracion = expiracion
        db.session.commit()
        
        # Generar enlace de recuperación
        # Obtener el host desde la petición
        base_url = request.host_url.rstrip('/')
        enlace = f"{base_url}/restablecer/{token}"
        
        # Crear cuerpo del email en HTML
        cuerpo = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
                .header {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 30px; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Recuperación de Contraseña</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{usuario.nombre or usuario.username}</strong>,</p>
                    <p>Has solicitado recuperar tu contraseña en el Sistema Macro Sena.</p>
                    <p>Haz clic en el siguiente botón para crear una nueva contraseña:</p>
                    <p style="text-align: center;">
                        <a href="{enlace}" class="button">Restablecer mi Contraseña</a>
                    </p>
                    <p><strong>Nota:</strong> Este enlace expirará en 1 hora.</p>
                    <p>Si no solicitaste este cambio, puedes ignorar este correo.</p>
                </div>
                <div class="footer">
                    <p>© 2024 Sistema Macro Sena</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        asunto = "Recuperación de Contraseña - Sistema Macro Sena"
        email_enviado = enviar_email(email, asunto, cuerpo)
        
        if email_enviado:
            flash(f'Las instrucciones de recuperación han sido enviadas a {email}', 'success')
            print(f"===== EMAIL DE RECUPERACIÓN ENVIADO =====")
            print(f"Para: {email}")
            print(f"Token: {token}")
            print(f"Enlace: {enlace}")
            print(f"==========================================")
        else:
            # Si falla el email, mostrar el enlace en consola
            print(f"===== EMAIL DE RECUPERACIÓN (ERROR - MOSTRANDO EN CONSOLA) =====")
            print(f"Para: {email}")
            print(f"Token: {token}")
            print(f"Enlace: {enlace}")
            print(f"===============================================================")
            flash(f'Error al enviar el correo. Contacta al administrador.', 'error')
    else:
        flash('El email no está registrado', 'error')
    
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('index'))
    
    # Obtener lista de usuarios para el admin
    usuarios = []
    if session.get('rol') == 'admin':
        usuarios = Usuario.query.all()
    
    return render_template('dashboard.html', username=session['username'], rol=session['rol'], usuarios=usuarios)

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('index'))

@app.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer_password(token):
    # Buscar usuario con el token
    usuario = Usuario.query.filter_by(token_recuperacion=token).first()
    
    if not usuario:
        flash('El enlace de recuperación no es válido', 'error')
        return redirect(url_for('index'))
    
    # Verificar si el token ha expirado
    if usuario.token_expiracion and usuario.token_expiracion < datetime.now():
        # Limpiar token
        usuario.token_recuperacion = None
        usuario.token_expiracion = None
        db.session.commit()
        flash('El enlace de recuperación ha expirado. Solicita uno nuevo.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('restablecer_password', token=token))
        
        # Validar requisitos mínimos de contraseña
        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('restablecer_password', token=token))
        
        # Actualizar contraseña
        usuario.password_hash = bcrypt.generate_password_hash(nueva_password).decode('utf-8')
        # Limpiar token
        usuario.token_recuperacion = None
        usuario.token_expiracion = None
        usuario.debe_cambiar_password = False
        db.session.commit()
        
        flash('Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('index'))
    
    return render_template('restablecer_password.html', token=token)

@app.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('cambiar_password'))
        
        # Validar requisitos mínimos de contraseña
        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('cambiar_password'))
        
        usuario = Usuario.query.get(session['usuario_id'])
        usuario.password_hash = bcrypt.generate_password_hash(nueva_password, rounds=12).decode('utf-8')
        usuario.debe_cambiar_password = False
        db.session.commit()
        
        flash('Contraseña actualizada exitosamente', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('cambiar_password.html', username=session['username'])

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
