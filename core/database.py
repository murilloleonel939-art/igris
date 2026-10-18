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
    ForeignKey, JSON, Index, UniqueConstraint, text,
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

    # ── Funciones habilitadas (permisos) ────────────────────────────────────
    # Cada columna abre una función de Igris para ese usuario. Los nombres y los
    # valores por defecto viven en core/capabilities.py (FEATURES / DEFAULT_FEATURES);
    # aquí solo se declaran. Hora y clima vienen activos; el resto lo abre el
    # administrador desde el panel.
    can_use_time = Column(Boolean, default=True, nullable=False)
    can_use_weather = Column(Boolean, default=True, nullable=False)
    can_use_email = Column(Boolean, default=False, nullable=False)
    can_use_email_write = Column(Boolean, default=False, nullable=False)
    can_use_calendar = Column(Boolean, default=False, nullable=False)
    can_use_calendar_write = Column(Boolean, default=False, nullable=False)
    can_use_notes = Column(Boolean, default=False, nullable=False)
    can_use_reminders = Column(Boolean, default=False, nullable=False)
    can_use_tuya = Column(Boolean, default=False, nullable=False)
    can_use_device = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    two_fa = relationship("TwoFactorAuth", back_populates="user", uselist=False, cascade="all, delete-orphan")
    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")
    ai_config = relationship("AIConfig", back_populates="user", uselist=False, cascade="all, delete-orphan")
    google_account = relationship("GoogleAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    telegram_link = relationship("TelegramLink", back_populates="user", uselist=False, cascade="all, delete-orphan")
    memories = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")


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
    # El embedding cifrado suele superar los 255 caracteres.
    voice_print = Column(Text, nullable=True)
    is_authorized = Column(Boolean, default=True)
    can_execute_commands = Column(Boolean, default=True)
    can_manage_users = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profiles")


class GlobalSetting(Base):
    """Configuración global persistente de la instalación."""
    __tablename__ = "global_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    """Recordatorio de Igris. due_at se guarda en UTC (sin zona); se muestra en hora de Colombia.

    Cada recordatorio pertenece a UN usuario (user_id). Las filas anteriores a la
    separación por usuario se asignan al administrador en la migración.
    """
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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
    """Nota de texto libre, siempre de un usuario concreto (user_id)."""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class UserMemory(Base):
    """Memoria estructurada de Igris para un usuario.

    kind separa la memoria personal estable de la operativa:
      - personal: preferencias, trato, hábitos y datos estables.
      - operational: pendientes, objetivos, proyectos y decisiones recientes.
    """
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(32), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(32), default="chat", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="memories")

    __table_args__ = (
        Index("ix_user_memories_user_kind_updated", "user_id", "kind", "updated_at"),
        UniqueConstraint("user_id", "kind", "content", name="uq_user_memory_content"),
    )


class GoogleAccount(Base):
    """Cuenta de Google que un usuario ha autorizado (Gmail y Calendar).

    El refresh token va CIFRADO (core/crypto.py): da acceso al correo y al
    calendario y no puede quedar en claro en la base. Un usuario tiene como mucho
    una cuenta; volver a autorizar sustituye la anterior.
    """
    __tablename__ = "google_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True)              # cuenta de Google autorizada
    refresh_token_enc = Column(Text, nullable=False)        # cifrado con core.crypto
    scopes = Column(Text, nullable=True)                    # permisos concedidos, separados por espacios
    last_error = Column(Text, nullable=True)                # último fallo de Google (token revocado, etc.)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="google_account")


class TelegramLink(Base):
    """Vinculación entre un usuario de Igris y su chat de Telegram.

    Se crea en dos pasos: el usuario pide un código en la web y luego envía
    "/start <código>" al bot. Solo entonces se guarda el chat_id. Así nadie puede
    hacerse pasar por otro: el código caduca y es de un solo uso.

    chat_id es NULL mientras el código está pendiente; la restricción UNIQUE
    impide que un mismo chat quede enlazado a dos usuarios.
    """
    __tablename__ = "telegram_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    chat_id = Column(BigInteger, nullable=True, unique=True, index=True)
    link_code = Column(String(32), nullable=True)           # código temporal de vinculación
    code_expires_at = Column(DateTime, nullable=True)
    username = Column(String(100), nullable=True)           # @usuario de Telegram, informativo
    created_at = Column(DateTime, default=utcnow, nullable=False)
    linked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="telegram_link")


# Crear tablas
def _table_exists(conn, dialect: str, table: str) -> bool:
    """¿Existe ya la tabla?

    Hace falta porque init_db() puede llamar a las migraciones en un momento en el
    que las tablas todavía no están: si create_all() falló y se reintenta, la
    primera pasada que salga bien crea las tablas, pero mientras tanto no se puede
    dar por hecho que existen (un ALTER TABLE sobre algo que no está da un error
    que parece un fallo de la base y no lo es).
    """
    if dialect == "sqlite":
        row = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name = :t"),
            {"t": table},
        ).fetchone()
        return row is not None
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t AND table_schema = current_schema()"
        ),
        {"t": table},
    ).fetchone()
    return row is not None


def _column_exists(conn, dialect: str, table: str, column: str) -> bool:
    """¿Existe ya la columna? (create_all no toca tablas que ya existen)."""
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(row[1] == column for row in rows)
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).fetchone()
    return row is not None


def _owner_user_id(conn) -> int:
    """A quién se le asignan los datos anteriores a la separación por usuario.

    Se busca el administrador más antiguo (o, si no hay ninguno marcado como tal,
    el usuario más antiguo). Todo lo que había antes de este cambio pertenecía al
    dueño de la instalación, y ese es el administrador.
    """
    row = conn.execute(text(
        "SELECT id FROM users ORDER BY is_admin DESC, id ASC LIMIT 1"
    )).fetchone()
    return row[0] if row else 0


def _run_migrations(engine) -> None:
    """Aplica migraciones incrementales: añade columnas nuevas a tablas existentes.

    create_all() no modifica tablas que ya existen, así que cualquier columna
    añadida al modelo después del primer despliegue debe agregarse aquí.
    El patrón es idempotente: comprueba si la columna existe antes de añadirla.

    Las columnas de permisos se añaden con DEFAULT para que las filas ya
    existentes queden con un valor válido (en SQLite, añadir una columna NOT NULL
    sin default falla directamente).
    """
    dialect = engine.dialect.name  # "sqlite" o "postgresql"

    with engine.begin() as conn:
        # Si las tablas todavía no existen (create_all acaba de fallar y se está
        # reintentando), no hay nada que migrar: se sale sin error. La siguiente
        # pasada, con las tablas ya creadas, aplicará lo que falte.
        if not _table_exists(conn, dialect, "users"):
            logger.info("Migraciones omitidas: la tabla 'users' todavía no existe")
            return

        # ── profiles.voice_print ────────────────────────────────────────────
        # Los embeddings cifrados pueden superar 255 caracteres.
        if _table_exists(conn, dialect, "profiles"):
            if not _column_exists(conn, dialect, "profiles", "voice_print"):
                conn.execute(text("ALTER TABLE profiles ADD COLUMN voice_print TEXT"))
                logger.info("Migración aplicada: profiles.voice_print (%s)", dialect)
            elif dialect == "postgresql":
                conn.execute(text("ALTER TABLE profiles ALTER COLUMN voice_print TYPE TEXT"))

        # ── users.addressing_instruction ────────────────────────────────────
        if not _column_exists(conn, dialect, "users", "addressing_instruction"):
            conn.execute(text("ALTER TABLE users ADD COLUMN addressing_instruction TEXT"))
            logger.info("Migración aplicada: users.addressing_instruction (%s)", dialect)

        # ── users.can_use_* (permisos por función) ──────────────────────────
        # Los valores por defecto se repiten aquí a propósito: son literales SQL
        # fijos, no deben depender de lo que diga capabilities.py en el futuro
        # (si mañana cambia el defecto, las bases ya migradas no deben cambiar).
        # Hora y clima nacen activos; el resto, apagado.
        permission_defaults = (
            ("can_use_time", "TRUE"),
            ("can_use_weather", "TRUE"),
            ("can_use_email", "FALSE"),
            ("can_use_email_write", "FALSE"),
            ("can_use_calendar", "FALSE"),
            ("can_use_calendar_write", "FALSE"),
            ("can_use_notes", "FALSE"),
            ("can_use_reminders", "FALSE"),
            ("can_use_tuya", "FALSE"),
            ("can_use_device", "FALSE"),
        )
        for column, default in permission_defaults:
            if _column_exists(conn, dialect, "users", column):
                continue
            # TRUE/FALSE los entienden los dos dialectos (en SQLite son 1 y 0).
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN {column} BOOLEAN NOT NULL DEFAULT {default}"
            ))
            logger.info("Migración aplicada: users.%s (%s)", column, dialect)

        # ── Separación de datos por usuario (notes, reminders) ──────────────
        # Se añade la columna y se asignan las filas existentes al dueño de la
        # instalación. Se queda NULLABLE en la base por compatibilidad (SQLite no
        # permite añadir NOT NULL sin default), pero el servidor siempre escribe
        # user_id y filtra por él: ver core/tools/notes.py y reminders.py.
        for table in ("notes", "reminders"):
            if not _table_exists(conn, dialect, table):
                continue
            if _column_exists(conn, dialect, table, "user_id"):
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))
            logger.info("Migración aplicada: %s.user_id (%s)", table, dialect)
            owner = _owner_user_id(conn)
            if owner:
                result = conn.execute(
                    text(f"UPDATE {table} SET user_id = :o WHERE user_id IS NULL"),
                    {"o": owner},
                )
                logger.info(
                    "Datos anteriores de %s asignados al usuario %s (%s filas)",
                    table, owner, result.rowcount,
                )


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
