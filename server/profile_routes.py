"""
Rutas de perfiles de usuarios autorizados y configuración AI
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db, User, Profile, AIConfig
from core.schemas import (
    ProfileCreate, ProfileUpdate, ProfileResponse,
    AIConfigUpdate, AIConfigResponse, DashboardResponse, UserResponse,
    SuccessResponse
)
from server.auth_routes import get_current_user

router = APIRouter(prefix="/api", tags=["profiles"])


# ============= PERFILES DE USUARIO =============

@router.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Listar todos los perfiles autorizados del usuario"""
    
    user = get_current_user(authorization, db)
    profiles = db.query(Profile).filter(Profile.user_id == user.id).all()
    return profiles


@router.post("/profiles", response_model=ProfileResponse)
async def create_profile(
    data: ProfileCreate,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Crear nuevo perfil autorizado"""
    
    user = get_current_user(authorization, db)
    
    profile = Profile(
        user_id=user.id,
        name=data.name,
        can_execute_commands=data.can_execute_commands,
        can_manage_users=data.can_manage_users
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return profile


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Obtener detalles de un perfil"""
    
    user = get_current_user(authorization, db)
    profile = db.query(Profile).filter(
        Profile.id == profile_id,
        Profile.user_id == user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    return profile


@router.put("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: int,
    data: ProfileUpdate,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Actualizar perfil"""
    
    user = get_current_user(authorization, db)
    profile = db.query(Profile).filter(
        Profile.id == profile_id,
        Profile.user_id == user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    # Actualizar campos
    if data.name is not None:
        profile.name = data.name
    if data.is_authorized is not None:
        profile.is_authorized = data.is_authorized
    if data.can_execute_commands is not None:
        profile.can_execute_commands = data.can_execute_commands
    if data.can_manage_users is not None:
        profile.can_manage_users = data.can_manage_users
    
    db.commit()
    db.refresh(profile)
    
    return profile


@router.delete("/profiles/{profile_id}", response_model=SuccessResponse)
async def delete_profile(
    profile_id: int,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Eliminar perfil"""
    
    user = get_current_user(authorization, db)
    profile = db.query(Profile).filter(
        Profile.id == profile_id,
        Profile.user_id == user.id
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    db.delete(profile)
    db.commit()
    
    return {
        "success": True,
        "message": f"Perfil '{profile.name}' eliminado"
    }


# ============= CONFIGURACIÓN AI =============

@router.get("/ai-config", response_model=AIConfigResponse)
async def get_ai_config(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Obtener configuración AI del usuario"""
    
    user = get_current_user(authorization, db)
    ai_config = db.query(AIConfig).filter(AIConfig.user_id == user.id).first()
    
    if not ai_config:
        # Crear configuración por defecto
        ai_config = AIConfig(user_id=user.id)
        db.add(ai_config)
        db.commit()
        db.refresh(ai_config)
    
    return ai_config


@router.put("/ai-config", response_model=AIConfigResponse)
async def update_ai_config(
    data: AIConfigUpdate,
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Actualizar configuración AI"""
    
    user = get_current_user(authorization, db)
    ai_config = db.query(AIConfig).filter(AIConfig.user_id == user.id).first()
    
    if not ai_config:
        ai_config = AIConfig(user_id=user.id)
        db.add(ai_config)
    
    # Actualizar campos
    if data.primary_provider is not None:
        ai_config.primary_provider = data.primary_provider
    if data.fallback_chain is not None:
        ai_config.fallback_chain = data.fallback_chain
    if data.stt_provider is not None:
        ai_config.stt_provider = data.stt_provider
    if data.tts_provider is not None:
        ai_config.tts_provider = data.tts_provider
    if data.stt_model is not None:
        ai_config.stt_model = data.stt_model
    if data.system_prompt is not None:
        ai_config.system_prompt = data.system_prompt
    if data.timezone is not None:
        ai_config.timezone = data.timezone
    
    db.commit()
    db.refresh(ai_config)
    
    return ai_config


# ============= DASHBOARD COMPLETO =============

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Obtener dashboard completo con usuario, config AI y perfiles"""
    
    user = get_current_user(authorization, db)
    
    # Obtener AI config
    ai_config = db.query(AIConfig).filter(AIConfig.user_id == user.id).first()
    if not ai_config:
        ai_config = AIConfig(user_id=user.id)
        db.add(ai_config)
        db.commit()
        db.refresh(ai_config)
    
    # Obtener perfiles
    profiles = db.query(Profile).filter(Profile.user_id == user.id).all()
    
    # Obtener estado 2FA
    from core.database import TwoFactorAuth
    two_fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
    two_fa_enabled = two_fa and two_fa.is_enabled
    
    return {
        "user": user,
        "ai_config": ai_config,
        "profiles": profiles,
        "two_fa_enabled": two_fa_enabled
    }
