"""
FRIDA Job Worker - Processamento assíncrono de imagens (PRD-04)

Responsabilidades:
1. Buscar próximo job na fila (FIFO)
2. Executar pipeline: segmentação → composição → validação
3. Atualizar progresso em cada etapa
4. Implementar retry com exponential backoff
5. Fallback de providers (remove.bg → rembg)
6. Salvar outputs no storage e banco

Uso:
    # Processar um job específico
    worker = JobWorker()
    worker.process_job("job-uuid")
    
    # Iniciar daemon (para uso com FastAPI)
    daemon = JobWorkerDaemon(poll_interval=2)
    daemon.start()
"""

import time
import threading
from typing import Optional, Tuple, Dict, Any
from io import BytesIO

from PIL import Image
from rembg import remove

# requests é opcional (apenas para remove.bg fallback)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from app.config import settings
from app.database import (
    get_job,
    get_next_queued_job,
    update_job_progress,
    increment_job_attempt,
    complete_job,
    fail_job,
    create_image,
    get_supabase_client
)
from app.services.image_composer import ImageComposer
from app.services.husk_layer import HuskLayer


# =============================================================================
# Job Worker
# =============================================================================

class JobWorker:
    """
    Worker para processamento de jobs de imagem.
    
    Pipeline:
    1. Segmentação (rembg) - remove fundo
    2. Composição (ImageComposer) - fundo branco + centralização + sombra
    3. Validação (HuskLayer) - quality score 0-100
    4. Upload - salvar no storage
    5. Registro - criar records em images table
    """
    
    # Configuração de etapas com progresso
    STEPS = {
        "downloading": (0, 20),     # progress: 0% → 20%
        "segmenting": (20, 50),     # progress: 20% → 50%
        "composing": (50, 75),      # progress: 50% → 75%
        "validating": (75, 85),     # progress: 75% → 85%
        "saving": (85, 95),         # progress: 85% → 95%
        "done": (95, 100)           # progress: 95% → 100%
    }
    
    # Retry configuration (exponential backoff)
    RETRY_DELAYS = [2, 4, 8]  # segundos
    MAX_ATTEMPTS = 3
    
    def __init__(self):
        """Inicializa worker com serviços de composição e validação."""
        self.composer = ImageComposer()
        self.husk = HuskLayer()
    
    def _get_client(self):
        """Cria novo client Supabase (evita cache)."""
        return get_supabase_client()
    
    def process_job(self, job_id: str) -> bool:
        """
        Processa um job completo.
        
        Args:
            job_id: UUID do job
            
        Returns:
            True se completou com sucesso, False se falhou
        """
        print(f"[WORKER] ══════════════════════════════════════")
        print(f"[WORKER] Iniciando job: {job_id}")
        
        job = get_job(job_id)
        if not job:
            print(f"[WORKER] ✗ Job não encontrado: {job_id}")
            return False
        
        if job["status"] not in ("queued", "failed"):
            print(f"[WORKER] ✗ Job em status inválido: {job['status']}")
            return False
        
        # Marcar como processing
        update_job_progress(job_id, status="processing", current_step="downloading", progress=5)
        
        try:
            input_data = job.get("input_data", {})
            original_path = input_data.get("original_path")
            
            if not original_path:
                raise ValueError("original_path não encontrado no input_data")
            
            # ============================================
            # ETAPA 1: Download da imagem original
            # ============================================
            print(f"[WORKER] 📥 Baixando imagem: {original_path}")
            update_job_progress(job_id, current_step="downloading", progress=10)
            
            original_bytes = self._download_from_storage("raw", original_path)
            
            update_job_progress(job_id, progress=20)
            print(f"[WORKER] ✓ Download concluído ({len(original_bytes)} bytes)")
            
            # ============================================
            # ETAPA 2: Segmentação com fallback
            # ============================================
            print(f"[WORKER] 🔪 Iniciando segmentação...")
            update_job_progress(job_id, current_step="segmenting", progress=25)
            
            segmented_bytes, provider_used = self._segment_with_fallback(original_bytes, job_id)
            
            update_job_progress(job_id, provider=provider_used, progress=50)
            print(f"[WORKER] ✓ Segmentação concluída com {provider_used} ({len(segmented_bytes)} bytes)")
            
            # ============================================
            # ETAPA 3: Composição (fundo branco)
            # ============================================
            print(f"[WORKER] 🎨 Iniciando composição...")
            update_job_progress(job_id, current_step="composing", progress=55)
            
            composed_bytes = self.composer.compose_from_bytes(segmented_bytes, target_size=1200)
            
            update_job_progress(job_id, progress=75)
            print(f"[WORKER] ✓ Composição concluída ({len(composed_bytes)} bytes)")
            
            # ============================================
            # ETAPA 4: Validação (quality score)
            # ============================================
            print(f"[WORKER] 🔍 Iniciando validação...")
            update_job_progress(job_id, current_step="validating", progress=78)
            
            quality_report = self.husk.validate_from_bytes(composed_bytes)
            quality_score = quality_report.score
            quality_passed = quality_report.passed
            
            update_job_progress(job_id, progress=85)
            status_emoji = "✅" if quality_passed else "⚠️"
            print(f"[WORKER] {status_emoji} Validação: score={quality_score}/100, passed={quality_passed}")
            
            # ============================================
            # ETAPA 5: Upload das imagens processadas
            # ============================================
            print(f"[WORKER] 📤 Salvando imagens no storage...")
            update_job_progress(job_id, current_step="saving", progress=88)
            
            product_id = job["product_id"]
            user_id = job["created_by"]
            
            client = self._get_client()
            
            # Upload segmented
            segmented_path = f"{user_id}/{product_id}/segmented.png"
            self._upload_to_storage(client, "segmented", segmented_path, segmented_bytes)
            segmented_url = client.storage.from_("segmented").get_public_url(segmented_path)
            
            update_job_progress(job_id, progress=92)
            
            # Upload processed
            processed_path = f"{user_id}/{product_id}/processed.png"
            self._upload_to_storage(client, "processed-images", processed_path, composed_bytes)
            processed_url = client.storage.from_("processed-images").get_public_url(processed_path)
            
            update_job_progress(job_id, progress=95)
            print(f"[WORKER] ✓ Imagens salvas no storage")
            
            # ============================================
            # ETAPA 6: Registrar imagens no banco
            # ============================================
            print(f"[WORKER] 💾 Registrando no banco...")
            
            # Registrar imagem segmentada
            try:
                segmented_record = create_image(
                    product_id=product_id,
                    type="segmented",
                    bucket="segmented",
                    path=segmented_path,
                    user_id=user_id
                )
                segmented_image_id = segmented_record.get("id") if segmented_record else None
            except Exception as e:
                print(f"[WORKER] ⚠️ Erro ao registrar segmented: {str(e)}")
                segmented_image_id = None
            
            # Registrar imagem processada
            try:
                processed_record = create_image(
                    product_id=product_id,
                    type="processed",
                    bucket="processed-images",
                    path=processed_path,
                    user_id=user_id
                )
                processed_image_id = processed_record.get("id") if processed_record else None
            except Exception as e:
                print(f"[WORKER] ⚠️ Erro ao registrar processed: {str(e)}")
                processed_image_id = None
            
            # ============================================
            # ETAPA 7: Completar job
            # ============================================
            update_job_progress(job_id, current_step="done", progress=100)
            
            output_data = {
                "images": {
                    "original": {
                        "bucket": "raw",
                        "path": original_path,
                        "url": input_data.get("original_url")
                    },
                    "segmented": {
                        "id": segmented_image_id,
                        "bucket": "segmented",
                        "path": segmented_path,
                        "url": segmented_url
                    },
                    "processed": {
                        "id": processed_image_id,
                        "bucket": "processed-images",
                        "path": processed_path,
                        "url": processed_url
                    }
                },
                "quality_score": quality_score,
                "quality_passed": quality_passed,
                "quality_details": quality_report.details,
                "provider_used": provider_used
            }
            
            complete_job(job_id, output_data)
            print(f"[WORKER] ══════════════════════════════════════")
            print(f"[WORKER] ✓ JOB COMPLETO: {job_id}")
            print(f"[WORKER] ══════════════════════════════════════")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"[WORKER] ✗ Erro no job {job_id}: {error_msg}")
            return self._handle_failure(job_id, error_msg)
    
    def _segment_with_fallback(self, image_bytes: bytes, job_id: str) -> Tuple[bytes, str]:
        """
        Segmenta imagem com fallback de providers.
        
        Tenta rembg (self-hosted) primeiro.
        Remove.bg pode ser adicionado como fallback.
        
        Returns:
            (segmented_bytes, provider_used)
        """
        providers = [
            ("rembg", self._segment_rembg),
            # ("remove.bg", self._segment_removebg),  # Descomentarquando tiver API key
        ]
        
        last_error = None
        
        for provider_name, provider_func in providers:
            try:
                print(f"[WORKER] Tentando segmentação com {provider_name}...")
                result = provider_func(image_bytes)
                return result, provider_name
            except Exception as e:
                last_error = str(e)
                print(f"[WORKER] ✗ {provider_name} falhou: {last_error}")
                continue
        
        # Todos os providers falharam
        raise Exception(f"Segmentação falhou com todos os providers. Último erro: {last_error}")
    
    def _segment_rembg(self, image_bytes: bytes) -> bytes:
        """Segmentação via rembg (U2NET local)."""
        return remove(image_bytes)
    
    def _segment_removebg(self, image_bytes: bytes) -> bytes:
        """
        Segmentação via remove.bg API.
        Requer REMOVEBG_API_KEY no .env e biblioteca requests instalada.
        """
        if not REQUESTS_AVAILABLE:
            raise ValueError("Biblioteca 'requests' não instalada. Execute: pip install requests")

        api_key = getattr(settings, 'REMOVEBG_API_KEY', None)
        if not api_key:
            raise ValueError("REMOVEBG_API_KEY não configurada")

        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": image_bytes},
            data={"size": "auto"},
            headers={"X-Api-Key": api_key}
        )

        if response.status_code != 200:
            raise Exception(f"remove.bg error: {response.status_code} - {response.text}")

        return response.content
    
    def _download_from_storage(self, bucket: str, path: str) -> bytes:
        """Download de arquivo do Supabase Storage."""
        client = self._get_client()
        response = client.storage.from_(bucket).download(path)
        return response
    
    def _upload_to_storage(self, client, bucket: str, path: str, data: bytes) -> str:
        """Upload de arquivo para Supabase Storage."""
        # Tentar remover arquivo existente (se houver)
        try:
            client.storage.from_(bucket).remove([path])
        except:
            pass  # Ignora se não existir
        
        client.storage.from_(bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": "image/png"}
        )
        return path
    
    def _handle_failure(self, job_id: str, error: str) -> bool:
        """
        Trata falha do job.
        
        Se ainda tem tentativas, volta para fila com backoff.
        Se esgotou tentativas, marca como failed definitivo.
        """
        result = increment_job_attempt(job_id, error, retry_delay_seconds=self._get_retry_delay(job_id))
        
        if result and result.get("should_retry"):
            # Ainda pode tentar
            attempt = result.get("attempts", 0)
            max_attempts = result.get("max_attempts", 3)
            
            print(f"[WORKER] ⏳ Job {job_id} aguardando retry (tentativa {attempt}/{max_attempts})")
            return False
        else:
            # Esgotou tentativas
            fail_job(job_id, f"Falhou após {self.MAX_ATTEMPTS} tentativas. Último erro: {error}")
            print(f"[WORKER] ✗ Job {job_id} falhou definitivamente")
            return False
    
    def _get_retry_delay(self, job_id: str) -> int:
        """Calcula delay para próxima tentativa (exponential backoff)."""
        job = get_job(job_id)
        if not job:
            return self.RETRY_DELAYS[0]
        
        attempts = job.get("attempts", 0)
        delay_index = min(attempts, len(self.RETRY_DELAYS) - 1)
        return self.RETRY_DELAYS[delay_index]


