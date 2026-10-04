"""
Autenticación - Login, Password hashing, Google Authenticator (2FA)
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import pyotp
import qrcode
from io import BytesIO
import base64
from sqlalchemy.orm import Session
from core.database import User, TwoFactorAuth

# Configuración
SECRET_KEY = os.environ.get("SECRET_KEY", "tu-clave-secreta-cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============= PASSWORD HASHING =============

def hash_password(password: str) -> str:
    """Hashear contraseña con bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    return pwd_context.verify(plain_password, hashed_password)


# ============= JWT TOKENS =============

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Crear JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {"user_id": user_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int) -> str:
    """Crear JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"user_id": user_id, "exp": expire, "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[int]:
    """Verificar JWT y retornar user_id"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


# ============= GOOGLE AUTHENTICATOR / 2FA =============

def generate_2fa_secret() -> str:
    """Generar nuevo secreto para Google Authenticator"""
    return pyotp.random_base32()


def get_2fa_qr_code(username: str, secret: str, issuer: str = "IGRIS") -> str:
    """Generar QR code para escanear en Google Authenticator"""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name=issuer)
    
    # Generar QR code como imagen base64
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_base64}"


def verify_2fa_code(secret: str, code: str) -> bool:
    """Verificar código 2FA ingresado por el usuario"""
    totp = pyotp.TOTP(secret)
    # Permitir 1 ventana anterior y siguiente (±30 segundos)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> list:
    """Generar códigos de respaldo para 2FA (sin internet, etc)"""
    import secrets
    return [secrets.token_hex(4) for _ in range(count)]


def verify_backup_code(backup_codes: list, code: str) -> bool:
    """Verificar si un código de respaldo es válido"""
    return code in backup_codes


# ============= USUARIO =============

def create_user(db: Session, username: str, email: str, password: str) -> Optional[User]:
    """Crear nuevo usuario"""
    if db.query(User).filter(User.username == username).first():
        return None  # Usuario ya existe
    
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Obtener usuario por nombre"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Obtener usuario por ID"""
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Autenticar usuario (contraseña correcta)"""
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


# ============= 2FA SETUP =============

def setup_2fa_for_user(db: Session, user_id: int) -> dict:
    """Preparar 2FA para usuario (antes de activar)"""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    # Generar secreto
    secret = generate_2fa_secret()
    backup_codes = generate_backup_codes()
    
    # Crear registro en BD (aún no activado)
    two_fa = TwoFactorAuth(
        user_id=user_id,
        secret_key=secret,
        is_enabled=False,
        backup_codes=backup_codes
    )
    db.add(two_fa)
    db.commit()
    db.refresh(two_fa)
    
    # Generar QR code
    qr_code = get_2fa_qr_code(user.username, secret)
    
    return {
        "secret": secret,
        "qr_code": qr_code,
        "backup_codes": backup_codes,
        "message": "Escanea el QR con Google Authenticator, luego confirma con un código"
    }


def enable_2fa_for_user(db: Session, user_id: int, code: str) -> bool:
    """Activar 2FA después de que usuario confirme código"""
    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
    if not two_fa or two_fa.is_enabled:
        return False
    
    if verify_2fa_code(two_fa.secret_key, code):
        two_fa.is_enabled = True
        two_fa.last_verified = datetime.utcnow()
        db.commit()
        return True
    
    return False


def disable_2fa_for_user(db: Session, user_id: int):
    """Desactivar 2FA"""
    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
    if two_fa:
        two_fa.is_enabled = False
        db.commit()


def verify_user_2fa(db: Session, user_id: int, code: str) -> bool:
    """Verificar código 2FA durante login"""
    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
    if not two_fa or not two_fa.is_enabled:
        return True  # 2FA no configurado, permitir login
    
    # Intentar con código normal
    if verify_2fa_code(two_fa.secret_key, code):
        two_fa.last_verified = datetime.utcnow()
        db.commit()
        return True
    
    # Intentar con código de respaldo
    if verify_backup_code(two_fa.backup_codes, code):
        # Remover código usado
        two_fa.backup_codes.remove(code)
        db.commit()
        return True
    
    return False
