from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os
import smtplib
import secrets
import re
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from models.database import db, bcrypt
from models.usuario import Usuario
from models.falla import Falla

auth_bp = Blueprint('auth', __name__)

# Configuración de email SMTP
SMTP_EMAIL = 'jhoset40@gmail.com'
SMTP_PASSWORD = 'nocgkncmnwxpzbhi'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587


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


def es_admin():
    """Verifica si el usuario actual es admin o administrador"""
    return session.get('rol') in ['admin', 'administrador']


def es_docente():
    """Verifica si el usuario actual es docente"""
    return session.get('rol') == 'docente'


# Crear base de datos y usuario admin por defecto
def init_db():
    from app import app
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


# Rutas del Blueprint
@auth_bp.route('/')
def index():
    mostrar_registro = False
    if 'usuario_id' in session and es_admin():
        mostrar_registro = True
    # Obtener intentos fallidos
    intentos = session.get('intentos_fallidos', 0)
    mostrar_recuperar = intentos >= 3
    
    return render_template('index.html', mostrar_registro=mostrar_registro, 
                           intentos=intentos, mostrar_recuperar=mostrar_recuperar)


@auth_bp.route('/login', methods=['POST'])
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
            return redirect(url_for('auth.cambiar_password'))
        
        flash(f'Bienvenido, {usuario.username}!', 'success')
        return redirect(url_for('auth.dashboard'))
    else:
        # Login fallido - incrementar intentos
        intentos = session.get('intentos_fallidos', 0) + 1
        session['intentos_fallidos'] = intentos
        
        if intentos >= 3:
            flash(f'Usuario o contraseña incorrectos. Ha alcanzado el límite de 3 intentos.', 'error')
        else:
            flash(f'Usuario o contraseña incorrectos. Intentos: {intentos}/3', 'error')
        return redirect(url_for('auth.index'))


