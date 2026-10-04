"""
Base de datos - Modelos de usuarios, perfiles y configuración 2FA
PostgreSQL para EC2 (Coolify), SQLite para RPi (fallback)
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Detectar si estamos en modo local (RPi/desarrollo) o producción (EC2)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./igris.db"  # Fallback a SQLite local
)

# Para PostgreSQL en Coolify, espera: postgresql://user:pass@host:5432/db
if not DATABASE_URL.startswith("sqlite"):
    # PostgreSQL
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """Modelo de usuario con autenticación"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    two_fa = relationship("TwoFactorAuth", back_populates="user", uselist=False, cascade="all, delete-orphan")
    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")
    ai_config = relationship("AIConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")


class TwoFactorAuth(Base):
    """Google Authenticator - 2FA"""
    __tablename__ = "two_factor_auth"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    secret_key = Column(String(255), nullable=False)  # Base32 encoded
    is_enabled = Column(Boolean, default=False)
    backup_codes = Column(JSON, default=[])  # Lista de códigos de respaldo
    created_at = Column(DateTime, default=datetime.utcnow)
    last_verified = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="two_fa")


class Profile(Base):
    """Perfil autorizado para comandos de voz"""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)  # Nombre/alias del perfil
    voice_print = Column(String(255), nullable=True)  # Huella de voz (futuro)
    is_authorized = Column(Boolean, default=True)
    can_execute_commands = Column(Boolean, default=True)
    can_manage_users = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profiles")


class AIConfig(Base):
    """Configuración de proveedores AI por usuario"""
    __tablename__ = "ai_config"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    primary_provider = Column(String(50), default="groq")  # groq, openai, anthropic, local
    fallback_chain = Column(JSON, default=["groq", "openai", "anthropic", "local"])
    stt_provider = Column(String(50), default="local")  # local, openai
    tts_provider = Column(String(50), default="local")  # local, edge-tts
    stt_model = Column(String(50), default="tiny")  # tiny, base, small, medium, large
    system_prompt = Column(Text, default="Eres un asistente IA útil y respetuoso.")
    timezone = Column(String(50), default="America/Bogota")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="ai_config")


class Session(Base):
    """Sesiones activas de usuario (para cerrar sesión desde múltiples dispositivos)"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)


# Crear tablas
def init_db():
    """Inicializar base de datos"""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos inicializada")


def get_db():
    """Dependency para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