# =============================================================================
# Job Worker Daemon
# =============================================================================

class JobWorkerDaemon:
    """
    Daemon que roda em background processando jobs.
    
    Usa threading.Event para shutdown graceful e interruptível.
    
    Uso:
        daemon = JobWorkerDaemon(poll_interval=2)
        daemon.start()
        # ... aplicação roda ...
        daemon.stop()  # Aguarda job atual terminar
    """
    
    def __init__(self, poll_interval: int = 2):
        """
        Args:
            poll_interval: Intervalo em segundos entre polls da fila
        """
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
        self.worker = JobWorker()
        self.jobs_processed = 0
        self.jobs_failed = 0
        self._current_job_id = None  # Rastreia job em processamento
        self._stop_event = threading.Event()  # Evento para shutdown graceful
    
    def start(self):
        """Inicia daemon em thread separada."""
        if self.running:
            print("[DAEMON] Já está rodando")
            return
        
        self.running = True
        self._stop_event.clear()
        
        # daemon=False permite shutdown graceful (aguarda job atual)
        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=False,
            name="JobWorkerDaemon"
        )
        self.thread.start()
        print(f"[DAEMON] ✓ Iniciado (poll_interval={self.poll_interval}s)")
    
    def stop(self, timeout: int = 30):
        """
        Para o daemon gracefully.
        
        Args:
            timeout: Tempo máximo para aguardar job atual (default 30s)
        """
        if not self.running:
            return
        
        print("[DAEMON] Parando (aguardando job atual)...")
        self.running = False
        self._stop_event.set()  # Sinaliza para thread parar
        
        if self.thread:
            self.thread.join(timeout=timeout)
            
            if self.thread.is_alive():
                print(f"[DAEMON] ⚠ Timeout! Job {self._current_job_id} ainda processando")
            else:
                print(f"[DAEMON] ✓ Parado (processados={self.jobs_processed}, falhas={self.jobs_failed})")
    
    def _run_loop(self):
        """Loop principal do daemon com stop event interruptível."""
        print("[DAEMON] Loop iniciado, aguardando jobs...")
        
        while self.running and not self._stop_event.is_set():
            try:
                # Buscar próximo job
                job = get_next_queued_job()
                
                if job:
                    job_id = job["id"]
                    self._current_job_id = job_id
                    print(f"[DAEMON] 📋 Encontrou job: {job_id}")
                    
                    # Processar job
                    success = self.worker.process_job(job_id)
                    self._current_job_id = None
                    
                    if success:
                        self.jobs_processed += 1
                    else:
                        self.jobs_failed += 1
                    
                    # Verificar stop entre jobs
                    if self._stop_event.is_set():
                        break
                    
                    # Pequena pausa entre jobs
                    self._stop_event.wait(timeout=0.5)  # Interruptível
                else:
                    # Sem jobs, aguardar (interruptível pelo stop_event)
                    self._stop_event.wait(timeout=self.poll_interval)
                    
            except Exception as e:
                print(f"[DAEMON] ✗ Erro no loop: {str(e)}")
                self._stop_event.wait(timeout=self.poll_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do daemon."""
        return {
            "running": self.running,
            "current_job": self._current_job_id,
            "jobs_processed": self.jobs_processed,
            "jobs_failed": self.jobs_failed,
            "poll_interval": self.poll_interval
        }


# =============================================================================
# Instâncias Globais (para uso no FastAPI)
# =============================================================================

job_worker = JobWorker()
job_daemon = JobWorkerDaemon(poll_interval=2)
