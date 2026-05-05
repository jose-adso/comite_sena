from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import os, re, uuid
from models.database import db
from models.plantilla import Plantilla
from routes.utils import es_admin, es_super_o_admin, get_rol_activo, etiqueta_rol_visible

plantillas_bp = Blueprint('plantillas', __name__)


@plantillas_bp.route('/gestionar-plantillas')
def gestionar_plantillas():
    if 'usuario_id' not in session or not es_super_o_admin():
        flash('No tiene permisos para acceder a esta sección', 'error')
        return redirect(url_for('auth.dashboard'))

    # Obtener plantillas registradas en BD
    plantillas_bd = Plantilla.query.order_by(Plantilla.fecha_creacion.desc()).all()

    # Obtener archivos .docx en static/plantillas que no estén registrados
    upload_folder = os.path.join(current_app.root_path, 'static', 'plantillas')
    archivos_en_disco = []
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            if filename.lower().endswith('.docx'):
                archivo_path = f"plantillas/{filename}"
                # Verificar si ya está registrado en BD
                existe_en_bd = any(p.archivo_path == archivo_path for p in plantillas_bd)
                if not existe_en_bd:
                    archivos_en_disco.append({
                        'id': None,
                        'nombre': filename,
                        'descripcion': 'Archivo en disco (no registrado)',
                        'tipo_uso': None,
                        'archivo_path': archivo_path,
                        'activa': True,
                        'fecha_creacion': None,
                        'creado_por': None,
                        'es_archivo_sueltos': True
                    })

    # Combinar ambas listas: BD primero, luego archivos sueltos
    todas_plantillas = list(plantillas_bd) + archivos_en_disco

    return render_template(
        'plantillas/gestionar.html',
        plantillas=todas_plantillas,
        username=session['username'],
        rol=get_rol_activo(),
        rol_visible=etiqueta_rol_visible(),
    )


