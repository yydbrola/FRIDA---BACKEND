"""
Image Pipeline Service - FRIDA v0.5.2

Orquestra o pipeline completo de processamento de imagem:
1. Upload original → bucket 'raw' → type='original'
2. Segmentação (rembg) → bucket 'segmented' → type='segmented'
3. Composição → bucket 'processed-images' → type='processed'
4. Validação (husk_layer) → quality_score

Todas as versões são registradas na tabela 'images'.
"""

import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from io import BytesIO

from PIL import Image
from rembg import remove

from app.services.image_composer import image_composer
from app.services.husk_layer import husk_layer, QualityReport
from app.database import get_supabase_client, create_image
from app.config import settings


# =============================================================================
# Constants
# =============================================================================

BUCKETS = {
    "original": "raw",
    "segmented": "segmented",
    "processed": "processed-images"
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PipelineResult:
    """
    Resultado do processamento completo do pipeline.

    Attributes:
        success: Se o pipeline completou com sucesso
        product_id: ID do produto processado
        images: Dict com info de cada imagem {type: {id, bucket, path, url}}
        quality_report: Relatório de qualidade (se processado)
        error: Mensagem de erro (se falhou)
    """
    success: bool
    product_id: str
    images: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    quality_report: Optional[QualityReport] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        return {
            "success": self.success,
            "product_id": self.product_id,
            "images": self.images,
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "error": self.error
        }


# =============================================================================
# Pipeline Class
# =============================================================================

class ImagePipelineSync:
    """
    Pipeline síncrono de processamento de imagem (MVP).

    Processa imagem em 3 estágios, salvando cada versão no
    Supabase Storage e registrando na tabela images.
    """

    def __init__(self):
        """Inicializa o pipeline com thread-safe client loading."""
        self._client = None
        self._client_lock = threading.Lock()

    @property
    def client(self):
        """Thread-safe lazy load do Supabase client."""
        if self._client is None:
            with self._client_lock:
                # Double-check locking pattern
                if self._client is None:
                    self._client = get_supabase_client()
        return self._client
    
    # ==========================================================================
    # Método Principal
    # ==========================================================================
    
    def process_image(
        self,
        image_bytes: bytes,
        product_id: str,
        user_id: str,
        filename: str = "image.png"
    ) -> PipelineResult:
        """
        Executa pipeline completo de processamento.

        Args:
            image_bytes: Bytes da imagem original
            product_id: UUID do produto
            user_id: UUID do usuário
            filename: Nome original do arquivo

        Returns:
            PipelineResult com status e informações das imagens

        Note:
            Implementa rollback automático em caso de falha.
            Se qualquer etapa falhar, os arquivos já uploadados são removidos.
        """
        result = PipelineResult(
            success=False,
            product_id=product_id,
            images={}
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Lista de arquivos uploadados para rollback em caso de erro
        uploaded_files: list[tuple[str, str]] = []  # [(bucket, path), ...]

        try:
            print(f"[PIPELINE] Iniciando processamento para produto {product_id}")

            # =================================================================
            # STAGE 0: Validação de Segurança (DoS Protection)
            # =================================================================
            print("[PIPELINE] Stage 0: Validando arquivo...")

            # Validar tamanho do arquivo
            file_size = len(image_bytes)
            if file_size > settings.MAX_FILE_SIZE_BYTES:
                size_mb = file_size / (1024 * 1024)
                raise ValueError(
                    f"Arquivo muito grande: {size_mb:.1f}MB. "
                    f"Limite: {settings.MAX_FILE_SIZE_MB}MB"
                )

            # Validar dimensões da imagem (previne memory exhaustion)
            with BytesIO(image_bytes) as img_buffer:
                with Image.open(img_buffer) as img:
                    width, height = img.size
                    max_dim = max(width, height)
                    if max_dim > settings.MAX_IMAGE_DIMENSION:
                        raise ValueError(
                            f"Imagem muito grande: {width}x{height}px. "
                            f"Dimensão máxima: {settings.MAX_IMAGE_DIMENSION}px"
                        )
                    print(f"[PIPELINE] ✓ Validação OK: {file_size/1024:.1f}KB, {width}x{height}px")

            # =================================================================
            # STAGE 1: Upload Original
            # =================================================================
            print("[PIPELINE] Stage 1: Salvando original...")

            original_path = f"{product_id}/{timestamp}_original.png"
            original_url = self._upload_to_storage(
                bucket=BUCKETS["original"],
                path=original_path,
                data=image_bytes
            )

            if original_url:
                uploaded_files.append((BUCKETS["original"], original_path))
                original_record = self._create_image_record(
                    product_id=product_id,
                    image_type="original",
                    bucket=BUCKETS["original"],
                    path=original_path,
                    user_id=user_id
                )

                result.images["original"] = {
                    "id": original_record.get("id") if original_record else None,
                    "bucket": BUCKETS["original"],
                    "path": original_path,
                    "url": original_url
                }
                print(f"[PIPELINE] ✓ Original salvo: {original_path}")

            # =================================================================
            # STAGE 2: Segmentação (rembg)
            # =================================================================
            print("[PIPELINE] Stage 2: Removendo fundo...")

            # Remover fundo usando rembg com tratamento de erro específico
            try:
                segmented_bytes = remove(image_bytes)
            except MemoryError as e:
                raise RuntimeError(f"Memória insuficiente para processar imagem: {e}")
            except Exception as e:
                # rembg pode falhar por vários motivos: modelo não carregado, imagem corrompida, etc.
                raise RuntimeError(f"Erro na segmentação (rembg): {e}")

            if not segmented_bytes:
                raise RuntimeError("Segmentação retornou imagem vazia")

            segmented_path = f"{product_id}/{timestamp}_segmented.png"
            segmented_url = self._upload_to_storage(
                bucket=BUCKETS["segmented"],
                path=segmented_path,
                data=segmented_bytes
            )

            if segmented_url:
                uploaded_files.append((BUCKETS["segmented"], segmented_path))
                segmented_record = self._create_image_record(
                    product_id=product_id,
                    image_type="segmented",
                    bucket=BUCKETS["segmented"],
                    path=segmented_path,
                    user_id=user_id
                )

                result.images["segmented"] = {
                    "id": segmented_record.get("id") if segmented_record else None,
                    "bucket": BUCKETS["segmented"],
                    "path": segmented_path,
                    "url": segmented_url
                }
                print(f"[PIPELINE] ✓ Segmentado salvo: {segmented_path}")

            # =================================================================
            # STAGE 3: Composição (fundo branco)
            # =================================================================
            print("[PIPELINE] Stage 3: Compondo fundo branco...")

            # Compor com fundo branco usando image_composer
            processed_bytes = image_composer.compose_from_bytes(segmented_bytes)

            processed_path = f"{product_id}/{timestamp}_processed.png"
            processed_url = self._upload_to_storage(
                bucket=BUCKETS["processed"],
                path=processed_path,
                data=processed_bytes
            )

            if processed_url:
                uploaded_files.append((BUCKETS["processed"], processed_path))

            # =================================================================
            # STAGE 4: Validação de Qualidade
            # =================================================================
            print("[PIPELINE] Stage 4: Validando qualidade...")

            quality_report = husk_layer.validate_from_bytes(processed_bytes)
            result.quality_report = quality_report

            quality_score = quality_report.score if quality_report else None

            if processed_url:
                processed_record = self._create_image_record(
                    product_id=product_id,
                    image_type="processed",
                    bucket=BUCKETS["processed"],
                    path=processed_path,
                    user_id=user_id,
                    quality_score=quality_score
                )

                result.images["processed"] = {
                    "id": processed_record.get("id") if processed_record else None,
                    "bucket": BUCKETS["processed"],
                    "path": processed_path,
                    "url": processed_url,
                    "quality_score": quality_score
                }
                print(f"[PIPELINE] ✓ Processado salvo: {processed_path}")
            
            # =================================================================
            # Sucesso
            # =================================================================
            result.success = True
            print(f"[PIPELINE] ✓ Pipeline completo! Quality Score: {quality_score}/100")

        except Exception as e:
            error_msg = str(e)
            result.error = error_msg
            print(f"[PIPELINE] ❌ Erro: {error_msg}")

            # Rollback: remover arquivos já uploadados para evitar órfãos
            if uploaded_files:
                print(f"[PIPELINE] 🔄 Iniciando rollback de {len(uploaded_files)} arquivo(s)...")
                self._rollback_uploads(uploaded_files)

        return result
    
    # ==========================================================================
    # Métodos Auxiliares
    # ==========================================================================

    def _rollback_uploads(self, uploaded_files: list[tuple[str, str]]) -> None:
        """
        Remove arquivos já uploadados em caso de falha no pipeline.

        Args:
            uploaded_files: Lista de tuplas (bucket, path) dos arquivos a remover

        Note:
            Erros de remoção são logados mas não propagados,
            pois o pipeline já está em estado de erro.
        """
        for bucket, path in uploaded_files:
            try:
                self.client.storage.from_(bucket).remove([path])
                print(f"[PIPELINE] ✓ Rollback: removido {bucket}/{path}")
            except Exception as e:
                # Log mas não falha - já estamos em estado de erro
                print(f"[PIPELINE] ⚠️ Rollback falhou para {bucket}/{path}: {e}")

    def _upload_to_storage(
        self,
        bucket: str,
        path: str,
        data: bytes
    ) -> Optional[str]:
        """
        Upload de arquivo para Supabase Storage.
        
        Args:
            bucket: Nome do bucket
            path: Caminho do arquivo no bucket
            data: Bytes do arquivo
            
        Returns:
            URL pública do arquivo ou None se falhar
        """
        try:
            # Upload
            response = self.client.storage.from_(bucket).upload(
                path=path,
                file=data,
                file_options={"content-type": "image/png"}
            )
            
            # Gerar URL pública
            url_response = self.client.storage.from_(bucket).get_public_url(path)
            
            return url_response
            
        except Exception as e:
            print(f"[PIPELINE] ⚠️ Erro no upload ({bucket}/{path}): {str(e)}")
            return None
    
    def _create_image_record(
        self,
        product_id: str,
        image_type: str,
        bucket: str,
        path: str,
        user_id: str,
        quality_score: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Registra imagem na tabela images.
        
        Args:
            product_id: UUID do produto
            image_type: Tipo (original, segmented, processed)
            bucket: Nome do bucket
            path: Caminho no storage
            user_id: UUID do usuário
            quality_score: Score de qualidade (0-100)
            
        Returns:
            Dict com dados do registro ou None se falhar
        """
        try:
            # Usar função do database.py
            record = create_image(
                product_id=product_id,
                type=image_type,
                bucket=bucket,
                path=path,
                user_id=user_id
            )
            
            # Atualizar quality_score se fornecido
            if quality_score is not None and record:
                try:
                    self.client.table('images').update({
                        'quality_score': quality_score
                    }).eq('id', record['id']).execute()
                except Exception as e:
                    # Logar erro mas não falhar o pipeline por causa do score
                    print(f"[PIPELINE] ⚠️ Erro ao atualizar quality_score: {e}")
            
            return record
            
        except Exception as e:
            print(f"[PIPELINE] ⚠️ Erro ao criar registro: {str(e)}")
            return None


# =============================================================================
# Singleton Export
# =============================================================================

image_pipeline_sync = ImagePipelineSync()
