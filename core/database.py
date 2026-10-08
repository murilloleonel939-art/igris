"""
Base de datos - Modelos de usuarios, perfiles, configuración 2FA, recordatorios y notas
PostgreSQL para EC2 (Coolify), SQLite para RPi (fallback)
"""
import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Integer, BigInteger, Boolean, DateTime, Text,
    ForeignKey, JSON, Index, text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

logger = logging.getLogger(__name__)

# Detectar si estamos en modo local (RPi/desarrollo) o producción (EC2)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./igris.db"  # Fallback a SQLite local
)

# Coolify entrega "postgres://" o "postgresql://"; con psycopg 3 SQLAlchemy necesita el prefijo del driver
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(_prefix):]
        break

IS_POSTGRES = DATABASE_URL.startswith("postgresql")


def _ensure_postgres_database_exists(url: str) -> None:
    """Crea la base de datos si todavía no existe.

    En Coolify el servicio PostgreSQL arranca con una base ya creada, pero si
    DATABASE_URL apunta a un nombre distinto (por ejemplo igris), la conexión
    falla con "database does not exist" y el backend no arranca.

    Se conecta a la base de mantenimiento "postgres" con el mismo usuario y
    ejecuta CREATE DATABASE. Si el usuario no tiene permiso, se avisa y se
    sigue: puede que la base ya exista o que la cree el propio Coolify.
    """
    try:
        parsed = make_url(url)
    except Exception as e:
        logger.warning("No se pudo interpretar DATABASE_URL: %s", e)
        return

    target = parsed.database
    if not target or target == "postgres":
        return

    # Conexión a la base de mantenimiento del mismo servidor
    admin_url = parsed.set(database="postgres")
    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target},
            ).scalar()
            if exists:
                logger.info("Base de datos PostgreSQL '%s' ya existe", target)
            else:
                # El nombre no puede ir como parámetro; se cita como identificador
                safe = target.replace('"', '""')
                conn.execute(text(f'CREATE DATABASE "{safe}"'))
                logger.info("Base de datos PostgreSQL '%s' creada", target)
        admin_engine.dispose()
    except (OperationalError, ProgrammingError) as e:
        logger.warning(
            "No se pudo verificar/crear la base de datos '%s' (%s). "
            "Si la base ya existe o la crea Coolify, esto es normal.",
            target, type(e).__name__,
        )
    except Exception as e:
        logger.warning("Aviso al comprobar la base de datos '%s': %s", target, e)


def _build_engine():
    """Crea el motor, validando la conexión y creando la base si hace falta."""
    if IS_POSTGRES:
        _ensure_postgres_database_exists(DATABASE_URL)

    if IS_POSTGRES:
        # pool_pre_ping: descarta conexiones muertas (Coolify reinicia Postgres
        # sin avisar y, sin esto, la primera petición después falla).
        # pool_recycle: renueva las conexiones cada 30 min.
        return create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=10,
        )

    # SQLite (desarrollo local / RPi)
    return create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    """Ahora en UTC, sin zona horaria (así se guardan todas las fechas de recordatorios)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """Modelo de usuario con autenticación"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    addressing_instruction = Column(Text, nullable=True)  # Instrucción de trato personalizado para Igris
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
    primary_provider = Column(String(50), default="nemotron")  # nemotron, openai, anthropic, local
    fallback_chain = Column(JSON, default=["nemotron", "openai", "anthropic", "local"])
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


class Reminder(Base):
    """Recordatorio de Igris. due_at se guarda en UTC (sin zona); se muestra en hora de Colombia."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(200), nullable=False)
    due_at = Column(DateTime, nullable=False)                    # UTC
    status = Column(String(20), default="pendiente", nullable=False)  # pendiente | enviado | cancelado
    channel = Column(String(20), default="telegram", nullable=False)  # canal de aviso
    chat_id = Column(BigInteger, nullable=True)                  # Telegram de quien lo creó; NULL = todos los autorizados
    repeat = Column(String(20), nullable=True)                   # NULL | diaria | semanal
    attempts = Column(Integer, default=0, nullable=False)        # intentos de envío fallidos
    created_at = Column(DateTime, default=utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_reminders_status_due", "status", "due_at"),)


class Note(Base):
    """Nota de texto libre del usuario"""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


# Crear tablas
def _run_migrations(engine) -> None:
    """Aplica migraciones incrementales: añade columnas nuevas a tablas existentes.

    create_all() no modifica tablas que ya existen, así que cualquier columna
    añadida al modelo después del primer despliegue debe agregarse aquí.
    El patrón es idempotente: comprueba si la columna existe antes de añadirla.
    """
    dialect = engine.dialect.name  # "sqlite" o "postgresql"

    with engine.begin() as conn:
        # ── users.addressing_instruction ────────────────────────────────────
        if dialect == "sqlite":
            rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            existing = {row[1] for row in rows}
            if "addressing_instruction" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN addressing_instruction TEXT"))
                logger.info("Migración aplicada: users.addressing_instruction (sqlite)")
        else:
            # PostgreSQL: information_schema es fiable en todos los proveedores
            row = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='addressing_instruction'"
            )).fetchone()
            if not row:
                conn.execute(text("ALTER TABLE users ADD COLUMN addressing_instruction TEXT"))
                logger.info("Migración aplicada: users.addressing_instruction (postgresql)")


def init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Crea las tablas que falten y valida la conexión.

    En Coolify el backend y PostgreSQL se despliegan a la vez: es normal que
    durante los primeros segundos la base todavía no acepte conexiones. Por eso
    se reintenta con espera creciente en lugar de morir al primer fallo.

    create_all() solo crea lo que falta; no borra ni modifica nada existente.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            # Comprobación real de que la base responde, no solo de que el
            # motor se construyó.
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # Migraciones incrementales: añade columnas nuevas a tablas existentes
            # que create_all() no toca porque la tabla ya existe.
            _run_migrations(engine)

            tables = ", ".join(sorted(Base.metadata.tables))
            logger.info("Base de datos lista (%s). Tablas: %s", engine.dialect.name, tables)
            if engine.dialect.name == "sqlite":
                logger.warning(
                    "Usando SQLite: los datos se pierden en cada despliegue si no "
                    "hay un volumen persistente. Define DATABASE_URL para usar PostgreSQL."
                )
            return
        except Exception as e:
            last_error = e
            if attempt < retries:
                logger.warning(
                    "La base de datos no responde todavía (intento %s/%s): %s. "
                    "Reintentando en %.0fs…",
                    attempt, retries, type(e).__name__, delay,
                )
                time.sleep(delay)

    logger.error(
        "No se pudo preparar la base de datos tras %s intentos: %s",
        retries, last_error,
    )
    # Se lanza para que el despliegue falle de forma visible en lugar de
    # arrancar con una base rota y dar errores raros en cada petición.
    raise last_error if last_error else RuntimeError("Base de datos no disponible")


def get_db():
    """Dependency para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