@auth_bp.route('/registro', methods=['POST'])
def registro():
    # Solo el admin puede registrar nuevos usuarios
    if 'usuario_id' not in session or not es_admin():
        flash('No tiene permisos para registrar usuarios', 'error')
        return redirect(url_for('auth.index'))
    
    username = request.form.get('reg_username')
    nombre = request.form.get('reg_nombre')
    apellido = request.form.get('reg_apellido')
    telefono = request.form.get('reg_telefono')
    email = request.form.get('reg_email')
    rol = request.form.get('reg_rol', 'docente')  # Por defecto docente
    
    # Verificar si el usuario ya existe
    if Usuario.query.filter_by(username=username).first():
        flash('El usuario ya existe', 'error')
        return redirect(url_for('auth.dashboard'))
    
    if email and Usuario.query.filter_by(email=email).first():
        flash('El email ya está registrado', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # Generar contraseña aleatoria
    password_aleatoria = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # Hashear la contraseña
    password_hash = bcrypt.generate_password_hash(password_aleatoria, rounds=12).decode('utf-8')
    
    nuevo_usuario = Usuario(
        username=username,
        password_hash=password_hash,
        rol=rol,
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
        <p>Acceso al sistema: <a href='http://127.0.0.1:8080'>http://127.0.0.1:8080</a></p>
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
    
    return redirect(url_for('auth.dashboard'))


@auth_bp.route('/recuperar', methods=['POST'])
def recuperar():
    print("===== INICIANDO PROCESO DE RECUPERACIÓN =====")
    email = request.form.get('rec_email')
    print(f"Email recibido: {email}")
    
    try:
        usuario = Usuario.query.filter_by(email=email).first()
        print(f"Usuario encontrado: {usuario}")
        
        if usuario is None:
            print("Usuario no encontrado en la base de datos")
            flash('El email no está registrado', 'error')
            return redirect(url_for('auth.index'))
        
        # Generar token único
        token = secrets.token_hex(16)
        expiracion = datetime.now() + timedelta(hours=1)
        print(f"Token generado: {token}")
        print(f"Expiración: {expiracion}")
        
        # Guardar token en la base de datos
        try:
            usuario.token_recuperacion = token
            usuario.token_expiracion = expiracion
            db.session.commit()
            print("Token guardado exitosamente en la base de datos")
        except Exception as db_error:
            print(f"ERROR DE BASE DE DATOS: {db_error}")
            db.session.rollback()
            flash('Error al procesar la solicitud. Contacta al administrador.', 'error')
            return redirect(url_for('auth.index'))
        
        # Generar enlace de recuperación
        # Usar puerto fijo 8080
        base_url = 'http://127.0.0.1:8080'
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
        
        # Agregar logs para el envío de email
        print(f"===== INTENTANDO ENVIAR EMAIL =====")
        print(f"SMTP_EMAIL: {SMTP_EMAIL}")
        print(f"SMTP_SERVER: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"Destinatario: {email}")
        
        try:
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
        except Exception as email_error:
            print(f"ERROR AL ENVIAR EMAIL: {email_error}")
            # Mostrar enlace en consola como fallback
            print(f"===== FALLBACK - ENLACE DE RECUPERACIÓN =====")
            print(f"Para: {email}")
            print(f"Token: {token}")
            print(f"Enlace: {enlace}")
            print(f"===============================================")
            flash(f'Error al enviar el correo. El enlace de recuperación es: {enlace}', 'error')
            
    except Exception as e:
        print(f"ERROR GENERAL EN RECUPERACIÓN: {e}")
        flash('Error al procesar la solicitud. Contacta al administrador.', 'error')
    
    return redirect(url_for('auth.index'))


@auth_bp.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    # Redirigir docentes a su vista específica
    if es_docente():
        return redirect(url_for('auth.vista_docente'))
    
    # Obtener lista de usuarios para el admin
    usuarios = []
    if es_admin():
        usuarios = Usuario.query.all()
    
    return render_template('dashboard.html', username=session['username'], rol=session['rol'], usuarios=usuarios)


@auth_bp.route('/docente')
def vista_docente():
    """Vista del panel docente para registro de fallas"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    if not es_docente():
        flash('No tiene acceso a esta sección', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # Obtener datos del instructor desde la sesión
    nombre_instructor = session.get('nombre', session.get('username', 'Instructor'))
    
    return render_template('docente.html', username=session['username'], nombre_instructor=nombre_instructor)


@auth_bp.route('/registrar-falla', methods=['POST'])
def registrar_falla():
    """Procesa el registro de fallas de un aprendiz"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    if not es_docente():
        flash('No tiene acceso a esta sección', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # Obtener datos del formulario
    nombre_instructor = request.form.get('nombre_instructor')
    cedula_instructor = request.form.get('cedula_instructor')
    correo_instructor = request.form.get('correo_instructor')
    nombre_ficha = request.form.get('nombre_ficha')
    numero_ficha = request.form.get('numero_ficha')
    nombre_aprendiz = request.form.get('nombre_aprendiz')
    documento_aprendiz = request.form.get('documento_aprendiz')
    correo_aprendiz = request.form.get('correo_aprendiz')
    telefono_aprendiz = request.form.get('telefono_aprendiz')
    descripcion_faltas = request.form.get('descripcion_faltas')
    fecha_falta = request.form.get('fecha')
    
    # Convertir fecha
    from datetime import datetime
    fecha_falta_date = datetime.strptime(fecha_falta, '%Y-%m-%d').date() if fecha_falta else None
    
    # Manejar imágenes evidencia
    evidencias = request.files.getlist('evidencia')
    archivos_guardados = []
    evidencia_ruta = ''
    firma_ruta = ''
    
    if evidencias and evidencias[0].filename:
        # Crear carpeta de evidencias si no existe
        from app import app
        import os
        upload_folder = os.path.join(app.root_path, 'static', 'evidencias')
        os.makedirs(upload_folder, exist_ok=True)
        
        for evidencia in evidencias:
            if evidencia and evidencia.filename:
                # Generar nombre único
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{evidencia.filename}"
                filepath = os.path.join(upload_folder, filename)
                evidencia.save(filepath)
                archivos_guardados.append(f"evidencias/{filename}")
        
        evidencia_ruta = ','.join(archivos_guardados)
    
    # Manejar firma
    firma = request.files.get('firma')
    if firma and firma.filename:
        upload_folder = os.path.join(app.root_path, 'static', 'firmas')
        os.makedirs(upload_folder, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"firma_{timestamp}_{firma.filename}"
        filepath = os.path.join(upload_folder, filename)
        firma.save(filepath)
        firma_ruta = f"firmas/{filename}"
    
    # Crear registro de falla en la base de datos
    try:
        falla = Falla(
            instructor_id=session['usuario_id'],
            nombre_instructor=nombre_instructor,
            cedula_instructor=cedula_instructor,
            correo_instructor=correo_instructor,
            nombre_ficha=nombre_ficha,
            numero_ficha=numero_ficha,
            nombre_aprendiz=nombre_aprendiz,
            documento_aprendiz=documento_aprendiz,
            correo_aprendiz=correo_aprendiz,
            telefono_aprendiz=telefono_aprendiz,
            descripcion_faltas=descripcion_faltas,
            fecha_falta=fecha_falta_date,
            evidencia=evidencia_ruta,
            firma=firma_ruta
        )
        db.session.add(falla)
        db.session.commit()
        flash('Falla registrada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar la falla: {str(e)}', 'error')
    
    return redirect(url_for('auth.vista_docente'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('auth.index'))


@auth_bp.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer_password(token):
    print(f"===== RUTA /restablecer/{token} ACCEDIDA =====")
    
    # Buscar usuario con el token
    try:
        usuario = Usuario.query.filter_by(token_recuperacion=token).first()
        print(f"Usuario encontrado: {usuario}")
    except Exception as db_error:
        print(f"ERROR AL BUSCAR USUARIO: {db_error}")
        flash('El enlace de recuperación no es válido', 'error')
        return redirect(url_for('auth.index'))
    
    if not usuario:
        flash('El enlace de recuperación no es válido', 'error')
        return redirect(url_for('auth.index'))
    
    # Verificar si el token ha expirado
    if usuario.token_expiracion and usuario.token_expiracion < datetime.now():
        # Limpiar token
        usuario.token_recuperacion = None
        usuario.token_expiracion = None
        db.session.commit()
        flash('El enlace de recuperación ha expirado. Solicita uno nuevo.', 'error')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('auth.restablecer_password', token=token))
        
        # Validar requisitos mínimos de contraseña
        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('auth.restablecer_password', token=token))
        
        # Actualizar contraseña
        try:
            usuario.password_hash = bcrypt.generate_password_hash(nueva_password).decode('utf-8')
            # Limpiar token
            usuario.token_recuperacion = None
            usuario.token_expiracion = None
            usuario.debe_cambiar_password = False
            db.session.commit()
            print("===== CONTRASEÑA ACTUALIZADA EXITOSAMENTE =====")
            flash('Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.index'))
        except Exception as update_error:
            print(f"ERROR AL ACTUALIZAR CONTRASEÑA: {update_error}")
            db.session.rollback()
            flash('Error al actualizar la contraseña. Contacta al administrador.', 'error')
            return redirect(url_for('auth.restablecer_password', token=token))
    
    return render_template('restablecer_password.html', token=token)


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('auth.cambiar_password'))
        
        # Validar requisitos mínimos de contraseña
        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('auth.cambiar_password'))
        
        usuario = Usuario.query.get(session['usuario_id'])
        usuario.password_hash = bcrypt.generate_password_hash(nueva_password, rounds=12).decode('utf-8')
        usuario.debe_cambiar_password = False
        db.session.commit()
        
        flash('Contraseña actualizada exitosamente', 'success')
        return redirect(url_for('auth.dashboard'))
    
    return render_template('cambiar_password.html', username=session['username'])


@auth_bp.route('/eliminar-usuario/<int:usuario_id>', methods=['POST'])
def eliminar_usuario(usuario_id):
    """Elimina un usuario (solo el admin puede eliminar)"""
    # Verificar que el usuario esté logueado
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    # Verificar que sea admin (solo admin puede eliminar usuarios)
    if session.get('rol') not in ['admin', 'administrador']:
        flash('No tiene permisos para eliminar usuarios', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # No permitir que el admin se elimine a sí mismo
    if usuario_id == session.get('usuario_id'):
        flash('No puede eliminarse a sí mismo', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # Buscar el usuario a eliminar
    usuario = Usuario.query.get(usuario_id)
    
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # No permitir eliminar al usuario admin principal
    if usuario.username == 'joserojas':
        flash('No puede eliminar el usuario administrador principal', 'error')
        return redirect(url_for('auth.dashboard'))
    
    # Eliminar el usuario
    username_eliminado = usuario.username
    db.session.delete(usuario)
    db.session.commit()
    
    flash(f'Usuario {username_eliminado} eliminado exitosamente', 'success')
    return redirect(url_for('auth.dashboard'))

