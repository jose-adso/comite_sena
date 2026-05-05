from models.database import db
from datetime import datetime

class Grabacion(db.Model):
    """Modelo para grabaciones de reuniones"""
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    duracion = db.Column(db.Integer, default=0)
    hora_inicio = db.Column(db.DateTime, nullable=True)
    audio_path = db.Column(db.String(500), nullable=True)
    transcripcion = db.Column(db.Text, nullable=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('reclamo.id'), nullable=True)
    falla_id = db.Column(db.Integer, db.ForeignKey('falla.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.now)
    
    usuario = db.relationship('Usuario', backref='grabaciones')
    claim = db.relationship('Reclamo', backref='grabaciones')
    falla = db.relationship('Falla', backref='grabaciones')
    
    def __repr__(self):
        return f'<Grabacion {self.id} - {self.titulo}>'