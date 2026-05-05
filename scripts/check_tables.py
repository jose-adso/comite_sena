from app import app
from models.database import db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print('Tablas en la base de datos:')
    for table in tables:
        print(f'  - {table}')
    
    # Check specifically for grabacion
    if 'grabacion' in tables:
        print('\n✅ Tabla grabacion existe')
    else:
        print('\n❌ Tabla grabacion NO existe')
