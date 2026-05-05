from models.database import db
from datetime import datetime


class Plantilla(db.Model):
    """Modelo para gestionar plantillas DOCX del sistema"""
    __tablename__ = 'plantilla'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True)
    descripcion = db.Column(db.String(500), nullable=True)
    archivo_path = db.Column(db.String(500), nullable=False)
    tipo_uso = db.Column(db.String(50), nullable=True)
    activa = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    # Relación
    creado_por = db.relationship('Usuario', backref='plantillas_creadas')

    def __repr__(self):
        return f'<Plantilla {self.id} - {self.nombre}>'
