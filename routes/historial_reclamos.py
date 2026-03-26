from flask import render_template, request, redirect, url_for, flash, session

from models.database import db
from models.reclamo import Reclamo, ESTADOS_RECLAMO
from routes.auth import auth_bp
from routes.utils import es_admin, get_rol_activo, etiqueta_rol_visible


@auth_bp.route('/historial-reclamos')
def historial_reclamos():
    """Vista del historial de reclamos de instructores"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if not es_admin():
        flash('No tiene permisos para ver esta sección', 'error')
        return redirect(url_for('auth.dashboard'))

    estado_filtro = request.args.get('estado', '').strip()
    instructor_filtro = request.args.get('instructor', '').strip()

    query = Reclamo.query
    if estado_filtro:
        query = query.filter(Reclamo.estado == estado_filtro)
    if instructor_filtro:
        query = query.filter(Reclamo.nombre_instructor.ilike(f'%{instructor_filtro}%'))

    reclamos = query.order_by(Reclamo.fecha_registro.desc()).all()
    return render_template(
        'historial_reclamos.html',
        username=session['username'],
        rol=get_rol_activo(),
        rol_visible=etiqueta_rol_visible(),
        reclamos=reclamos,
        estados=ESTADOS_RECLAMO,
        estado_filtro=estado_filtro,
        instructor_filtro=instructor_filtro,
    )


@auth_bp.route('/actualizar-reclamo/<int:reclamo_id>', methods=['POST'])
def actualizar_reclamo(reclamo_id):
    """Actualizar el estado de un reclamo"""
    if 'usuario_id' not in session:
        return redirect(url_for('auth.index'))

    if not es_admin():
        flash('No tiene permisos para esta acción', 'error')
        return redirect(url_for('auth.historial_reclamos'))

    reclamo = Reclamo.query.get_or_404(reclamo_id)
    nuevo_estado = (request.form.get('estado') or '').strip()
    observacion = (request.form.get('observacion_admin') or '').strip()

    if nuevo_estado not in ESTADOS_RECLAMO:
        flash('Estado no válido', 'error')
        return redirect(url_for('auth.historial_reclamos'))

    reclamo.estado = nuevo_estado
    if observacion:
        reclamo.observacion_admin = observacion
    db.session.commit()
    flash(f'Reclamo #{reclamo_id} actualizado a "{nuevo_estado}"', 'success')
    return redirect(url_for('auth.historial_reclamos'))