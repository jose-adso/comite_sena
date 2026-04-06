from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import secrets
from datetime import datetime, timedelta

from models.database import db, bcrypt
from models.usuario import Usuario, ROLES_VALIDOS
from routes.utils import es_super_o_admin, es_admin
from routes.utils import get_rol_activo, etiqueta_rol_visible
from routes.utils import enviar_email

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.route('/gestionar-usuarios')
def gestionar_usuarios():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_super_o_admin():
        flash('No tiene permisos para gestionar usuarios', 'error')
        return redirect(url_for('auth.dashboard'))

    usuarios = Usuario.query.order_by(Usuario.fecha_creacion.desc()).all()
    return render_template(
        'gestionar_usuarios.html',
        usuarios=usuarios,
        username=session['username'],
        rol=get_rol_activo(),
        rol_visible=etiqueta_rol_visible(),
        usuario_actual_id=session.get('usuario_id'),
    )


@usuarios_bp.route('/registrar-usuario', methods=['GET', 'POST'])
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
        return redirect(url_for('usuarios.registrar_usuario'))

    if rol not in ROLES_VALIDOS:
        flash('Rol no válido', 'error')
        return redirect(url_for('usuarios.registrar_usuario'))

    try:
        existente = Usuario.query.filter_by(email=correo).first()
        if existente:
            flash('Ya existe un usuario con ese correo', 'error')
            return redirect(url_for('usuarios.registrar_usuario'))

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
        
        return redirect(url_for('usuarios.gestionar_usuarios'))
    except Exception as e:
        db.session.rollback()
        print(f'Error registering user: {e}')
        flash(f'No fue posible registrar el usuario. Error: {str(e)}', 'error')
        return redirect(url_for('usuarios.registrar_usuario'))


@usuarios_bp.route('/eliminar-usuario/<int:usuario_id>', methods=['POST'])
def eliminar_usuario(usuario_id):
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_super_o_admin():
        flash('No tiene permisos para eliminar usuarios', 'error')
        return redirect(url_for('auth.dashboard'))

    # No permitir eliminar al propio usuario
    if session['usuario_id'] == usuario_id:
        flash('No puede eliminarse a sí mismo', 'error')
        return redirect(url_for('usuarios.gestionar_usuarios'))

    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('usuarios.gestionar_usuarios'))

    # No permitir eliminar al super admin
    if usuario.rol == 'super admin':
        flash('No se puede eliminar el usuario super admin', 'error')
        return redirect(url_for('usuarios.gestionar_usuarios'))

    try:
        nombre_eliminado = usuario.nombre
        db.session.delete(usuario)
        db.session.commit()
        flash(f'Usuario {nombre_eliminado} eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        print(f'Error eliminando usuario: {e}')
        flash('No fue posible eliminar el usuario', 'error')

    return redirect(url_for('usuarios.gestionar_usuarios'))