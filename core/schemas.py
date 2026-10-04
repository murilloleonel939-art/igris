"""
Schemas Pydantic para validación de datos
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ============= AUTH & LOGIN =============

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

    class Config:
        json_schema_extra = {
            "example": {
                "username": "murillo",
                "email": "murillo@example.com",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!"
            }
        }


class UserLogin(BaseModel):
    username: str
    password: str
    otp_code: Optional[str] = None  # Google Authenticator code


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============= 2FA / GOOGLE AUTHENTICATOR =============

class Setup2FAResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]
    message: str


class Verify2FARequest(BaseModel):
    code: str  # Código de Google Authenticator


class Verify2FAResponse(BaseModel):
    success: bool
    message: str
    backup_codes: Optional[List[str]] = None


class Disable2FARequest(BaseModel):
    password: str


# ============= PROFILES (Perfiles de Usuarios Autorizados) =============

class ProfileCreate(BaseModel):
    name: str
    can_execute_commands: bool = True
    can_manage_users: bool = False


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    is_authorized: Optional[bool] = None
    can_execute_commands: Optional[bool] = None
    can_manage_users: Optional[bool] = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    is_authorized: bool
    can_execute_commands: bool
    can_manage_users: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= AI CONFIG =============

class AIConfigUpdate(BaseModel):
    primary_provider: Optional[str] = None  # groq, openai, anthropic, local
    fallback_chain: Optional[List[str]] = None  # [groq, openai, anthropic, local]
    stt_provider: Optional[str] = None  # local, openai
    tts_provider: Optional[str] = None  # local, edge-tts
    stt_model: Optional[str] = None  # tiny, base, small, medium, large
    system_prompt: Optional[str] = None
    timezone: Optional[str] = None


class AIConfigResponse(BaseModel):
    id: int
    primary_provider: str
    fallback_chain: List[str]
    stt_provider: str
    tts_provider: str
    stt_model: str
    system_prompt: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============= DASHBOARD =============

class DashboardResponse(BaseModel):
    user: UserResponse
    ai_config: AIConfigResponse
    profiles: List[ProfileResponse]
    two_fa_enabled: bool


# ============= RESPONSES =============

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class SuccessResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
