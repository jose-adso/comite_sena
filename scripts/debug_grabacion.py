from app import app
from models.database import db
from models.grabacion import Grabacion

with app.app_context():
    g = Grabacion.query.get(2)
    if g:
        print(f"ID: {g.id}")
        print(f"Título: {g.titulo}")
        print(f"Transcripción: {repr(g.transcripcion[:200] if g.transcripcion else 'VACÍA')}")
        print(f"Audio path: {g.audio_path}")
    else:
        print("Grabación ID 2 no encontrada")
