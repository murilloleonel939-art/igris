"""
Rutas de autenticación - Login, registro, 2FA
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from core.database import get_db, User, TwoFactorAuth
from core.auth import (
    authenticate_user, create_user, get_user_by_id,
    create_access_token, create_refresh_token, verify_token,
    setup_2fa_for_user, enable_2fa_for_user, verify_user_2fa, verify_password
)
from core.schemas import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    Setup2FAResponse, Verify2FARequest, Verify2FAResponse, Disable2FARequest,
    SuccessResponse
)

# El prefijo se define SOLO aquí. En main.py se incluye sin prefix.
router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_user(authorization: str, db: Session) -> User:
    """Obtiene el usuario actual a partir del header 'Authorization: Bearer <token>'"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no válido")

    token = authorization.split(" ", 1)[1]
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token expirado o no válido")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return user


# ============= REGISTRO =============

@router.post("/register", response_model=UserResponse)
async def register(
    data: UserRegister,
    db: Session = Depends(get_db)
):
    """Registrar nuevo usuario"""

    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La contraseña debe tener al menos 8 caracteres"
        )

    if data.password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Las contraseñas no coinciden"
        )

    user = create_user(db, data.username, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya existe"
        )

    return user


# ============= LOGIN =============

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """Login con usuario y contraseña"""

    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Usuario o contraseña incorrectos"
        )

    # Si el usuario es nuevo (creado con is_active=False) y no tiene 2FA configurado, bloquear login
    # Pero si es un usuario existente que ya tenía cuenta activa antes, permitir (restaurado por authenticate_user)
    if not user.is_active and not db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first():
        raise HTTPException(
            status_code=403,
            detail="Cuenta pendiente de activación por un administrador"
        )

    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
    requires_2fa = bool(two_fa and two_fa.is_enabled)

    if requires_2fa:
        if not credentials.otp_code:
            raise HTTPException(
                status_code=403,
                detail="Código 2FA requerido"
            )

        if not verify_user_2fa(db, user.id, credentials.otp_code):
            raise HTTPException(
                status_code=401,
                detail="Código 2FA inválido"
            )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "requires_2fa": False
    }


# ============= 2FA =============

@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Preparar Google Authenticator 2FA"""

    user = get_current_user(authorization, db)
    result = setup_2fa_for_user(db, user.id)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="No se pudo configurar 2FA"
        )

    return result


@router.post("/2fa/verify", response_model=Verify2FAResponse)
async def verify_2fa(
    data: Verify2FARequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Confirmar y activar 2FA"""

    user = get_current_user(authorization, db)

    if enable_2fa_for_user(db, user.id, data.code):
        two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
        backup_codes = two_fa.backup_codes

        return {
            "success": True,
            "message": "2FA activado correctamente. Guarda tus códigos de respaldo.",
            "backup_codes": backup_codes
        }

    raise HTTPException(
        status_code=400,
        detail="Código 2FA inválido. Intenta de nuevo."
    )


@router.post("/2fa/disable", response_model=SuccessResponse)
async def disable_2fa(
    data: Disable2FARequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Desactivar 2FA"""

    user = get_current_user(authorization, db)

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Contraseña incorrecta"
        )

    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
    if two_fa:
        two_fa.is_enabled = False
        db.commit()

    return {
        "success": True,
        "message": "2FA desactivado correctamente"
    }


# ============= USUARIO ACTUAL =============

@router.get("/me", response_model=UserResponse)
async def get_me(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Obtener datos del usuario actual"""

    user = get_current_user(authorization, db)
    return user


@router.post("/logout", response_model=SuccessResponse)
async def logout(authorization: str = Header(None)):
    """Logout (solo invalida token en cliente)"""
    return {
        "success": True,
        "message": "Sesión cerrada"
    }
