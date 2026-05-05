from app import app
from models.database import db

with app.app_context():
    try:
        db.session.execute(db.text("""
            ALTER TABLE grabacion ADD COLUMN falla_id INTEGER REFERENCES falla(id);
        """))
        db.session.commit()
        print('Columna falla_id agregada')
    except Exception as e:
        print(f'Error: {e}')
        db.session.rollback()