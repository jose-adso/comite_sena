import os
import re
import sys
import secrets
import smtplib
import textwrap
import shutil
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
from werkzeug.security import check_password_hash as wz_check_password_hash
from flask import session, flash, send_file, current_app

from models.database import db, bcrypt
from models.usuario import Usuario

load_dotenv()

PATRONES_COMUNES = [
    'password', 'contraseña', '123456', 'qwerty', 'abc123',
    'admin', 'sena', 'usuario', '111111', 'letmein',
]
BCRYPT_ROUNDS = 14
ROLES_ALTERNABLES = ['super admin', 'administrador', 'instructor', 'planta']


def roles_disponibles_para_usuario():
    rol_real = (session.get('rol_real') or session.get('rol') or '').strip().lower()

    if rol_real == 'super admin' or rol_real.startswith('super'):
        return ['super admin', 'administrador', 'instructor', 'planta']
    if rol_real == 'administrador':
        return ['administrador', 'instructor', 'planta']
    if rol_real in ROLES_ALTERNABLES:
        return [rol_real]
    return ['instructor']


# ── Email ─────────────────────────────────────────────────────────────────────
def enviar_email(destinatario, asunto, cuerpo):
    try:
        smtp_email = (current_app.config.get('SMTP_EMAIL') or os.getenv('SMTP_EMAIL', '')).strip()
        smtp_password = (current_app.config.get('SMTP_PASSWORD') or os.getenv('SMTP_PASSWORD', '')).strip().replace(' ', '')
        smtp_server = (current_app.config.get('SMTP_SERVER') or os.getenv('SMTP_SERVER', 'smtp.gmail.com')).strip()
        smtp_port = int(current_app.config.get('SMTP_PORT') or os.getenv('SMTP_PORT', '587'))

        if not smtp_email or not smtp_password:
            print('Error al enviar email: faltan SMTP_EMAIL/SMTP_PASSWORD en variables de entorno')
            return False

        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'html'))
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False


# ── Autenticación local SQLite ───────────────────────────────────────────────
def get_external_user_by_username(username):
    username = (username or '').strip()
    if not username:
        return None

    usuario = Usuario.query.filter(
        db.or_(
            Usuario.username == username,
            Usuario.email == username.lower(),
        )
    ).first()

    if not usuario:
        return None

    return {
        'id': usuario.id,
        'username': usuario.username,
        'nombre': usuario.nombre,
        'email': usuario.email,
        'correo': usuario.email,
        'rol': usuario.rol,
        'debe_cambiar_password': usuario.debe_cambiar_password,
        'password_hash': usuario.password_hash,
    }


# ── Contraseñas ───────────────────────────────────────────────────────────────
def password_matches(raw_password, user_row):
    stored_hash = user_row.get('password_hash') or user_row.get('_password_hash')
    stored_password = user_row.get('password')

    if stored_hash:
        try:
            return bcrypt.check_password_hash(stored_hash, raw_password)
        except Exception:
            pass
        try:
            return wz_check_password_hash(stored_hash, raw_password)
        except Exception:
            pass

    if stored_password:
        return stored_password == raw_password

    return False


def validar_password(password):
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    if len(re.findall(r'[A-Z]', password)) < 1:
        return False, "La contraseña debe contener al menos 1 letra mayúscula"
    if len(re.findall(r'[a-z]', password)) < 1:
        return False, "La contraseña debe contener al menos 1 letra minúscula"
    if len(re.findall(r'\d', password)) < 1:
        return False, "La contraseña debe contener al menos 1 número"
    if len(re.findall(r'[!@#$%^&*(),.?\":{}|<>_~\-]', password)) < 1:
        return False, "La contraseña debe contener al menos 1 carácter especial (!@#$%^&*(),.?\":{}|<>_~-)"
    if re.search(r'(.)\1{2,}', password):
        return False, "La contraseña no puede tener 3 o más caracteres iguales consecutivos"
    password_lower = password.lower()
    for patron in PATRONES_COMUNES:
        if patron in password_lower:
            return False, "La contraseña no puede contener palabras comunes"
    return True, ""


def password_ya_usada(usuario, nueva_password):
    if bcrypt.check_password_hash(usuario.password_hash, nueva_password):
        return True
    for hash_anterior in usuario.get_historial():
        if bcrypt.check_password_hash(hash_anterior, nueva_password):
            return True
    return False


# ── Roles / sesión ────────────────────────────────────────────────────────────
def es_admin():
    return get_rol_activo() in ['administrador', 'planta', 'super admin']


def es_super_o_admin():
    return get_rol_activo() in ['administrador', 'super admin']


def es_docente():
    return get_rol_activo() in ['instructor']


def get_rol_activo():
    rol_activo = session.get('rol_activo')
    if rol_activo:
        return rol_activo.strip().lower()
    return session.get('rol_real') or session.get('rol') or 'instructor'


