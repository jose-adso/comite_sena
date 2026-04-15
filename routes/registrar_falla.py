import os
import secrets
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session
from docx import Document
from docx.shared import Inches

from models.database import db, bcrypt
from models.usuario import Usuario
from models.falla import Falla
from routes.auth import auth_bp
from routes.utils import (
    es_admin,
    _username_seguro,
    BCRYPT_ROUNDS,
    _replace_in_paragraph,
    _replace_placeholders_doc,
    _enviar_pdf_siempre,
    etiqueta_rol_visible,
)

# Importar función de formateo de fecha desde notificaciones
from routes.notificaciones import formatear_fecha_larga


@auth_bp.route('/registrar-falla')
def vista_registrar_falla():
    """Vista para registrar una falta de aprendiz"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    nombre_instructor = session.get('nombre', session.get('username', 'Instructor'))
    return render_template(
        'registrar_falla.html',
        username=session['username'],
        nombre_instructor=nombre_instructor,
        rol_visible=etiqueta_rol_visible(),
    )


@auth_bp.route('/registrar-falla', methods=['POST'])
def registrar_falla():
    """Procesar el registro de una falta de aprendiz"""
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    nombre_instructor = (request.form.get('nombre_instructor') or '').strip()
    cedula_instructor = (request.form.get('cedula_instructor') or '').strip()
    nombre_ficha = (request.form.get('nombre_ficha') or '').strip()
    numero_ficha = (request.form.get('numero_ficha') or '').strip()
    nombre_aprendiz = (request.form.get('nombre_aprendiz') or '').strip()
    documento_aprendiz = (request.form.get('documento_aprendiz') or '').strip()
    correo_aprendiz = (request.form.get('correo_aprendiz') or '').strip()
    telefono_aprendiz = (request.form.get('telefono_aprendiz') or '').strip()
    descripcion_faltas = (request.form.get('descripcion_faltas') or '').strip()
    fecha_falta = request.form.get('fecha')

    # Corrección automática si los campos están invertidos
    if len(numero_ficha) > 20 and len(nombre_ficha) <= 20:
        nombre_ficha, numero_ficha = numero_ficha, nombre_ficha

    limites = [
        ('Nombre instructor', nombre_instructor, 100),
        ('Cédula instructor', cedula_instructor, 20),
        ('Nombre ficha', nombre_ficha, 100),
        ('Número ficha', numero_ficha, 20),
        ('Nombre aprendiz', nombre_aprendiz, 100),
        ('Documento aprendiz', documento_aprendiz, 20),
        ('Correo aprendiz', correo_aprendiz, 120),
        ('Teléfono aprendiz', telefono_aprendiz, 20),
    ]
    for etiqueta, valor, max_len in limites:
        if len(valor) > max_len:
            flash(f'{etiqueta} supera el límite ({max_len} caracteres)', 'error')
            return redirect(url_for('auth.vista_registrar_falla'))

    fecha_falta_date = datetime.strptime(fecha_falta, '%Y-%m-%d').date() if fecha_falta else None

    # Obtener usuario instructor
    usuario_local = Usuario.query.get(session.get('usuario_id'))
    if not usuario_local:
        username_sesion = session.get('username', 'instructor')
        correo_sesion = (session.get('correo') or '').strip().lower()
        usuario_local = Usuario.query.filter_by(email=correo_sesion).first() if correo_sesion else None
        if not usuario_local:
            usuario_local = Usuario.query.filter_by(username=_username_seguro(username_sesion)).first()
        if not usuario_local:
            temp_password = secrets.token_urlsafe(24)
            usuario_local = Usuario(
                username=_username_seguro(username_sesion),
                password_hash=bcrypt.generate_password_hash(temp_password, rounds=BCRYPT_ROUNDS).decode('utf-8'),
                rol='instructor',
                nombre=username_sesion,
                email=correo_sesion or None,
                debe_cambiar_password=False,
            )
            db.session.add(usuario_local)
            db.session.commit()
        session['usuario_id'] = usuario_local.id

    from flask import current_app

    # Manejar evidencias (múltiples archivos)
    evidencias = request.files.getlist('evidencia')
    archivos_guardados = []
    evidencia_ruta = ''

    if evidencias and evidencias[0].filename:
        upload_folder = os.path.join(current_app.root_path, 'static', 'evidencias')
        os.makedirs(upload_folder, exist_ok=True)
        for evidencia in evidencias:
            if evidencia and evidencia.filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{evidencia.filename}"
                evidencia.save(os.path.join(upload_folder, filename))
                archivos_guardados.append(f"evidencias/{filename}")
        evidencia_ruta = ','.join(archivos_guardados)

    # Manejar firma
    firma = request.files.get('firma')
    firma_ruta = ''
    if firma and firma.filename:
        upload_folder = os.path.join(current_app.root_path, 'static', 'firmas')
        os.makedirs(upload_folder, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"firma_{timestamp}_{firma.filename}"
        firma.save(os.path.join(upload_folder, filename))
        firma_ruta = f"firmas/{filename}"

    try:
        falla = Falla(
            instructor_id=usuario_local.id,
            nombre_instructor=nombre_instructor,
            cedula_instructor=cedula_instructor,
            correo_instructor=session.get('correo', ''),
            nombre_ficha=nombre_ficha,
            numero_ficha=numero_ficha,
            nombre_aprendiz=nombre_aprendiz,
            documento_aprendiz=documento_aprendiz,
            correo_aprendiz=correo_aprendiz,
            telefono_aprendiz=telefono_aprendiz,
            descripcion_faltas=descripcion_faltas,
            fecha_falta=fecha_falta_date,
            evidencia=evidencia_ruta,
            firma=firma_ruta,
        )
        db.session.add(falla)
        db.session.commit()
        flash('Falla registrada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar la falla: {str(e)}', 'error')

    return redirect(url_for('auth.vista_registrar_falla'))


@auth_bp.route('/generar-formato/<int:falla_id>')
def generar_formato(falla_id):
    """Generar formato PDF de comité para una falla"""
    print(f'[PDF] Iniciar generar_formato falla_id={falla_id}')
    print(f'[PDF] Session keys: {list(session.keys())}')
    if 'usuario_id' not in session and 'username' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))
    
    rol = session.get('rol', session.get('rol_real', '')).lower()
    print(f'[PDF] Rol del usuario: {rol}')
    if rol not in ['super admin', 'administrador']:
        print(f'[PDF] Acceso denegado para rol: {rol}')
        flash('No tiene permisos para generar PDFs', 'error')
        return redirect(url_for('auth.dashboard'))

    falla = Falla.query.get_or_404(falla_id)
    print(f'[PDF] Generando PDF para falla: {falla_id}')

    try:
        print('[PDF] Cargando plantilla...')
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'FORMATO COMITE.docx')
        print(f'[PDF] Template path: {template_path}')
        print(f'[PDF] Template exists: {os.path.exists(template_path)}')
        doc = Document(template_path)
        print('[PDF] Plantilla cargada')

        print('[PDF] Haciendo reemplazos...')
        replacements = {
            '[FECHA]': formatear_fecha_larga(falla.fecha_falta) if falla.fecha_falta else '',
            '[NOMBRE INSTRUCTOR]': falla.nombre_instructor,
            '[NUMERO DECEDULA]': falla.cedula_instructor,
            '[NOMBRE FICHA]': falla.nombre_ficha or '',
            '[NUMERO FICHA]': falla.numero_ficha or '',
            '[NOMBRE APRENDIZ]': falla.nombre_aprendiz,
            '[CEDULA APREDIZ]': falla.documento_aprendiz or '',
            '[CORREO APRENDIZ]': falla.correo_aprendiz or '',
            '[TELEFONO APREDIZ]': falla.telefono_aprendiz or '',
            '[TELEFONO APRENDIZ]': falla.telefono_aprendiz or '',
            'Descripcion de Faltas': 'Descripcion de Faltas: ' + (falla.descripcion_faltas or ''),
            'Descripción de Faltas': 'Descripción de Faltas: ' + (falla.descripcion_faltas or ''),
            'Evidencia Fotografica': 'Evidencia Fotografica',
            'Evidencia Fotográfica': 'Evidencia Fotográfica',
            'Quien presenta la queja y/o informe por la firma': 'Quien presenta la queja y/o informe por la firma',
            'Firma del Instructor': 'Firma del Instructor',
            '[firma]': 'Firma del Instructor',
        }
        print('[PDF] Ejecutando _replace_placeholders_doc...')
        import threading
        import time
        
        result = [None]
        error = [None]
        
        def do_replace():
            try:
                _replace_placeholders_doc(doc, replacements)
                result[0] = 'done'
            except Exception as e:
                error[0] = str(e)
        
        thread = threading.Thread(target=do_replace)
        thread.daemon = True
        thread.start()
        thread.join(timeout=15)
        
        if thread.is_alive():
            print('[PDF] _replace_placeholders_doc timeout!')
            flash('Error: timeout al generar PDF', 'error')
            return redirect(url_for('auth.vista_historial'))
        elif error[0]:
            print(f'[PDF] Error en replace: {error[0]}')
            flash(f'Error al generar PDF: {error[0]}', 'error')
            return redirect(url_for('auth.vista_historial'))
        
        print('[PDF] Reemplazos hechos')

        # Agregar evidencias fotográficas sin sobrescribir el texto del párrafo
        print(f'[PDF] evidencia: {falla.evidencia}')
        if falla.evidencia:
            evidencia_paths = falla.evidencia.split(',')
            print(f'[PDF] evidencia_paths: {evidencia_paths}')
            for paragraph in doc.paragraphs:
                text = paragraph.text
                if 'Evidencia Fotográfica' in text or 'Evidencia Fotografica' in text:
                    print(f'[PDF] Encontrado párrafo Evidencia: "{text[:50]}"')
                    _replace_in_paragraph(paragraph, {'Evidencia Fotográfica': '', 'Evidencia Fotografica': ''})
                    for ev_path in evidencia_paths:
                        if ev_path.strip():
                            full_path = os.path.join(os.path.dirname(__file__), '..', 'static', ev_path.strip())
                            print(f'[PDF] evapor full_path: {full_path}')
                            print(f'[PDF] evapor existe: {os.path.exists(full_path)}')
                            if os.path.exists(full_path):
                                try:
                                    paragraph.add_run().add_break()
                                    run = paragraph.add_run()
                                    run.add_picture(full_path, width=Inches(4.0))
                                    paragraph.add_run().add_break()
                                    paragraph.add_run().add_break()
                                except Exception:
                                    paragraph.add_run(f"[Evidencia: {os.path.basename(full_path)}]\n\n")
                    break
                    for ev_path in evidencia_paths:
                        if ev_path.strip():
                            full_path = os.path.join(os.path.dirname(__file__), '..', 'static', ev_path.strip())
                            if os.path.exists(full_path):
                                try:
                                    paragraph.add_run().add_break()
                                    run = paragraph.add_run()
                                    run.add_picture(full_path, width=Inches(4.0))
                                    paragraph.add_run().add_break()
                                    paragraph.add_run().add_break()
                                except Exception:
                                    paragraph.add_run(f"[Evidencia: {os.path.basename(full_path)}]\n\n")
                    break

        # Agregar firma preservando el formato del párrafo
        print(f'[PDF] firma: {falla.firma}')
        if falla.firma:
            full_path = os.path.join(os.path.dirname(__file__), '..', 'static', falla.firma.strip())
            print(f'[PDF] firma full_path: {full_path}')
            print(f'[PDF] firma existe: {os.path.exists(full_path)}')
            if os.path.exists(full_path):
                for paragraph in doc.paragraphs:
                    text = paragraph.text
                    if 'Quien presenta la queja y/o informe por la firma' in text:
                        print(f'[PDF] Encontrado firma: "{text[:50]}"')
                        _replace_in_paragraph(paragraph, {'Quien presenta la queja y/o informe por la firma': ''})
                        try:
                            paragraph.add_run().add_break()
                            run = paragraph.add_run()
                            run.add_picture(full_path, width=Inches(2.0))
                        except Exception:
                            paragraph.add_run(f"[Firma: {os.path.basename(full_path)}]")
                        break
                    elif 'Firma del Instructor' in text or '[firma]' in text:
                        print(f'[PDF] Encontrado Firma del Instructor: "{text[:50]}"')
                        _replace_in_paragraph(paragraph, {'Firma del Instructor': '', '[firma]': ''})
                        try:
                            paragraph.add_run().add_break()
                            run = paragraph.add_run()
                            run.add_picture(full_path, width=Inches(2.0))
                        except Exception:
                            paragraph.add_run(f"[Firma: {os.path.basename(full_path)}]")
                        break

        import tempfile
        import uuid
        temp_dir = tempfile.gettempdir()
        temp_docx = os.path.join(temp_dir, f'formato_comite_{falla_id}_{uuid.uuid4().hex}.docx')
        temp_pdf = os.path.join(temp_dir, f'formato_comite_{falla_id}_{uuid.uuid4().hex}.pdf')
        doc.save(temp_docx)
        
        print(f'[PDF] DOCX guardado, intentando convertir a PDF...')

        return _enviar_pdf_siempre(
            temp_docx=temp_docx,
            temp_pdf=temp_pdf,
            download_name=f'formato_comite_{falla.numero_ficha}_{falla.nombre_aprendiz.replace(" ", "_")}.pdf',
            doc_para_respaldo=doc,
            titulo_respaldo='Formato comite generado',
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error al generar el formato: {str(e)}', 'error')
        return redirect(url_for('auth.vista_historial'))