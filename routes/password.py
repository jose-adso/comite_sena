import secrets
from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, flash, session

from models.database import db, bcrypt
from models.usuario import Usuario
from routes.auth import auth_bp
from routes.utils import enviar_email, validar_password, password_ya_usada, BCRYPT_ROUNDS


@auth_bp.route('/recuperar', methods=['POST'])
def recuperar():
    email = request.form.get('rec_email')
    try:
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario is None:
            flash('El email no está registrado', 'error')
            return redirect(url_for('auth.index'))

        token = secrets.token_hex(16)
        expiracion = datetime.now() + timedelta(hours=1)
        try:
            usuario.token_recuperacion = token
            usuario.token_expiracion = expiracion
            db.session.commit()
        except Exception as db_error:
            print(f"ERROR DE BASE DE DATOS: {db_error}")
            db.session.rollback()
            flash('Error al procesar la solicitud. Contacta al administrador.', 'error')
            return redirect(url_for('auth.index'))

        enlace = f"http://127.0.0.1:8080/restablecer/{token}"
        cuerpo = f"""
        <html><body>
            <h1>Recuperación de Contraseña</h1>
            <p>Hola <strong>{usuario.nombre or usuario.username}</strong>,</p>
            <p>Haz clic en el siguiente enlace para crear una nueva contraseña:</p>
            <p><a href="{enlace}">Restablecer mi Contraseña</a></p>
            <p>Este enlace expirará en 1 hora.</p>
        </body></html>
        """
        email_enviado = enviar_email(email, 'Recuperación de Contraseña - Sistema Macro Sena', cuerpo)
        if email_enviado:
            flash(f'Las instrucciones de recuperación han sido enviadas a {email}', 'success')
        else:
            flash('Error al enviar el correo. Contacta al administrador.', 'error')

    except Exception as e:
        print(f"ERROR GENERAL EN RECUPERACIÓN: {e}")
        flash('Error al procesar la solicitud. Contacta al administrador.', 'error')

    return redirect(url_for('auth.index'))


@auth_bp.route('/olvide-password', methods=['GET', 'POST'])
def olvide_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario:
            token = secrets.token_hex(16)
            usuario.token_recuperacion = token
            usuario.token_expiracion = datetime.now() + timedelta(hours=1)
            db.session.commit()

            enlace = url_for('auth.restablecer_password', token=token, _external=True)
            cuerpo = f"""
            <h2>Recuperación de contraseña</h2>
            <p>Hola <strong>{usuario.nombre or usuario.username}</strong>,</p>
            <p>Haz clic en el siguiente enlace (válido por 1 hora):</p>
            <p><a href="{enlace}" style="background:#198754;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
                Restablecer contraseña
            </a></p>
            <p>Si no solicitaste esto, ignora este mensaje.</p>
            """
            enviar_email(email, 'Recuperación de contraseña - Sistema Macro Sena', cuerpo)

        flash('Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'success')
        return redirect(url_for('auth.olvide_password'))

    return render_template('olvide_password.html')


@auth_bp.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer_password(token):
    try:
        usuario = Usuario.query.filter_by(token_recuperacion=token).first()
    except Exception as db_error:
        print(f"ERROR AL BUSCAR USUARIO: {db_error}")
        flash('El enlace de recuperación no es válido', 'error')
        return redirect(url_for('auth.index'))

    if not usuario:
        flash('El enlace de recuperación no es válido', 'error')
        return redirect(url_for('auth.index'))

    if usuario.token_expiracion and usuario.token_expiracion < datetime.now():
        usuario.token_recuperacion = None
        usuario.token_expiracion = None
        db.session.commit()
        flash('El enlace de recuperación ha expirado. Solicita uno nuevo.', 'error')
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')

        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('auth.restablecer_password', token=token))

        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('auth.restablecer_password', token=token))

        if password_ya_usada(usuario, nueva_password):
            flash('No puedes reutilizar una contraseña anterior. Elige una nueva.', 'error')
            return redirect(url_for('auth.restablecer_password', token=token))

        try:
            usuario.agregar_historial(usuario.password_hash)
            usuario.password_hash = bcrypt.generate_password_hash(
                nueva_password, rounds=BCRYPT_ROUNDS
            ).decode('utf-8')
            usuario.token_recuperacion = None
            usuario.token_expiracion = None
            usuario.debe_cambiar_password = False
            db.session.commit()
            flash('Tu contraseña ha sido restablecida exitosamente. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.index'))
        except Exception as update_error:
            print(f"ERROR AL ACTUALIZAR CONTRASEÑA: {update_error}")
            db.session.rollback()
            flash('Error al actualizar la contraseña. Contacta al administrador.', 'error')
            return redirect(url_for('auth.restablecer_password', token=token))

    return render_template('restablecer_password.html', token=token)


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
def cambiar_password():
    if 'usuario_id' not in session:
        flash('Debe iniciar sesión primero', 'error')
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')

        if nueva_password != confirmar_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('auth.cambiar_password'))

        es_valida, mensaje = validar_password(nueva_password)
        if not es_valida:
            flash(mensaje, 'error')
            return redirect(url_for('auth.cambiar_password'))

        usuario = Usuario.query.get(session['usuario_id'])

        if password_ya_usada(usuario, nueva_password):
            flash('No puedes reutilizar una contraseña anterior. Elige una nueva.', 'error')
            return redirect(url_for('auth.cambiar_password'))

        usuario.agregar_historial(usuario.password_hash)
        usuario.password_hash = bcrypt.generate_password_hash(
            nueva_password, rounds=BCRYPT_ROUNDS
        ).decode('utf-8')
        usuario.debe_cambiar_password = False
        db.session.commit()

        flash('Contraseña actualizada exitosamente', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('cambiar_password.html', username=session['username'])
