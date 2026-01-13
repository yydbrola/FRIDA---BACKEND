"""
Database helper usando Supabase Client.
Funções minimalistas para consultar tabela users.

IMPORTANTE:
- Usa supabase-py já instalado no projeto
- Zero dependências novas
- Funções sync (def, não async)
"""

from typing import Optional, Dict, Any
from supabase import Client, create_client

from app.config import settings


def get_supabase_client() -> Client:
    """
    Retorna Supabase Client configurado.
    
    IMPORTANTE: Cria cliente novo a cada chamada (sem singleton/cache).
    Isso garante que sempre usa a API key atual do .env.
    
    Returns:
        Client: Supabase Client configurado
    
    Raises:
        ValueError: Se SUPABASE_URL ou SUPABASE_KEY não configurados
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL e SUPABASE_KEY são obrigatórios. "
            "Verifique arquivo .env"
        )
    
    # Debug: identificar tipo de key sendo usada
    key_preview = settings.SUPABASE_KEY[:20] + "..." if len(settings.SUPABASE_KEY) > 20 else settings.SUPABASE_KEY
    print(f"[DATABASE] Creating client with key: {key_preview}")
    
    client = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_KEY
    )
    
    print("[DATABASE] ✓ Client created successfully")
    return client


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


# =============================================================================
# Products CRUD
# =============================================================================

def create_product(name: str, category: str, classification: dict, user_id: str) -> Dict[str, Any]:
    """
    Cria um novo produto no banco de dados.
    
    Args:
        name: Nome do produto
        category: Categoria (bolsa, lancheira, garrafa_termica)
        classification: Resultado da classificação Gemini (dict)
        user_id: UUID do usuário criador
        
    Returns:
        Dict com dados completos do produto criado
        
    Raises:
        Exception: Se falha ao inserir no banco
    """
    client = get_supabase_client()
    
    try:
        result = client.table('products').insert({
            'name': name,
            'category': category,
            'classification_result': classification,
            'created_by': user_id,
            'status': 'draft'
        }).execute()
        
        if not result.data:
            raise Exception("Falha ao criar produto: resposta vazia")
        
        return result.data[0]
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao criar produto: {str(e)}")
        raise


def get_user_products(user_id: str) -> list:
    """
    Lista todos os produtos de um usuário.
    
    Args:
        user_id: UUID do usuário
        
    Returns:
        Lista de produtos (vazia se nenhum encontrado)
    """
    client = get_supabase_client()
    
    try:
        result = client.table('products')\
            .select('*')\
            .eq('created_by', user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao listar produtos: {str(e)}")
        return []


# =============================================================================
# Images CRUD
# =============================================================================

def create_image(
    product_id: str, 
    type: str, 
    bucket: str, 
    path: str, 
    user_id: str
) -> Dict[str, Any]:
    """
    Registra uma imagem processada no banco.
    
    Args:
        product_id: UUID do produto relacionado
        type: Tipo da imagem ('original', 'segmented', 'processed')
        bucket: Nome do bucket no Supabase Storage
        path: Caminho do arquivo no storage
        user_id: UUID do usuário criador
        
    Returns:
        Dict com dados completos da imagem registrada
        
    Raises:
        ValueError: Se type não for válido
        Exception: Se falha ao inserir no banco
    """
    # Validar type
    valid_types = ['original', 'segmented', 'processed']
    if type not in valid_types:
        raise ValueError(f"Tipo inválido: {type}. Use: {', '.join(valid_types)}")
    
    client = get_supabase_client()
    
    try:
        result = client.table('images').insert({
            'product_id': product_id,
            'type': type,
            'storage_bucket': bucket,
            'storage_path': path,
            'created_by': user_id
        }).execute()
        
        if not result.data:
            raise Exception("Falha ao registrar imagem: resposta vazia")
        
        return result.data[0]
        
    except Exception as e:
        print(f"[DATABASE] ❌ Erro ao registrar imagem: {str(e)}")
        raise

