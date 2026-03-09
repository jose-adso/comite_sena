from models.database import db

class Usuario(db.Model):
    """Modelo de Usuario para la base de datos"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    rol = db.Column(db.String(20), default='usuario')
    nombre = db.Column(db.String(100), nullable=True)
    apellido = db.Column(db.String(100), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    debe_cambiar_password = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    token_recuperacion = db.Column(db.String(32), nullable=True)
    token_expiracion = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Usuario {self.username}>'
