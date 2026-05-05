from flask import render_template, request, redirect, url_for, flash, session
import secrets
from datetime import datetime, timedelta

from models.database import db, bcrypt
from models.falla import Falla
from models.usuario import Usuario, ROLES_VALIDOS
from routes.auth import auth_bp
from routes.utils import es_admin, es_super_o_admin, validar_password, password_matches
from routes.utils import get_rol_activo, etiqueta_rol_visible, puede_cambiar_rol, roles_disponibles_para_usuario
from routes.utils import enviar_email, tiene_acceso_total


@auth_bp.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    rol_activo = get_rol_activo()
    es_admin_usr = es_admin()

    fallas_nuevas = []
    if es_admin_usr:
        cinco_dias = datetime.now() - timedelta(days=5)
        fallas_nuevas = (Falla.query
                        .filter(Falla.fecha_registro >= cinco_dias)
                        .order_by(Falla.fecha_registro.desc())
                        .limit(10)
                        .all())

    return render_template(
        'dashboard.html',
        username=session['username'],
        rol=rol_activo,
        rol_visible=etiqueta_rol_visible(),
        puede_cambiar_rol=puede_cambiar_rol(),
        roles_alternables=roles_disponibles_para_usuario(),
        fallas_nuevas=fallas_nuevas,
        es_admin=es_admin_usr,
    )


@auth_bp.route('/vista-historial')
def vista_historial():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not tiene_acceso_total():
        flash('No tiene permisos para ver esta sección', 'error')
        return redirect(url_for('auth.dashboard'))

    filter_instructor = request.args.get('filter_instructor', '').strip()
    filter_aprendiz = request.args.get('filter_aprendiz', '').strip()

    query = Falla.query
    if filter_instructor:
        query = query.filter(Falla.nombre_instructor.ilike(f'%{filter_instructor}%'))
    if filter_aprendiz:
        query = query.filter(Falla.nombre_aprendiz.ilike(f'%{filter_aprendiz}%'))

    fallas = query.order_by(Falla.fecha_registro.desc()).all()
    return render_template(
        'historial.html',
        username=session['username'],
        rol=get_rol_activo(),
        rol_visible=etiqueta_rol_visible(),
        fallas=fallas,
    )


@auth_bp.route('/agregar-admin', methods=['POST'])
def agregar_admin():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_super_o_admin():
        flash('No tiene permisos para agregar administradores', 'error')
        return redirect(url_for('auth.dashboard'))

    nombre = (request.form.get('admin_nombre') or '').strip()
    correo = (request.form.get('admin_correo') or '').strip().lower()
    password = request.form.get('admin_password') or ''

    if not nombre or not correo or not password:
        flash('Nombre, correo y contraseña son obligatorios', 'error')
        return redirect(url_for('auth.dashboard'))

    es_valida, mensaje = validar_password(password)
    if not es_valida:
        flash(mensaje, 'error')
        return redirect(url_for('auth.dashboard'))

    try:
        existente = Usuario.query.filter_by(email=correo).first()
        if existente:
            flash('Ya existe un usuario con ese correo', 'error')
            return redirect(url_for('auth.dashboard'))

        username_base = correo.split('@')[0] if '@' in correo else correo
        username_final = username_base
        indice = 1
        while Usuario.query.filter_by(username=username_final).first():
            username_final = f'{username_base}_{indice}'
            indice += 1

        usuario = Usuario(
            username=username_final,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            rol='administrador',
            nombre=nombre,
            email=correo,
            debe_cambiar_password=True,
        )
        db.session.add(usuario)
        db.session.commit()

        flash('Administrador agregado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        print(f'Error agregando administrador: {e}')
        flash('No fue posible agregar el administrador', 'error')

    return redirect(url_for('auth.dashboard'))


@auth_bp.route('/registrar-usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_super_o_admin():
        flash('No tiene permisos para registrar usuarios', 'error')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'GET':
        return render_template(
            'registrar_usuario.html',
            username=session['username'],
            rol=get_rol_activo(),
            rol_visible=etiqueta_rol_visible(),
            roles_validos=ROLES_VALIDOS,
        )

    # POST - Procesar registro
    nombre = (request.form.get('nombre') or '').strip()
    apellido = (request.form.get('apellido') or '').strip()
    correo = (request.form.get('correo') or '').strip().lower()
    telefono = (request.form.get('telefono') or '').strip()
    rol = (request.form.get('rol') or '').strip().lower()

    if not nombre or not correo or not rol:
        flash('Nombre, correo y rol son obligatorios', 'error')
        return redirect(url_for('auth.registrar_usuario'))

    if rol not in ROLES_VALIDOS:
        flash('Rol no válido', 'error')
        return redirect(url_for('auth.registrar_usuario'))

    try:
        existente = Usuario.query.filter_by(email=correo).first()
        if existente:
            flash('Ya existe un usuario con ese correo', 'error')
            return redirect(url_for('auth.registrar_usuario'))

        username_base = correo.split('@')[0] if '@' in correo else correo
        # Limitar username a 70 caracteres para dejar espacio al sufijo _1, _2, etc.
        username_base = username_base[:70]
        username_final = username_base
        indice = 1
        while Usuario.query.filter_by(username=username_final).first():
            username_final = f'{username_base}_{indice}'
            indice += 1

        # Generar contraseña temporal aleatoria
        password_temporal = secrets.token_urlsafe(12)
        password_hash = bcrypt.generate_password_hash(password_temporal).decode('utf-8')
        
        usuario = Usuario(
            username=username_final,
            password_hash=password_hash,
            rol=rol,
            nombre=nombre,
            apellido=apellido,
            email=correo,
            telefono=telefono,
            debe_cambiar_password=True,
        )
        db.session.add(usuario)
        db.session.commit()

        # Enviar correo con enlace para configurar contraseña
        token = secrets.token_hex(16)
        usuario.token_recuperacion = token
        usuario.token_expiracion = datetime.now() + timedelta(hours=24)
        db.session.commit()

        enlace = url_for('auth.restablecer_password', token=token, _external=True)
        cuerpo = f"""
        <h2>Bienvenido al Sistema Macro Sena</h2>
        <p>Hola <strong>{nombre}</strong>,</p>
        <p>Tu cuenta ha sido creada exitosamente. Para configurar tu contraseña, haz clic en el siguiente enlace (válido por 24 horas):</p>
        <p><a href="{enlace}" style="background:#198754;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
            Configurar mi contraseña
        </a></p>
        <p><strong>Usuario:</strong> {username_final}</p>
        <p>Si no solicitaste este correo, ignora este mensaje.</p>
        """
        
        email_enviado = enviar_email(correo, 'Bienvenido al Sistema Macro Sena - Configura tu contraseña', cuerpo)

        if email_enviado:
            flash(f'Usuario {nombre} registrado exitosamente. Se ha enviado un correo para configurar la contraseña.', 'success')
        else:
            flash(f'Usuario {nombre} registrado, pero no se pudo enviar el correo. El usuario deberá usar la recuperación de contraseña.', 'warning')
        
        return redirect(url_for('auth.dashboard'))
    except Exception as e:
        db.session.rollback()
        print(f'Error registrando usuario: {e}')
        flash(f'No fue posible registrar el usuario. Error: {str(e)}', 'error')
        return redirect(url_for('auth.registrar_usuario'))
