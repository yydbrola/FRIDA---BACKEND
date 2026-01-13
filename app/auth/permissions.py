"""
RBAC - Role-Based Access Control para FastAPI.

Implementado como Dependency Factories (não decorators).

Uso:
    from app.auth.permissions import require_admin, require_user, require_any

    # Apenas admin
    @app.delete("/users/{id}")
    def delete_user(user: AuthUser = Depends(require_admin)):
        ...

    # Apenas user
    @app.get("/my-profile")
    def get_profile(user: AuthUser = Depends(require_user)):
        ...

    # Qualquer autenticado (admin ou user)
    @app.get("/products")
    def list_products(user: AuthUser = Depends(require_any)):
        ...

    # Roles customizados
    @app.post("/moderate")
    def moderate(user: AuthUser = Depends(require_role("admin", "moderator"))):
        ...
"""

from fastapi import Depends, HTTPException

from app.auth.supabase import get_current_user, AuthUser


def require_role(*allowed_roles: str):
    """
    Cria uma dependência FastAPI que valida o role do usuário.

    Args:
        *allowed_roles: Roles permitidos (ex: "admin", "user")

    Returns:
        Dependência que retorna AuthUser se autorizado

    Raises:
        HTTPException 403: Se user.role não está em allowed_roles

    Exemplo:
        @app.delete("/admin-only")
        def admin_endpoint(user: AuthUser = Depends(require_role("admin"))):
            # Garantido: user.role == "admin"
            ...
    """
    async def role_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado. Role '{user.role}' não autorizado. "
                       f"Roles permitidos: {', '.join(allowed_roles)}"
            )
        return user

    return role_checker


# =============================================================================
# Dependências pré-configuradas para uso comum
# =============================================================================

# Apenas administradores
require_admin = require_role("admin")

# Apenas usuários comuns
require_user = require_role("user")

# Qualquer usuário autenticado (admin ou user)
require_any = require_role("admin", "user")
