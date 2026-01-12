"""
Frida Orchestrator - Auth Module
Autenticação via Supabase JWT.
"""

from app.auth.supabase import verify_supabase_jwt, get_current_user_id, AuthenticationError

__all__ = ["verify_supabase_jwt", "get_current_user_id", "AuthenticationError"]
