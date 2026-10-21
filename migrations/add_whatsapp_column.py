"""
Migración: Agregar columna can_use_whatsapp a tabla users

Ejecutar en producción:
    python migrations/add_whatsapp_column.py
"""
import os
import sys
from sqlalchemy import inspect, text, create_engine

# Agregar el directorio padre al path para importar core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import DATABASE_URL, IS_POSTGRES

def run_migration():
    """Agrega la columna can_use_whatsapp si no existe."""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('users')]
        
        if 'can_use_whatsapp' in columns:
            print("✓ Columna 'can_use_whatsapp' ya existe")
            return
        
        print("→ Agregando columna 'can_use_whatsapp' a tabla 'users'...")
        
        if IS_POSTGRES:
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN can_use_whatsapp BOOLEAN DEFAULT FALSE NOT NULL;
            """))
        else:
            # SQLite
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN can_use_whatsapp BOOLEAN DEFAULT 0 NOT NULL;
            """))
        
        conn.commit()
        print("✓ Columna 'can_use_whatsapp' agregada exitosamente")

if __name__ == "__main__":
    run_migration()
