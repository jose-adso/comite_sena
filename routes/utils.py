import os
import re
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
ROLES_ALTERNABLES = ['admin', 'administrador', 'instructor', 'planta']


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
    if len(password) < 12:
        return False, "La contraseña debe tener al menos 12 caracteres"
    if len(re.findall(r'[A-Z]', password)) < 2:
        return False, "La contraseña debe contener al menos 2 letras mayúsculas"
    if len(re.findall(r'[a-z]', password)) < 2:
        return False, "La contraseña debe contener al menos 2 letras minúsculas"
    if len(re.findall(r'\d', password)) < 2:
        return False, "La contraseña debe contener al menos 2 números"
    if len(re.findall(r'[!@#$%^&*(),.?\":{}|<>_~\-]', password)) < 2:
        return False, "La contraseña debe contener al menos 2 caracteres especiales (!@#$%^&*(),.?\":{}|<>_-)"
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
    return get_rol_activo() in ['admin', 'administrador', 'planta']


def es_super_o_admin():
    return get_rol_activo() in ['admin', 'administrador']


def es_docente():
    return get_rol_activo() in ['instructor']


def get_rol_activo():
    rol_real = (session.get('rol') or '').strip().lower()
    if rol_real == 'admin':
        return (session.get('rol_activo') or rol_real).strip().lower()
    return rol_real


def puede_cambiar_rol():
    return (session.get('rol') or '').strip().lower() == 'admin'








def etiqueta_rol_visible():
    return get_rol_activo()


def normalizar_rol_externo(usuario_row):
    rol = (usuario_row.get('rol') or usuario_row.get('role') or '').strip().lower()
    if rol in ['admin', 'administrador', 'planta', 'instructor']:
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


def _convertir_con_libreoffice(temp_docx, temp_pdf):
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
        return False, str(e)

    if result.returncode != 0:
        detalle = (result.stderr or result.stdout or '').strip()
        return False, detalle or f'LibreOffice retorno codigo {result.returncode}'

    if not os.path.exists(pdf_generado_path) or os.path.getsize(pdf_generado_path) == 0:
        return False, 'LibreOffice no genero un PDF valido.'

    if os.path.abspath(pdf_generado_path) != os.path.abspath(temp_pdf):
        os.replace(pdf_generado_path, temp_pdf)

    return True, None


def _replace_in_paragraph(paragraph, replacements):
    if not paragraph.runs:
        return
    for run in paragraph.runs:
        texto_original = run.text
        texto_actualizado = texto_original
        for placeholder, value in replacements.items():
            texto_actualizado = texto_actualizado.replace(placeholder, str(value))
        if texto_actualizado != texto_original:
            run.text = texto_actualizado

    texto_post_runs = ''.join(run.text for run in paragraph.runs)
    texto_fallback = texto_post_runs
    for placeholder, value in replacements.items():
        texto_fallback = texto_fallback.replace(placeholder, str(value))

    if texto_fallback != texto_post_runs:
        for run in paragraph.runs:
            run.text = ''
        paragraph.runs[0].text = texto_fallback


def _replace_placeholders_doc(doc, replacements):
    for paragraph in doc.paragraphs:
        _replace_in_paragraph(paragraph, replacements)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _replace_in_paragraph(paragraph, replacements)


def _enviar_pdf_siempre(temp_docx, temp_pdf, download_name, doc_para_respaldo, titulo_respaldo):
    conversion_error = None
    for _ in range(3):
        try:
            from docx2pdf import convert
            convert(temp_docx, temp_pdf)
            if os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0:
                return send_file(
                    temp_pdf, as_attachment=True,
                    download_name=download_name, mimetype='application/pdf',
                )
        except Exception as e:
            conversion_error = e

    ok_libreoffice, detalle_libreoffice = _convertir_con_libreoffice(temp_docx, temp_pdf)
    if ok_libreoffice:
        return send_file(
            temp_pdf, as_attachment=True,
            download_name=download_name, mimetype='application/pdf',
        )

    # Intentar crear PDF de respaldo como última opción
    try:
        _crear_pdf_respaldo_desde_doc(doc_para_respaldo, temp_pdf, titulo_respaldo)
        if os.path.exists(temp_pdf) and os.path.getsize(temp_pdf) > 0:
            return send_file(
                temp_pdf, as_attachment=True,
                download_name=download_name, mimetype='application/pdf',
            )
    except Exception as respaldo_error:
        pass
    
    # Si todo falla, mostrar error en lugar de enviar DOCX
    raise RuntimeError(
        f'No fue posible convertir a PDF. docx2pdf error: {conversion_error}. LibreOffice: {ok_libreoffice}'
    )
