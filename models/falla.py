from models.database import db
from datetime import datetime

class Falla(db.Model):
    """Modelo para registrar fallas de aprendices"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Datos del instructor
    instructor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre_instructor = db.Column(db.String(100), nullable=False)
    cedula_instructor = db.Column(db.String(20), nullable=False)
    correo_instructor = db.Column(db.String(120), nullable=False)
    
    # Datos de la ficha
    nombre_ficha = db.Column(db.String(100), nullable=False)
    numero_ficha = db.Column(db.String(20), nullable=False)
    
    # Datos del aprendiz
    nombre_aprendiz = db.Column(db.String(100), nullable=False)
    documento_aprendiz = db.Column(db.String(20), nullable=False)
    correo_aprendiz = db.Column(db.String(120), nullable=False)
    telefono_aprendiz = db.Column(db.String(20), nullable=False)
    
    # Descripción de la falta
    descripcion_faltas = db.Column(db.Text, nullable=False)
    
    # Fecha de la falta (ingresada por el instructor)
    fecha_falta = db.Column(db.Date, nullable=False)
    
    # Firma del instructor (ruta de la imagen)
    firma = db.Column(db.String(500), nullable=True)
    
    # Evidencia (ruta de la imagen)
    evidencia = db.Column(db.String(500), nullable=True)
    
    # Fecha de registro (automática)
    fecha_registro = db.Column(db.DateTime, default=datetime.now)
    
    # Relación con instructor
    instructor = db.relationship('Usuario', backref='fallas')
    
    def __repr__(self):
        return f'<Falla {self.id} - {self.nombre_aprendiz}>'
