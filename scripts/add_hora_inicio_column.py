"""Agrega la columna hora_inicio a la tabla grabacion"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db

with app.app_context():
    # Verificar si la columna ya existe
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('grabacion')]
    
    if 'hora_inicio' not in columns:
        # Agregar la columna
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE grabacion ADD COLUMN hora_inicio TIMESTAMP'))
            conn.commit()
        print('Columna hora_inicio agregada exitosamente')
    else:
        print('La columna hora_inicio ya existe')
