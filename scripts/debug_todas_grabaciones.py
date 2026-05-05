from app import app
from models.database import db
from models.grabacion import Grabacion

with app.app_context():
    grabaciones = Grabacion.query.all()
    print(f"Total grabaciones: {len(grabaciones)}")
    for g in grabaciones:
        print(f"ID: {g.id}, Título: {g.titulo}, Transcripción: {len(g.transcripcion or '')} chars")
