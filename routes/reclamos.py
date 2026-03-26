import os
import tempfile
import uuid
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session

from models.database import db
from models.usuario import Usuario
from models.reclamo import Reclamo, TIPOS_RECLAMO, ESTADOS_RECLAMO
from routes.auth import auth_bp
from routes.utils import es_admin, get_rol_activo, etiqueta_rol_visible


@auth_bp.route('/reclamo')
def vista_reclamo():
    """Vista para registrar un nuevo reclamo"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_admin():
        flash('No tiene acceso a esta sección', 'error')
        return redirect(url_for('auth.dashboard'))

    usuario = Usuario.query.get(session['usuario_id'])
    return render_template(
        'reclamo.html',
        username=session['username'],
        rol_visible=etiqueta_rol_visible(),
        tipos_reclamo=TIPOS_RECLAMO,
        nombre_instructor=usuario.nombre or session['username'],
        correo_instructor=usuario.email or '',
    )


@auth_bp.route('/registrar-reclamo', methods=['POST'])
def registrar_reclamo():
    """Registrar un nuevo reclamo"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_admin():
        flash('No tiene acceso a esta sección', 'error')
        return redirect(url_for('auth.dashboard'))

    nombre_instructor = (request.form.get('nombre_instructor') or '').strip()
    cedula_instructor = (request.form.get('cedula_instructor') or '').strip()
    correo_instructor = (request.form.get('correo_instructor') or '').strip()
    nombre_aprendiz = (request.form.get('nombre_aprendiz') or '').strip()
    documento_aprendiz = (request.form.get('documento_aprendiz') or '').strip()
    nombre_ficha = (request.form.get('nombre_ficha') or '').strip()
    numero_ficha = (request.form.get('numero_ficha') or '').strip()
    tipo_reclamo = (request.form.get('tipo_reclamo') or '').strip()
    descripcion = (request.form.get('descripcion') or '').strip()
    fecha_incidente = request.form.get('fecha_incidente')

    campos_requeridos = [
        ('Nombre instructor', nombre_instructor),
        ('Cédula instructor', cedula_instructor),
        ('Correo instructor', correo_instructor),
        ('Nombre aprendiz', nombre_aprendiz),
        ('Documento aprendiz', documento_aprendiz),
        ('Nombre ficha', nombre_ficha),
        ('Número ficha', numero_ficha),
        ('Tipo de reclamo', tipo_reclamo),
        ('Descripción', descripcion),
        ('Fecha del incidente', fecha_incidente),
    ]
    for etiqueta, valor in campos_requeridos:
        if not valor:
            flash(f'{etiqueta} es obligatorio', 'error')
            return redirect(url_for('auth.vista_reclamo'))

    if tipo_reclamo not in TIPOS_RECLAMO:
        flash('Tipo de reclamo no válido', 'error')
        return redirect(url_for('auth.vista_reclamo'))

    try:
        fecha_incidente_date = datetime.strptime(fecha_incidente, '%Y-%m-%d').date()
    except ValueError:
        flash('Fecha del incidente inválida', 'error')
        return redirect(url_for('auth.vista_reclamo'))

    # Guardar evidencia adjunta
    evidencia_ruta = None
    evidencia = request.files.get('evidencia')
    if evidencia and evidencia.filename:
        from app import app as flask_app
        ext = os.path.splitext(evidencia.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.pdf']:
            flash('Formato de evidencia no permitido (JPG, PNG, WEBP, PDF)', 'error')
            return redirect(url_for('auth.vista_reclamo'))
        upload_folder = os.path.join(flask_app.root_path, 'static', 'evidencias')
        os.makedirs(upload_folder, exist_ok=True)
        filename = f"reclamo_{uuid.uuid4().hex}{ext}"
        evidencia.save(os.path.join(upload_folder, filename))
        evidencia_ruta = f"evidencias/{filename}"

    try:
        reclamo = Reclamo(
            instructor_id=session['usuario_id'],
            nombre_instructor=nombre_instructor,
            cedula_instructor=cedula_instructor,
            correo_instructor=correo_instructor,
            nombre_aprendiz=nombre_aprendiz,
            documento_aprendiz=documento_aprendiz,
            nombre_ficha=nombre_ficha,
            numero_ficha=numero_ficha,
            tipo_reclamo=tipo_reclamo,
            descripcion=descripcion,
            fecha_incidente=fecha_incidente_date,
            evidencia=evidencia_ruta,
            estado='Pendiente',
        )
        db.session.add(reclamo)
        db.session.commit()
        flash('✅ Reclamo registrado correctamente. Quedará en revisión.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f'Error al registrar reclamo: {e}')
        flash('Error al guardar el reclamo. Intente de nuevo.', 'error')

    return redirect(url_for('auth.vista_reclamo'))
