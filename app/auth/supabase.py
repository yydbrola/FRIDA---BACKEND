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
from typing import Optional, Literal
from fastapi import HTTPException, Header, status
from pydantic import BaseModel

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
# AuthUser Model
# =============================================================================

class AuthUser(BaseModel):
    """
    Modelo de usuário autenticado com dados do banco.
    Substitui retorno direto de user_id (string).
    """
    user_id: str
    email: str
    role: Literal["admin", "user"]
    name: Optional[str] = None


# =============================================================================
# FastAPI Dependencies
# =============================================================================

def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> AuthUser:
    """
    Dependency que valida JWT + consulta users table.
    
    Fluxo de validação:
    1. Dev mode (AUTH_ENABLED=false) → retorna AuthUser fake (bypass)
    2. Prod mode → valida JWT usando verify_supabase_jwt() existente
    3. Prod mode → consulta users table via Supabase Client
    4. Se user não existe na tabela → HTTP 403 (não cadastrado)
    5. Se user existe → retorna AuthUser com dados completos
    
    Args:
        authorization: Header "Authorization: Bearer {token}"
    
    Returns:
        AuthUser com user_id, email, role, name
    
    Raises:
        HTTPException 401: JWT inválido ou expirado
        HTTPException 403: User não cadastrado no sistema
        HTTPException 500: Erro de database
    """
    # Dev mode: bypass completo (não consulta banco)
    if not settings.AUTH_ENABLED:
        return AuthUser(
            user_id=DEV_USER_ID,
            email="dev@frida.com",
            role="admin",
            name="Dev User"
        )
    
    # Prod mode: validar JWT (usa código existente)
    try:
        user_id = verify_supabase_jwt(authorization)
    except AuthenticationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Erro de autenticação: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # NOVA VALIDAÇÃO: consultar users table
    try:
        from app.database import get_user_by_id
        user_data = get_user_by_id(user_id)
    except Exception as e:
        # Erro de database (conexão, timeout, etc)
        print(f"[AUTH] ❌ Erro ao consultar users table: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao validar usuário. Tente novamente."
        )
    
    # User não existe na tabela users
    if not user_data:
        raise HTTPException(
            status_code=403,
            detail=(
                "Usuário não cadastrado no sistema. "
                "Contate o administrador para aprovação."
            )
        )
    
    # Validar campo role (defesa contra dados inválidos)
    role = user_data.get("role", "user")
    if role not in ["admin", "user"]:
        print(f"[AUTH] ⚠️ Role inválido para user {user_id}: {role}")
        role = "user"  # Fallback seguro
    
    # Retornar dados completos do usuário
    return AuthUser(
        user_id=str(user_data["id"]),
        email=user_data["email"],
        role=role,
        name=user_data.get("name")
    )


def get_current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """
    Dependency do FastAPI para obter o user_id do token JWT.
    
    DEPRECATED: Use get_current_user() diretamente para ter acesso a role.
    Mantido para backward compatibility.
    
    Args:
        authorization: Header Authorization (injetado automaticamente)
        
    Returns:
        user_id extraído do token JWT
        
    Raises:
        AuthenticationError: Se token ausente/inválido e AUTH_ENABLED=True
    """
    user = get_current_user(authorization)
    return user.user_id

