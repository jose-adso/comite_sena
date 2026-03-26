from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash as wz_generate_password_hash

from models.database import db
from models.falla import Falla
from models.usuario import Usuario
from routes.auth import auth_bp
from routes.utils import es_admin, es_super_o_admin, validar_password
from routes.utils import get_rol_activo, etiqueta_rol_visible, puede_cambiar_rol, ROLES_ALTERNABLES


@auth_bp.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    rol_activo = get_rol_activo()
    es_admin_usr = es_admin()

    fallas_nuevas = []
    if es_admin_usr:
        fallas_nuevas = Falla.query.order_by(Falla.fecha_registro.desc()).limit(10).all()

    return render_template(
        'dashboard.html',
        username=session['username'],
        rol=rol_activo,
        rol_visible=etiqueta_rol_visible(),
        puede_cambiar_rol=puede_cambiar_rol(),
        roles_alternables=ROLES_ALTERNABLES,
        fallas_nuevas=fallas_nuevas,
        es_admin=es_admin_usr,
    )


@auth_bp.route('/vista-historial')
def vista_historial():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_admin():
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
            password_hash=wz_generate_password_hash(password, method='scrypt'),
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