def puede_cambiar_rol():
    return len(roles_disponibles_para_usuario()) > 1








def etiqueta_rol_visible():
    return get_rol_activo()


def normalizar_rol_externo(usuario_row):
    rol = (usuario_row.get('rol') or usuario_row.get('role') or '').strip().lower()
    if rol in ['super admin', 'administrador', 'planta', 'instructor']:
        return rol
    return 'instructor'


def _username_seguro(valor):
    base = re.sub(r'[^a-zA-Z0-9_.-]+', '_', (valor or '').strip().lower())
    return base.strip('_') or 'usuario'


# ── PDF helpers (compartidos entre instructor y notificaciones) ──────────────────
def _crear_pdf_respaldo_desde_doc(doc, pdf_path, titulo='Documento generado'):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(pdf_path, pagesize=LETTER)
    width, height = LETTER
    y = height - 40
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, titulo)
    y -= 22
    c.setFont('Helvetica', 10)

    def escribir_linea(texto):
        nonlocal y
        if not texto:
            return
        lineas = textwrap.wrap(str(texto), width=100) or ['']
        for linea in lineas:
            if y < 50:
                c.showPage()
                c.setFont('Helvetica', 10)
                y = height - 40
            c.drawString(40, y, linea)
            y -= 14

    for paragraph in doc.paragraphs:
        texto = ' '.join((paragraph.text or '').split())
        if texto:
            escribir_linea(texto)

    for table in doc.tables:
        for row in table.rows:
            celdas = [' '.join((cell.text or '').split()) for cell in row.cells]
            texto_fila = ' | '.join([c for c in celdas if c])
            if texto_fila:
                escribir_linea(texto_fila)

    c.save()


def _archivo_generado_valido(path_archivo):
    try:
        return os.path.exists(path_archivo) and os.path.getsize(path_archivo) > 0
    except OSError:
        return False


def _convertir_con_docx2pdf(temp_docx, temp_pdf, timeout=60):
    """Convertir DOCX a PDF usando docx2pdf en un subproceso con timeout."""
    import traceback
    if not os.path.exists(temp_docx):
        return False, f'El archivo DOCX no existe: {temp_docx}'

    docx_size = os.path.getsize(temp_docx)
    print(f'[PDF] docx2pdf: convirtiendo {temp_docx} ({docx_size} bytes) -> {temp_pdf}')

    script = (
        "import os\n"
        "import sys\n"
        "from docx2pdf import convert\n"
        f"temp_docx = r\"{temp_docx}\"\n"
        f"temp_pdf = r\"{temp_pdf}\"\n"
        "try:\n"
        "    convert(temp_docx, temp_pdf)\n"
        "    print('CONVERSION_DONE', file=sys.stderr)\n"
        "except Exception as e:\n"
        "    print(f'ERROR: {e}', file=sys.stderr)\n"
        "    if not (os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0):\n"
        "        raise\n"
    )

    try:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

        run_kwargs = {
            'capture_output': True,
            'text': True,
            'timeout': timeout,
            'check': False,
        }
        if os.name == 'nt' and hasattr(subprocess, 'CREATE_NO_WINDOW'):
            run_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        result = subprocess.run([sys.executable, '-c', script], **run_kwargs)
        
        if result.stdout:
            print(f'[PDF] docx2pdf stdout: {result.stdout[:500]}')
        if result.stderr:
            print(f'[PDF] docx2pdf stderr: {result.stderr[:1000]}')
            
    except subprocess.TimeoutExpired:
        print(f'[PDF] docx2pdf timeout después de {timeout}s')
        if _archivo_generado_valido(temp_pdf):
            return True, f'docx2pdf tardó más de {timeout}s, pero el PDF sí fue generado.'
        return False, f'docx2pdf excedió el tiempo límite de {timeout}s.'
    except Exception as e:
        print(f'[PDF] docx2pdf exception: {e}')
        traceback.print_exc()
        if _archivo_generado_valido(temp_pdf):
            return True, f'PDF generado con advertencia: {str(e)}'
        return False, f'Error al convertir: {str(e)}'

    if _archivo_generado_valido(temp_pdf):
        print(f'[PDF] docx2pdf exitoso: {os.path.getsize(temp_pdf)} bytes')
        detalle = (result.stderr or result.stdout or '').strip()
        return True, detalle or None

    print(f'[PDF] docx2pdf falló - PDF no generado. returncode={result.returncode}')
    if result.returncode != 0:
        detalle = (result.stderr or result.stdout or '').strip()
        return False, detalle or f'docx2pdf retornó código {result.returncode}'

    return False, 'docx2pdf no generó el archivo PDF'


