from app import app
from models.database import db

with app.app_context():
    # Agregar columna claim_id a la tabla grabacion
    try:
        db.session.execute(db.text("""
            ALTER TABLE grabacion ADD COLUMN claim_id INTEGER REFERENCES reclamo(id);
        """))
        db.session.commit()
        print('Columna claim_id agregada correctamente')
    except Exception as e:
        print(f'Error: {e}')
        db.session.rollback()