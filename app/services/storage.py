"""
Frida Orchestrator - Storage Service
Serviço de armazenamento no Supabase para auditoria de imagens processadas.

IMPORTANTE: Este serviço é OPCIONAL. Se as credenciais do Supabase não estiverem
configuradas, a API funciona normalmente sem persistência.

Estrutura de arquivos no Storage:
- {user_id}/{product_id}/{timestamp}_{unique_id}.png (se product_id fornecido)
- {user_id}/{timestamp}_{unique_id}.png (se não)
"""

import uuid
from datetime import datetime
from typing import Optional, TypedDict

from supabase import create_client, Client

from app.config import settings


class StorageResult(TypedDict):
    """Resultado do armazenamento."""
    success: bool
    image_url: Optional[str]
    record_id: Optional[str]
    error: Optional[str]


class StorageService:
    """
    Serviço de armazenamento no Supabase.
    
    Funcionalidades:
    - Upload de imagens processadas para Supabase Storage
    - Registro de auditoria na tabela historico_geracoes
    - Organização por namespace: user_id/product_id/
    
    NOTA: Este serviço é não-bloqueante. Erros de storage não
    impedem o retorno da resposta ao cliente.
    """
    
    BUCKET_NAME = "processed-images"
    TABLE_NAME = "historico_geracoes"
    
    def __init__(self):
        """Inicializa o cliente Supabase."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError(
                "Supabase não configurado. Configure SUPABASE_URL e SUPABASE_KEY no .env"
            )
        
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        
        print("[StorageService] Cliente Supabase inicializado")
    
    def upload_image(
        self, 
        image_bytes: bytes, 
        user_id: str,
        categoria: str,
        product_id: Optional[str] = None,
        extension: str = "png"
    ) -> tuple[bool, Optional[str]]:
        """
        Faz upload de imagem para o Supabase Storage com namespace por usuário.
        
        Args:
            image_bytes: Bytes da imagem processada
            user_id: ID do usuário (obrigatório para namespace)
            categoria: Categoria do produto (para metadados)
            product_id: ID do produto (opcional, organiza em subpasta)
            extension: Extensão do arquivo
            
        Returns:
            Tuple (success: bool, url: str | None)
        """
        try:
            # Gera nome único para o arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{timestamp}_{unique_id}.{extension}"
            
            # Constrói path com namespace por user_id
            if product_id:
                path = f"{user_id}/{product_id}/{filename}"
            else:
                path = f"{user_id}/{filename}"
            
            # Upload para o bucket
            response = self.client.storage.from_(self.BUCKET_NAME).upload(
                path=path,
                file=image_bytes,
                file_options={"content-type": f"image/{extension}"}
            )
            
            # Obtém URL pública
            public_url = self.client.storage.from_(self.BUCKET_NAME).get_public_url(path)
            
            print(f"[StorageService] ✅ Image uploaded for user {user_id}: {path}")
            return True, public_url
            
        except Exception as e:
            print(f"[StorageService] Erro no upload: {e}")
            return False, None
    
    def registrar_geracao(
        self,
        user_id: str,
        categoria: str,
        estilo: str,
        confianca: float,
        image_url: Optional[str],
        ficha_tecnica: Optional[dict],
        product_id: Optional[str] = None,
        image_filename: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Registra uma geração na tabela de histórico para auditoria.
        
        Args:
            user_id: ID do usuário que fez a requisição
            categoria: Categoria classificada do produto
            estilo: Estilo da imagem (sketch/foto)
            confianca: Confiança da classificação
            image_url: URL pública da imagem no Storage
            ficha_tecnica: Dados da ficha técnica (JSON)
            product_id: ID do produto associado (opcional)
            image_filename: Nome original do arquivo
            processing_time_ms: Tempo de processamento em ms
            
        Returns:
            Tuple (success: bool, record_id: str | None)
        """
        try:
            record = {
                "user_id": user_id,
                "categoria": categoria,
                "estilo": estilo,
                "confianca": confianca,
                "image_url": image_url,
                "ficha_tecnica": ficha_tecnica,
                "product_id": product_id,
                "image_filename": image_filename,
                "processing_time_ms": processing_time_ms
            }
            
            response = self.client.table(self.TABLE_NAME).insert(record).execute()
            
            if response.data and len(response.data) > 0:
                record_id = response.data[0].get("id")
                print(f"[StorageService] ✅ Registro criado para user {user_id}: {record_id}")
                return True, record_id
            
            return False, None
            
        except Exception as e:
            print(f"[StorageService] Erro ao registrar: {e}")
            return False, None
    
    def processar_e_registrar(
        self,
        image_bytes: bytes,
        user_id: str,
        categoria: str,
        estilo: str,
        confianca: float,
        ficha_tecnica: Optional[dict] = None,
        product_id: Optional[str] = None,
        original_filename: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ) -> StorageResult:
        """
        Método principal: faz upload da imagem E registra no histórico.
        
        Este método encapsula o fluxo completo de persistência para
        auditoria empresarial.
        
        Args:
            image_bytes: Imagem processada em bytes
            user_id: ID do usuário (obrigatório)
            categoria: Categoria do produto
            estilo: sketch ou foto
            confianca: Confiança da classificação
            ficha_tecnica: Dados da ficha técnica (opcional)
            product_id: ID do produto (opcional)
            original_filename: Nome original do arquivo
            processing_time_ms: Tempo de processamento
            
        Returns:
            StorageResult com status e URLs
        """
        # 1. Upload da imagem com namespace
        upload_success, image_url = self.upload_image(
            image_bytes=image_bytes,
            user_id=user_id,
            categoria=categoria,
            product_id=product_id
        )
        
        if not upload_success:
            return StorageResult(
                success=False,
                image_url=None,
                record_id=None,
                error="Falha no upload da imagem"
            )
        
        # 2. Registra no histórico
        record_success, record_id = self.registrar_geracao(
            user_id=user_id,
            categoria=categoria,
            estilo=estilo,
            confianca=confianca,
            image_url=image_url,
            ficha_tecnica=ficha_tecnica,
            product_id=product_id,
            image_filename=original_filename,
            processing_time_ms=processing_time_ms
        )
        
        if not record_success:
            # Upload OK mas registro falhou - ainda retorna a URL
            return StorageResult(
                success=False,
                image_url=image_url,
                record_id=None,
                error="Imagem salva mas falha no registro de auditoria"
            )
        
        return StorageResult(
            success=True,
            image_url=image_url,
            record_id=record_id,
            error=None
        )

