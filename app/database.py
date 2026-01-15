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


def build_storage_public_url(bucket: str, path: str) -> str:
    """
    Constrói URL pública do Supabase Storage.
    
    Args:
        bucket: Nome do bucket (ex: 'processed-images', 'raw')
        path: Caminho do arquivo no bucket
        
    Returns:
        URL pública completa
    """
    if not settings.SUPABASE_URL or not bucket or not path:
        return ""
    
    # Supabase Storage URL pattern: {url}/storage/v1/object/public/{bucket}/{path}
    base_url = settings.SUPABASE_URL.rstrip('/')
    return f"{base_url}/storage/v1/object/public/{bucket}/{path}"


def get_user_products(user_id: str) -> list:
    """
    Lista todos os produtos de um usuário com thumbnail_url.
    
    Faz JOIN com tabela images para obter URL da imagem processada.
    Fallback: usa imagem original se processed não existir.
    
    Args:
        user_id: UUID do usuário
        
    Returns:
        Lista de produtos com thumbnail_url (vazia se nenhum encontrado)
    """
    client = get_supabase_client()
    
    try:
        # Buscar produtos com imagens relacionadas via foreign key
        # Supabase permite nested select: images(type, storage_bucket, storage_path)
        result = client.table('products')\
            .select('*, images(type, storage_bucket, storage_path)')\
            .eq('created_by', user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        products = result.data if result.data else []
        
        # Processar cada produto para adicionar thumbnail_url
        for product in products:
            thumbnail_url = None
            images = product.pop('images', []) or []
            
            # Prioridade: processed > original
            processed_img = next((img for img in images if img['type'] == 'processed'), None)
            original_img = next((img for img in images if img['type'] == 'original'), None)
            
            # Usar processed se existir, senão original
            img = processed_img or original_img
            
            if img and img.get('storage_bucket') and img.get('storage_path'):
                thumbnail_url = build_storage_public_url(
                    img['storage_bucket'], 
                    img['storage_path']
                )
            
            product['thumbnail_url'] = thumbnail_url
        
        return products
        
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


# =============================================================================
# JOBS CRUD (PRD-04)
# =============================================================================

def create_job(
    product_id: str,
    user_id: str,
    input_data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Cria novo job com status='queued'.
    
    Args:
        product_id: UUID do produto associado
        user_id: UUID do usuário que criou
        input_data: Dados de entrada (original_path, classification, etc)
    
    Returns:
        job_id (UUID string) ou None se falhar
    
    Exemplo de input_data:
        {
            "original_path": "raw/user_id/product_id/original.jpg",
            "classification": {"item": "bolsa", "estilo": "foto", "confianca": 0.95}
        }
    """
    try:
        client = get_supabase_client()
        
        data = {
            "product_id": product_id,
            "created_by": user_id,
            "status": "queued",
            "current_step": "uploading",
            "progress": 0,
            "input_data": input_data or {}
        }
        
        response = client.table("jobs").insert(data).execute()
        
        if response.data and len(response.data) > 0:
            job_id = response.data[0]["id"]
            print(f"[DATABASE] ✓ Job criado: {job_id}")
            return job_id
        else:
            print("[DATABASE] ✗ Falha ao criar job (sem data)")
            return None
            
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao criar job: {str(e)}")
        return None


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca job por ID.
    
    Args:
        job_id: UUID do job
    
    Returns:
        Dict com todos os campos do job ou None se não encontrado
    """
    try:
        client = get_supabase_client()
        
        response = client.table("jobs").select("*").eq("id", job_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao buscar job {job_id}: {str(e)}")
        return None


def get_job_by_product(product_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca job mais recente de um produto.
    
    Args:
        product_id: UUID do produto
    
    Returns:
        Job mais recente (ordenado por created_at DESC) ou None
    """
    try:
        client = get_supabase_client()
        
        response = client.table("jobs")\
            .select("*")\
            .eq("product_id", product_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao buscar job do produto {product_id}: {str(e)}")
        return None


def update_job_progress(
    job_id: str,
    status: Optional[str] = None,
    current_step: Optional[str] = None,
    progress: Optional[int] = None,
    provider: Optional[str] = None,
    last_error: Optional[str] = None
) -> bool:
    """
    Atualiza progresso do job.
    Apenas campos não-None são atualizados.
    
    Args:
        job_id: UUID do job
        status: 'queued', 'processing', 'completed', 'failed'
        current_step: 'uploading', 'classifying', 'segmenting', 'composing', 'validating', 'saving', 'done'
        progress: 0-100
        provider: 'remove.bg' ou 'rembg'
        last_error: Mensagem de erro (se houver)
    
    Returns:
        True se atualizou, False se falhou
    """
    try:
        client = get_supabase_client()
        
        # Monta update apenas com campos não-None
        update_data = {}
        if status is not None:
            update_data["status"] = status
        if current_step is not None:
            update_data["current_step"] = current_step
        if progress is not None:
            update_data["progress"] = progress
        if provider is not None:
            update_data["provider"] = provider
        if last_error is not None:
            update_data["last_error"] = last_error
        
        if not update_data:
            print("[DATABASE] ✗ Nenhum campo para atualizar")
            return False
        
        response = client.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data and len(response.data) > 0:
            print(f"[DATABASE] ✓ Job {job_id} atualizado: {list(update_data.keys())}")
            return True
        else:
            print(f"[DATABASE] ✗ Job {job_id} não encontrado para update")
            return False
            
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao atualizar job {job_id}: {str(e)}")
        return False


def increment_job_attempt(
    job_id: str,
    error: str,
    retry_delay_seconds: Optional[int] = None
) -> Dict[str, Any]:
    """
    Incrementa contador de tentativas e registra erro.
    
    Se retry_delay_seconds for fornecido, calcula next_retry_at.
    
    Args:
        job_id: UUID do job
        error: Mensagem de erro
        retry_delay_seconds: Segundos até próxima tentativa (para backoff)
    
    Returns:
        Dict com {attempts: int, max_attempts: int, should_retry: bool}
    """
    from datetime import datetime, timedelta, timezone
    
    try:
        client = get_supabase_client()
        
        # Busca job atual
        job = get_job(job_id)
        if not job:
            return {"attempts": 0, "max_attempts": 3, "should_retry": False}
        
        new_attempts = job.get("attempts", 0) + 1
        max_attempts = job.get("max_attempts", 3)
        should_retry = new_attempts < max_attempts
        
        # Monta update
        update_data = {
            "attempts": new_attempts,
            "last_error": error,
            "status": "failed"
        }
        
        # Calcula next_retry_at se deve tentar novamente
        if should_retry and retry_delay_seconds:
            next_retry = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)
            update_data["next_retry_at"] = next_retry.isoformat()
        
        response = client.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data:
            retry_status = "vai tentar novamente" if should_retry else "sem mais tentativas"
            print(f"[DATABASE] ✓ Job {job_id} attempt {new_attempts}/{max_attempts} ({retry_status})")
        
        return {
            "attempts": new_attempts,
            "max_attempts": max_attempts,
            "should_retry": should_retry
        }
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao incrementar attempt do job {job_id}: {str(e)}")
        return {"attempts": 0, "max_attempts": 3, "should_retry": False}


def complete_job(job_id: str, output_data: Dict[str, Any]) -> bool:
    """
    Marca job como completed e salva output.
    
    Args:
        job_id: UUID do job
        output_data: Resultado do processamento
            {
                "images": {
                    "original": {"bucket": "raw", "path": "..."},
                    "segmented": {"bucket": "segmented", "path": "..."},
                    "processed": {"bucket": "processed-images", "path": "...", "quality_score": 95}
                },
                "quality_score": 95,
                "quality_passed": True
            }
    
    Returns:
        True se completou, False se falhou
    """
    try:
        client = get_supabase_client()
        
        update_data = {
            "status": "completed",
            "current_step": "done",
            "progress": 100,
            "output_data": output_data
        }
        
        response = client.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data and len(response.data) > 0:
            print(f"[DATABASE] ✓ Job {job_id} completado com sucesso")
            return True
        else:
            print(f"[DATABASE] ✗ Job {job_id} não encontrado para completar")
            return False
            
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao completar job {job_id}: {str(e)}")
        return False


def fail_job(job_id: str, error: str) -> bool:
    """
    Marca job como failed definitivamente (sem mais retries).
    
    Args:
        job_id: UUID do job
        error: Mensagem de erro final
    
    Returns:
        True se atualizou, False se falhou
    """
    try:
        client = get_supabase_client()
        
        # Busca para pegar max_attempts
        job = get_job(job_id)
        max_attempts = job.get("max_attempts", 3) if job else 3
        
        update_data = {
            "status": "failed",
            "last_error": error,
            "attempts": max_attempts  # Garante que não vai tentar novamente
        }
        
        response = client.table("jobs").update(update_data).eq("id", job_id).execute()
        
        if response.data and len(response.data) > 0:
            print(f"[DATABASE] ✓ Job {job_id} marcado como failed (definitivo)")
            return True
        else:
            print(f"[DATABASE] ✗ Job {job_id} não encontrado para fail")
            return False
            
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao marcar job {job_id} como failed: {str(e)}")
        return False


def get_next_queued_job() -> Optional[Dict[str, Any]]:
    """
    Busca próximo job na fila (FIFO).
    
    Prioridade:
    1. Jobs 'queued' ordenados por created_at ASC
    2. Jobs 'failed' com attempts < max_attempts E next_retry_at <= NOW()
    
    Returns:
        Próximo job para processar ou None se fila vazia
    """
    from datetime import datetime, timezone
    
    try:
        client = get_supabase_client()
        
        # 1. Primeiro tenta pegar job 'queued' (FIFO)
        response = client.table("jobs")\
            .select("*")\
            .eq("status", "queued")\
            .order("created_at", desc=False)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            job = response.data[0]
            print(f"[DATABASE] ✓ Próximo job (queued): {job['id']}")
            return job
        
        # 2. Se não tem queued, busca failed pronto para retry
        now = datetime.now(timezone.utc).isoformat()
        
        # Busca failed com retry pendente
        response = client.table("jobs")\
            .select("*")\
            .eq("status", "failed")\
            .lte("next_retry_at", now)\
            .order("next_retry_at", desc=False)\
            .limit(1)\
            .execute()
        
        if response.data and len(response.data) > 0:
            job = response.data[0]
            # Verifica se ainda pode tentar
            if job.get("attempts", 0) < job.get("max_attempts", 3):
                print(f"[DATABASE] ✓ Próximo job (retry): {job['id']} (attempt {job['attempts']+1})")
                return job
        
        # Fila vazia
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao buscar próximo job: {str(e)}")
        return None


def get_user_jobs(user_id: str, limit: int = 20) -> list:
    """
    Lista jobs do usuário (mais recentes primeiro).
    
    Args:
        user_id: UUID do usuário
        limit: Máximo de jobs (default 20)
    
    Returns:
        Lista de jobs ordenada por created_at DESC
    """
    try:
        client = get_supabase_client()
        
        response = client.table("jobs")\
            .select("*")\
            .eq("created_by", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        jobs = response.data if response.data else []
        print(f"[DATABASE] ✓ {len(jobs)} jobs encontrados para usuário")
        return jobs
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao listar jobs do usuário: {str(e)}")
        return []


# =============================================================================
# TECHNICAL SHEETS CRUD (PRD-05)
# =============================================================================

def create_technical_sheet(
    product_id: str,
    user_id: str,
    data: Optional[dict] = None
) -> Optional[str]:
    """
    Cria uma nova ficha técnica para um produto.
    
    Args:
        product_id: UUID do produto (deve ser único)
        user_id: UUID do usuário criador
        data: Dados iniciais da ficha (opcional)
    
    Returns:
        sheet_id se sucesso, None se falha
    """
    try:
        client = get_supabase_client()
        
        # Data default com schema
        sheet_data = data if data else {"_version": 1, "_schema": "bag_v1"}
        
        # Garantir que _version e _schema existam
        if "_version" not in sheet_data:
            sheet_data["_version"] = 1
        if "_schema" not in sheet_data:
            sheet_data["_schema"] = "bag_v1"
        
        insert_data = {
            "product_id": product_id,
            "created_by": user_id,
            "data": sheet_data,
            "status": "draft",
            "version": 1
        }
        
        response = client.table("technical_sheets")\
            .insert(insert_data)\
            .execute()
        
        if response.data and len(response.data) > 0:
            sheet_id = response.data[0]["id"]
            print(f"[DATABASE] ✓ Technical sheet criada: {sheet_id}")
            return sheet_id
        
        print("[DATABASE] ✗ Nenhum dado retornado ao criar sheet")
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao criar technical sheet: {str(e)}")
        return None


def get_technical_sheet(sheet_id: str) -> Optional[dict]:
    """
    Busca ficha técnica por ID.
    
    Args:
        sheet_id: UUID da ficha
    
    Returns:
        Dict com dados da ficha ou None
    """
    try:
        client = get_supabase_client()
        
        response = client.table("technical_sheets")\
            .select("*")\
            .eq("id", sheet_id)\
            .single()\
            .execute()
        
        if response.data:
            print(f"[DATABASE] ✓ Sheet encontrada: {sheet_id}")
            return response.data
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao buscar sheet {sheet_id}: {str(e)}")
        return None


def get_sheet_by_product(product_id: str) -> Optional[dict]:
    """
    Busca ficha técnica pelo product_id.
    
    Args:
        product_id: UUID do produto
    
    Returns:
        Dict com dados da ficha ou None (não loga erro se não existe)
    """
    try:
        client = get_supabase_client()
        
        response = client.table("technical_sheets")\
            .select("*")\
            .eq("product_id", product_id)\
            .execute()
        
        # Pode não existir ainda - não é erro
        if response.data and len(response.data) > 0:
            print(f"[DATABASE] ✓ Sheet encontrada para product: {product_id}")
            return response.data[0]
        
        # Não encontrou - retorna None silenciosamente
        return None
        
    except Exception as e:
        # Só loga se for erro real (não "no rows")
        if "no rows" not in str(e).lower():
            print(f"[DATABASE] ✗ Erro ao buscar sheet por product: {str(e)}")
        return None


def update_technical_sheet(
    sheet_id: str,
    data: dict,
    user_id: str,
    change_summary: Optional[str] = None
) -> bool:
    """
    Atualiza dados da ficha técnica.
    O trigger de versionamento cuida de incrementar versão e arquivar.
    
    Args:
        sheet_id: UUID da ficha
        data: Novos dados (JSONB)
        user_id: UUID do usuário que está alterando
        change_summary: Descrição opcional da mudança
    
    Returns:
        True se sucesso, False se falha
    """
    try:
        client = get_supabase_client()
        
        # Buscar sheet atual para preservar metadados
        current = get_technical_sheet(sheet_id)
        if not current:
            print(f"[DATABASE] ✗ Sheet não encontrada: {sheet_id}")
            return False
        
        # Mesclar dados preservando _version e _schema se não fornecidos
        current_data = current.get("data", {})
        new_data = {**data}
        
        if "_version" not in new_data:
            new_data["_version"] = current_data.get("_version", 1)
        if "_schema" not in new_data:
            new_data["_schema"] = current_data.get("_schema", "bag_v1")
        
        update_payload = {
            "data": new_data
        }
        
        response = client.table("technical_sheets")\
            .update(update_payload)\
            .eq("id", sheet_id)\
            .execute()
        
        if response.data:
            new_version = response.data[0].get("version", "?")
            print(f"[DATABASE] ✓ Sheet atualizada: {sheet_id} (v{new_version})")
            return True
        
        return False
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao atualizar sheet: {str(e)}")
        return False


def update_sheet_status(
    sheet_id: str,
    status: str,
    user_id: str,
    rejection_comment: Optional[str] = None
) -> bool:
    """
    Atualiza status da ficha técnica.
    
    Args:
        sheet_id: UUID da ficha
        status: Novo status (draft/pending/approved/rejected/published)
        user_id: UUID do usuário que está alterando
        rejection_comment: Comentário se status = rejected
    
    Returns:
        True se sucesso, False se falha
    """
    valid_statuses = ["draft", "pending", "approved", "rejected", "published"]
    if status not in valid_statuses:
        print(f"[DATABASE] ✗ Status inválido: {status}")
        return False
    
    try:
        client = get_supabase_client()
        
        update_payload = {"status": status}
        
        # Se aprovado, registrar quem aprovou e quando
        if status == "approved":
            from datetime import datetime
            update_payload["approved_by"] = user_id
            update_payload["approved_at"] = datetime.utcnow().isoformat()
        
        # Se rejeitado, registrar comentário
        if status == "rejected" and rejection_comment:
            update_payload["rejection_comment"] = rejection_comment
        
        response = client.table("technical_sheets")\
            .update(update_payload)\
            .eq("id", sheet_id)\
            .execute()
        
        if response.data:
            print(f"[DATABASE] ✓ Sheet status atualizado: {sheet_id} → {status}")
            return True
        
        return False
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao atualizar status da sheet: {str(e)}")
        return False


def get_sheet_versions(sheet_id: str) -> list:
    """
    Lista histórico de versões de uma ficha.
    
    Args:
        sheet_id: UUID da ficha
    
    Returns:
        Lista de versões ordenada por version DESC (mais recente primeiro)
    """
    try:
        client = get_supabase_client()
        
        response = client.table("technical_sheet_versions")\
            .select("*")\
            .eq("sheet_id", sheet_id)\
            .order("version", desc=True)\
            .execute()
        
        versions = response.data if response.data else []
        print(f"[DATABASE] ✓ {len(versions)} versões encontradas para sheet")
        return versions
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao listar versões da sheet: {str(e)}")
        return []


def get_sheet_version(sheet_id: str, version: int) -> Optional[dict]:
    """
    Busca uma versão específica da ficha.
    
    Args:
        sheet_id: UUID da ficha
        version: Número da versão
    
    Returns:
        Dict com dados da versão ou None
    """
    try:
        client = get_supabase_client()
        
        response = client.table("technical_sheet_versions")\
            .select("*")\
            .eq("sheet_id", sheet_id)\
            .eq("version", version)\
            .single()\
            .execute()
        
        if response.data:
            print(f"[DATABASE] ✓ Versão {version} encontrada")
            return response.data
        
        return None
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao buscar versão {version}: {str(e)}")
        return None


def delete_technical_sheet(sheet_id: str) -> bool:
    """
    Deleta ficha técnica (CASCADE deleta versões automaticamente).
    
    Args:
        sheet_id: UUID da ficha
    
    Returns:
        True se sucesso, False se falha
    """
    try:
        client = get_supabase_client()
        
        response = client.table("technical_sheets")\
            .delete()\
            .eq("id", sheet_id)\
            .execute()
        
        # Delete retorna dados deletados
        if response.data:
            print(f"[DATABASE] ✓ Sheet deletada: {sheet_id}")
            return True
        
        print(f"[DATABASE] ⚠ Nenhuma sheet deletada (pode não existir)")
        return False
        
    except Exception as e:
        print(f"[DATABASE] ✗ Erro ao deletar sheet: {str(e)}")
        return False