def _convertir_con_libreoffice(temp_docx, temp_pdf):
    print(f'[PDF] LibreOffice: convirtiendo {temp_docx} -> {temp_pdf}')
    soffice_cmd = shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice_cmd:
        return False, 'LibreOffice no esta disponible en el sistema.'

    output_dir = os.path.dirname(temp_pdf)
    nombre_pdf_generado = f"{os.path.splitext(os.path.basename(temp_docx))[0]}.pdf"
    pdf_generado_path = os.path.join(output_dir, nombre_pdf_generado)

    try:
        if os.path.exists(pdf_generado_path):
            os.remove(pdf_generado_path)
        result = subprocess.run(
            [soffice_cmd, '--headless', '--convert-to', 'pdf', '--outdir', output_dir, temp_docx],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except Exception as e:
        print(f'[PDF] LibreOffice exception: {e}')
        return False, str(e)

    print(f'[PDF] LibreOffice returncode: {result.returncode}')
    if result.returncode != 0:
        detalle = (result.stderr or result.stdout or '').strip()
        print(f'[PDF] LibreOffice error: {detalle}')
        return False, detalle or f'LibreOffice retorno codigo {result.returncode}'

    if not os.path.exists(pdf_generado_path) or os.path.getsize(pdf_generado_path) == 0:
        return False, 'LibreOffice no genero un PDF valido.'

    if os.path.abspath(pdf_generado_path) != os.path.abspath(temp_pdf):
        os.replace(pdf_generado_path, temp_pdf)

    print(f'[PDF] LibreOffice exitoso: {os.path.getsize(temp_pdf)} bytes')
    return True, None


def _replace_in_paragraph(paragraph, replacements):
    if not paragraph.runs:
        return

    for placeholder, value in replacements.items():
        replacement = '' if value is None else str(value)
        
        for run in paragraph.runs:
            if run.text and placeholder in run.text:
                run.text = run.text.replace(placeholder, replacement)


def _replace_placeholders_in_container(container, replacements):
    for paragraph in getattr(container, 'paragraphs', []):
        _replace_in_paragraph(paragraph, replacements)

    for table in getattr(container, 'tables', []):
        for row in table.rows:
            for cell in row.cells:
                _replace_placeholders_in_container(cell, replacements)


def _replace_placeholders_doc(doc, replacements):
    _replace_placeholders_in_container(doc, replacements)

    for section in getattr(doc, 'sections', []):
        _replace_placeholders_in_container(section.header, replacements)
        _replace_placeholders_in_container(section.footer, replacements)


def _enviar_pdf_siempre(temp_docx, temp_pdf, download_name, doc_para_respaldo, titulo_respaldo):
    print(f'[PDF] ===== INICIANDO _enviar_pdf_siempre =====')
    print(f'[PDF] download_name: {download_name}')
    print(f'[PDF] temp_docx: {temp_docx}, existe: {os.path.exists(temp_docx)}')
    print(f'[PDF] temp_pdf: {temp_pdf}')
    
    ok_docx2pdf, detalle_docx2pdf = _convertir_con_docx2pdf(temp_docx, temp_pdf)
    print(f'[PDF] docx2pdf result: ok={ok_docx2pdf}, detalle={detalle_docx2pdf}')
    if ok_docx2pdf:
        print(f'[PDF] Enviando PDF via docx2pdf')
        return send_file(
            temp_pdf, as_attachment=True,
            download_name=download_name, mimetype='application/pdf',
        )

    print(f'⚠️ docx2pdf no disponible para {download_name}: {detalle_docx2pdf}')

    ok_libreoffice, detalle_libreoffice = _convertir_con_libreoffice(temp_docx, temp_pdf)
    print(f'[PDF] LibreOffice result: ok={ok_libreoffice}, detalle={detalle_libreoffice}')
    if ok_libreoffice:
        print(f'[PDF] Enviando PDF via LibreOffice')
        return send_file(
            temp_pdf, as_attachment=True,
            download_name=download_name, mimetype='application/pdf',
        )

    print(f'⚠️ LibreOffice no disponible para {download_name}: {detalle_libreoffice}')

    # Si la conversión real a PDF falla, entregar el DOCX para conservar el formato.
    try:
        flash(
            'No fue posible convertir a PDF en este entorno. Se descargará el archivo Word para conservar el formato original.',
            'warning',
        )
    except Exception:
        pass

    nombre_docx = f"{os.path.splitext(download_name)[0]}.docx"
    if os.path.exists(temp_docx) and os.path.getsize(temp_docx) > 0:
        print(f'[PDF] Entregando DOCX como fallback')
        return send_file(
            temp_docx,
            as_attachment=True,
            download_name=nombre_docx,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

    raise RuntimeError(
        f'No fue posible convertir a PDF. docx2pdf: {detalle_docx2pdf}. LibreOffice: {detalle_libreoffice}'
    )
