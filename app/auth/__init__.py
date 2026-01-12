"""
Frida Orchestrator - Auth Module
Autenticação via Supabase JWT.
"""

from app.auth.supabase import (
    # NOVOS
    AuthUser,
    get_current_user,
    
    # EXISTENTES
    get_current_user_id,    # Legacy (mantém para compatibilidade)
    verify_supabase_jwt,
    AuthenticationError
)

from app.auth.permissions import (
    require_role,
    require_admin,
    require_user,
    require_any
)

__all__ = [
    # Auth
    "AuthUser",
    "get_current_user",
    "get_current_user_id",
    "verify_supabase_jwt",
    "AuthenticationError",
    
    # Permissions
    "require_role",
    "require_admin",
    "require_user",
    "require_any"
]

