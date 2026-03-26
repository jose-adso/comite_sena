from models.database import db
from datetime import datetime


TIPOS_RECLAMO = [
    'Inasistencia injustificada',
    'Error en evaluación',
    'Conflicto con aprendiz',
    'Problema administrativo',
    'Falta de material o recursos',
    'Incumplimiento de normas',
    'Otro',
]

ESTADOS_RECLAMO = ['Pendiente', 'En revisión', 'Resuelto', 'Rechazado']


class Reclamo(db.Model):
    __tablename__ = 'reclamo'

    id = db.Column(db.Integer, primary_key=True)

    # FK al instructor que lo registra
    instructor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    instructor = db.relationship('Usuario', backref='reclamos')

    # Datos del instructor (redundantes para histórico)
    nombre_instructor = db.Column(db.String(100), nullable=False)
    cedula_instructor = db.Column(db.String(20), nullable=False)
    correo_instructor = db.Column(db.String(120), nullable=False)

    # Datos del aprendiz referenciado
    nombre_aprendiz = db.Column(db.String(100), nullable=False)
    documento_aprendiz = db.Column(db.String(20), nullable=False)
    nombre_ficha = db.Column(db.String(100), nullable=False)
    numero_ficha = db.Column(db.String(20), nullable=False)

    # Contenido del reclamo
    tipo_reclamo = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    fecha_incidente = db.Column(db.Date, nullable=False)

    # Evidencia adjunta (ruta del archivo)
    evidencia = db.Column(db.String(500), nullable=True)

    # Seguimiento
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')
    observacion_admin = db.Column(db.Text, nullable=True)

    fecha_registro = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Reclamo {self.id} - {self.nombre_instructor}>'
