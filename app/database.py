"""
Database helper usando Supabase Client.
Funções minimalistas para consultar tabela users.

IMPORTANTE:
- Usa supabase-py já instalado no projeto
- Zero dependências novas
- Funções sync (def, não async)
"""

from typing import Optional, Dict, Any
from supabase import Client

from app.config import settings

# Singleton do Supabase Client
_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Retorna Supabase Client configurado.
    Reutiliza instância se já criada (singleton).
    
    Returns:
        Supabase Client configurado
    
    Raises:
        ValueError: Se SUPABASE_URL ou SUPABASE_KEY não configurados
    """
    global _client
    
    if _client is None:
        from supabase import create_client
        
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL e SUPABASE_KEY são obrigatórios. "
                "Verifique arquivo .env"
            )
        
        _client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY
        )
        
        print("[DATABASE] ✓ Supabase Client configurado")
    
    return _client


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca usuário na tabela users por ID.
    
    Args:
        user_id: UUID do usuário (string)
    
    Returns:
        Dict com dados do usuário ou None se não encontrado
        Exemplo: {
            "id": "a1b2c3d4-...",
            "email": "user@example.com",
            "name": "Nome",
            "role": "admin",
            "created_at": "2026-01-12T10:00:00Z"
        }
    
    Raises:
        Exception: Se query falhar por erro de conexão/DB
    """
    try:
        client = get_supabase_client()
        
        # Query com Supabase Client
        response = client.table('users').select('*').eq('id', user_id).execute()
        
        # Supabase retorna response.data como lista
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        # User não encontrado
        return None
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao buscar user {user_id}: {str(e)}")
        raise


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Busca usuário na tabela users por email.
    
    Args:
        email: Email do usuário
    
    Returns:
        Dict com dados do usuário ou None se não encontrado
    
    Raises:
        Exception: Se query falhar
    """
    try:
        client = get_supabase_client()
        
        response = client.table('users').select('*').eq('email', email).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao buscar user por email {email}: {str(e)}")
        raise