@plantillas_bp.route('/nueva-plantilla', methods=['GET', 'POST'])
def nueva_plantilla():
    if 'usuario_id' not in session or not es_super_o_admin():
        flash('No tiene permisos para crear plantillas', 'error')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        archivo = request.files.get('archivo')

        # Validaciones
        if not archivo or not archivo.filename:
            flash('Debe seleccionar un archivo DOCX', 'error')
            return redirect(url_for('plantillas.nueva_plantilla'))

        # Validar extensión DOCX
        ext = os.path.splitext(archivo.filename)[1].lower()
        if ext != '.docx':
            flash('Solo se permiten archivos DOCX', 'error')
            return redirect(url_for('plantillas.nueva_plantilla'))

        # Extraer nombre base del archivo (sin extensión) y sanitizar
        nombre_base = os.path.splitext(archivo.filename)[0]
        # Limpiar caracteres inválidos para nombre de archivo
        nombre_archivo = re.sub(r'[<>:"/\\|?*]', '', nombre_base).strip()
        if not nombre_archivo:
            nombre_archivo = f"plantilla_{uuid.uuid4().hex[:8]}"

        # Verificar que no exista una plantilla con ese nombre
        plantilla_existente = Plantilla.query.filter_by(nombre=nombre_archivo).first()
        if plantilla_existente:
            flash('Ya existe una plantilla con ese nombre (use otro nombre de archivo)', 'error')
            return redirect(url_for('plantillas.nueva_plantilla'))

        # Guardar archivo con el nombre sanitizado
        filename = f"{nombre_archivo}{ext}"
        upload_folder = os.path.join(current_app.root_path, 'static', 'plantillas')
        os.makedirs(upload_folder, exist_ok=True)
        archivo.save(os.path.join(upload_folder, filename))
        archivo_path = f"plantillas/{filename}"

        # Guardar en BD
        try:
            plantilla = Plantilla(
                nombre=nombre_archivo,
                descripcion=None,
                tipo_uso=None,
                archivo_path=archivo_path,
                creado_por_usuario_id=session['usuario_id'],
                activa=True
            )
            db.session.add(plantilla)
            db.session.commit()
            flash('✅ Plantilla creada exitosamente', 'success')
            return redirect(url_for('plantillas.gestionar_plantillas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear plantilla: {str(e)}', 'error')
            return redirect(url_for('plantillas.nueva_plantilla'))
            return redirect(url_for('plantillas.nueva_plantilla'))

    return render_template(
        'plantillas/nueva.html',
        username=session['username'],
        rol=get_rol_activo(),
        rol_visible=etiqueta_rol_visible(),
    )


@plantillas_bp.route('/registrar-plantilla-existente', methods=['POST'])
def registrar_plantilla_existente():
    if 'usuario_id' not in session or not es_super_o_admin():
        flash('No tiene permisos para registrar plantillas', 'error')
        return redirect(url_for('auth.dashboard'))

    archivo_path = (request.form.get('archivo_path') or '').strip()
    if not archivo_path:
        flash('No se especificó el archivo', 'error')
        return redirect(url_for('plantillas.gestionar_plantillas'))

    # Construir ruta completa del archivo
    archivo_completo = os.path.join(current_app.root_path, 'static', archivo_path)
    if not os.path.exists(archivo_completo):
        flash('El archivo no existe en disco', 'error')
        return redirect(url_for('plantillas.gestionar_plantillas'))

    # Extraer nombre base del archivo (sin ruta)
    filename = os.path.basename(archivo_path)
    # Quitar extensión para el nombre
    nombre_base = os.path.splitext(filename)[0]
    # Limpiar nombre: reemplazar guiones bajos y espacios
    nombre_limpio = nombre_base.replace('_', ' ').replace('-', ' ').strip()

    # Determinar tipo de uso basado en el nombre del archivo
    tipo_uso = None
    nombre_lower = nombre_base.lower()
    if 'acta' in nombre_lower:
        tipo_uso = 'acta'
    elif 'format' in nombre_lower:
        if 'falta' in nombre_lower or 'inasistencia' in nombre_lower:
            tipo_uso = 'formato_falla'
        elif 'rendimiento' in nombre_lower:
            tipo_uso = 'formato_falla'
        elif 'etapa' in nombre_lower:
            tipo_uso = 'formato_falla'
        elif 'comportam' in nombre_lower:
            tipo_uso = 'formato_falla'
        elif 'incumpli' in nombre_lower:
            tipo_uso = 'formato_falla'
        elif 'desercion' in nombre_lower:
            tipo_uso = 'formato_falla'
        else:
            tipo_uso = 'formato_falla'
    elif 'resolucion' in nombre_lower:
        tipo_uso = 'resolucion'

    # Verificar que no exista ya en BD
    existente = Plantilla.query.filter_by(archivo_path=archivo_path).first()
    if existente:
        flash('Esta plantilla ya está registrada en la base de datos', 'warning')
        return redirect(url_for('plantillas.gestionar_plantillas'))

    try:
        plantilla = Plantilla(
            nombre=nombre_limpio,
            descripcion=f'Plantila registrada automáticamente desde archivo: {filename}',
            archivo_path=archivo_path,
            tipo_uso=tipo_uso,
            activa=True,
            creado_por_usuario_id=session['usuario_id']
        )
        db.session.add(plantilla)
        db.session.commit()
        flash(f'✅ Plantilla "{nombre_limpio}" registrada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar plantilla: {str(e)}', 'error')

    return redirect(url_for('plantillas.gestionar_plantillas'))


@plantillas_bp.route('/eliminar-plantilla/<int:plantilla_id>', methods=['POST'])
def eliminar_plantilla(plantilla_id):
    if 'usuario_id' not in session or not es_super_o_admin():
        flash('No tiene permisos para eliminar plantillas', 'error')
        return redirect(url_for('auth.dashboard'))

    plantilla = Plantilla.query.get_or_404(plantilla_id)

    try:
        # Eliminar archivo físico
        archivo_completo = os.path.join(current_app.root_path, 'static', plantilla.archivo_path)
        if os.path.exists(archivo_completo):
            os.remove(archivo_completo)

        # Eliminar registro en BD
        db.session.delete(plantilla)
        db.session.commit()
        flash(f'✅ Plantilla "{plantilla.nombre}" eliminada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar plantilla: {str(e)}', 'error')

    return redirect(url_for('plantillas.gestionar_plantillas'))

