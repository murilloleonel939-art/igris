#!/usr/bin/env python3
"""
Script para crear un usuario de prueba.
Uso: python create_test_user.py [username] [password]
Por defecto: test / test123
"""

import sys
sys.path.insert(0, '/home/dsh/igrisfase3')

from core.database import SessionLocal, User, init_db
from core.auth import hash_password

def create_test_user(username: str = "test", password: str = "test123"):
    init_db()
    
    db = SessionLocal()
    try:
        # Verificar si ya existe
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"❌ Usuario '{username}' ya existe")
            return False
        
        # Crear nuevo usuario
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            is_admin=False,
            can_use_homeassistant=True,
        )
        db.add(user)
        db.commit()
        
        print(f"✅ Usuario '{username}' creado exitosamente")
        print(f"   Contraseña: {password}")
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "test"
    password = sys.argv[2] if len(sys.argv) > 2 else "test123"
    create_test_user(username, password)
