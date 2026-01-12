"""
Frida Orchestrator - Supabase JWT Authentication
Validação de tokens JWT emitidos pelo Supabase Auth.

Este módulo fornece:
- verify_supabase_jwt(): Valida e decodifica token JWT
- get_current_user_id(): Dependency do FastAPI para injetar user_id
- AuthenticationError: Exceção para erros de autenticação

Configuração via .env:
- AUTH_ENABLED: Se False, desabilita validação (dev mode)
- SUPABASE_JWT_SECRET: Secret do projeto Supabase (obrigatório se AUTH_ENABLED=True)
"""

import jwt
from typing import Optional
from fastapi import HTTPException, Header, status

from app.config import settings


# =============================================================================
# Constants
# =============================================================================

# User ID fake para desenvolvimento quando AUTH_ENABLED=False
DEV_USER_ID = "00000000-0000-0000-0000-000000000000"

# Algoritmo usado pelo Supabase
JWT_ALGORITHM = "HS256"

# Audience esperada nos tokens Supabase
JWT_AUDIENCE = "authenticated"


# =============================================================================
# Exceptions
# =============================================================================

class AuthenticationError(HTTPException):
    """
    Exceção para erros de autenticação.
    Retorna HTTP 401 com header WWW-Authenticate: Bearer.
    """
    
    def __init__(self, detail: str = "Credenciais inválidas"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


# =============================================================================
# JWT Verification
# =============================================================================

def verify_supabase_jwt(authorization: str) -> str:
    """
    Valida e decodifica um token JWT do Supabase.
    
    Args:
        authorization: Header Authorization no formato "Bearer <token>"
        
    Returns:
        user_id (sub) extraído do token
        
    Raises:
        AuthenticationError: Se o token for inválido, expirado, etc.
        RuntimeError: Se SUPABASE_JWT_SECRET não estiver configurado
    """
    # Dev mode: retorna user_id fake
    if not settings.AUTH_ENABLED:
        return DEV_USER_ID
    
    # Verifica se JWT secret está configurado
    if not settings.SUPABASE_JWT_SECRET:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET não configurado. "
            "Configure no .env ou desabilite auth com AUTH_ENABLED=false"
        )
    
    # Valida formato "Bearer <token>"
    if not authorization:
        raise AuthenticationError("Header Authorization ausente")
    
    parts = authorization.split()
    
    if len(parts) != 2:
        raise AuthenticationError("Formato inválido. Use: Bearer <token>")
    
    scheme, token = parts
    
    if scheme.lower() != "bearer":
        raise AuthenticationError("Scheme inválido. Use: Bearer")
    
    # Decodifica e valida o token
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True
            }
        )
        
        # Extrai user_id do claim "sub"
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Token não contém user_id (sub)")
        
        return user_id
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token expirado")
    
    except jwt.InvalidAudienceError:
        raise AuthenticationError("Token audience inválido")
    
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Token inválido: {str(e)}")


# =============================================================================
# FastAPI Dependencies
# =============================================================================

def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """
    Dependency do FastAPI para obter o user_id do token JWT.
    
    Uso:
        @app.get("/protected")
        def protected_route(user_id: str = Depends(get_current_user_id)):
            return {"user_id": user_id}
    
    Args:
        authorization: Header Authorization (injetado automaticamente)
        
    Returns:
        user_id extraído do token JWT
        
    Raises:
        AuthenticationError: Se token ausente/inválido e AUTH_ENABLED=True
    """
    # Se authorization está presente, valida o token
    if authorization:
        return verify_supabase_jwt(authorization)
    
    # Se não há header e AUTH está desabilitado, retorna user fake
    if not settings.AUTH_ENABLED:
        return DEV_USER_ID
    
    # Auth habilitado mas sem header → erro
    raise AuthenticationError("Header Authorization ausente")
