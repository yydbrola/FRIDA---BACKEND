"""
Permission decorators para validação de roles.

Uso:
    @require_admin
    def admin_only_endpoint(user: AuthUser = Depends(get_current_user)):
        # user.role é garantido "admin"
        ...
"""

from functools import wraps
from typing import Callable
from fastapi import HTTPException, Depends

from app.auth.supabase import get_current_user, AuthUser


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator que valida role do usuário.
    
    Args:
        *allowed_roles: Lista de roles permitidos ("admin", "user")
    
    Returns:
        Decorator function
    
    Raises:
        HTTPException 403: Se user.role não está em allowed_roles
    
    Exemplo:
        @require_role("admin", "user")
        def endpoint(user: AuthUser = Depends(get_current_user)):
            # Apenas admin OU user podem acessar
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, user: AuthUser = Depends(get_current_user), **kwargs):
            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Acesso negado. Permissão necessária: {', '.join(allowed_roles)}"
                )
            return func(*args, user=user, **kwargs)
        return wrapper
    return decorator


# Atalhos comuns
require_admin = require_role("admin")
require_user = require_role("user")
require_any = require_role("admin", "user")  # Qualquer autenticado
