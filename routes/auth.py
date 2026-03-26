from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from models.usuario import Usuario

from routes.utils import (
    get_external_user_by_username,
    password_matches,
    normalizar_rol_externo,
    es_admin,
    puede_cambiar_rol,
    ROLES_ALTERNABLES,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    mostrar_registro = False
    if 'usuario_id' in session and es_admin():
        mostrar_registro = True
    intentos = session.get('intentos_fallidos', 0)
    mostrar_recuperar = intentos >= 3
    return render_template(
        'index.html',
        mostrar_registro=mostrar_registro,
        intentos=intentos,
        mostrar_recuperar=mostrar_recuperar,
    )


@auth_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    try:
        usuario = get_external_user_by_username(username)
    except Exception as e:
        print(f"Error consultando usuarios locales: {e}")
        flash('Error de conexion con la base de usuarios', 'error')
        return redirect(url_for('auth.index'))

    if usuario and password_matches(password, usuario):
        local_user = Usuario.query.get(usuario['id'])
        rol_real = normalizar_rol_externo(usuario)
        session['intentos_fallidos'] = 0
        session['usuario_id'] = local_user.id
        session['username'] = (
            usuario.get('username') or usuario.get('nombre') or usuario.get('correo') or username
        )
        session['correo'] = usuario.get('correo') or usuario.get('email') or ''
        session['rol'] = rol_real
        session['rol_real'] = rol_real
        session['rol_activo'] = rol_real

        if bool(usuario.get('debe_cambiar_password', usuario.get('must_change_password', False))):
            flash('Debe cambiar su contrasena temporal', 'warning')
            return redirect(url_for('auth.cambiar_password'))

        flash(f"Bienvenido, {session['username']}!", 'success')
        return redirect(url_for('auth.dashboard'))
    else:
        intentos = session.get('intentos_fallidos', 0) + 1
        session['intentos_fallidos'] = intentos
        if intentos >= 3:
            flash('Usuario o contrasena incorrectos. Ha alcanzado el limite de 3 intentos.', 'error')
        else:
            flash(f'Usuario o contrasena incorrectos. Intentos: {intentos}/3', 'error')
        return redirect(url_for('auth.index'))


@auth_bp.route('/cambiar-rol', methods=['POST'])
def cambiar_rol():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.index'))
    if not puede_cambiar_rol():
        flash('No tiene permisos para cambiar de rol', 'error')
        return redirect(url_for('auth.dashboard'))
    nuevo_rol = (request.form.get('rol_activo') or '').strip().lower()
    if nuevo_rol not in ROLES_ALTERNABLES:
        flash('Rol no válido', 'error')
        return redirect(url_for('auth.dashboard'))
    session['rol_activo'] = nuevo_rol
    flash(f'Rol cambiado a {nuevo_rol.capitalize()}', 'success')
    return redirect(url_for('auth.dashboard'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesion cerrada exitosamente', 'success')
    return redirect(url_for('auth.index'))


