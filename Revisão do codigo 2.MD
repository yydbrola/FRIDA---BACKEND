# REVIEW.MD - Code Review com Context7 (PRD 4 - Async Jobs)

**Data da Revisao:** 2026-01-14
**Versao do Projeto:** 0.5.4
**Ferramenta:** Context7 (Documentacao Atualizada)
**Revisor:** Claude Opus 4.5

---

## Resumo Executivo

| Categoria | Status | Prioridade |
|-----------|--------|------------|
| PRD 4 - Jobs Async | IMPLEMENTADO | - |
| FastAPI Lifecycle (startup) | DEPRECADO | Alta |
| Daemon Thread Graceful Shutdown | MELHORIA | Media |
| Supabase Client Thread Safety | OK | - |
| State Machine Jobs | OK | - |
| RLS Policies Jobs | OK | - |
| Endpoints REST | OK | - |
| Retry Logic (Exponential Backoff) | OK | - |

---

## Verificacao PRD 4 - Arquivos Implementados

### Arquivos Criados

| Arquivo | Descricao | Status |
|---------|-----------|--------|
| `app/services/job_worker.py` | JobWorker + JobWorkerDaemon | OK |
| `SQL para o SUPABASE/07_create_jobs_table.sql` | Schema tabela jobs | OK |
| `scripts/test_prd04_jobs.py` | Suite de testes PRD 04 | OK |

### Funcoes CRUD Adicionadas (database.py)

| Funcao | Linhas | Status |
|--------|--------|--------|
| `create_job()` | 240-286 | OK |
| `get_job()` | 289-311 | OK |
| `get_job_by_product()` | 314-341 | OK |
| `update_job_progress()` | 344-398 | OK |
| `increment_job_attempt()` | 401-459 | OK |
| `complete_job()` | 462-503 | OK |
| `fail_job()` | 506-541 | OK |
| `get_next_queued_job()` | 544-597 | OK |
| `get_user_jobs()` | 600-627 | OK |

### Endpoints Implementados (main.py)

| Endpoint | Metodo | Linhas | Status |
|----------|--------|--------|--------|
| `/process-async` | POST | 552-736 | OK |
| `/jobs/{job_id}` | GET | 743-805 | OK |
| `/jobs` | GET | 808-846 | OK |

---

## 1. FastAPI - `@app.on_event` DEPRECADO (Persistente)

**Severidade:** Alta
**Arquivo:** `app/main.py`
**Linhas:** 232-269

### Problema

O decorator `@app.on_event("startup")` e `@app.on_event("shutdown")` continuam em uso, apesar de estarem **depreciados** no FastAPI. A documentacao oficial (Context7) confirma que devem ser substituidos pelo `lifespan` context manager.

### Evidencia (Context7)

> "**on_startup** (Optional[Sequence[Callable]]) - **Deprecated**. A list of startup event handler functions. **Use lifespan instead.**"
>
> "The lifespan approach is the modern standard for handling application lifecycle."

### Codigo Atual (Problematico)

```python
# app/main.py:232-269
@app.on_event("startup")
async def startup_event():
    """Inicializa servicos no startup..."""
    global classifier_service, background_service, tech_sheet_service, storage_service
    # ... inicializacao de servicos

    # Iniciar Job Worker Daemon (PRD-04)
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            job_daemon.start()  # Inicia thread daemon
            print("[STARTUP] JobWorkerDaemon iniciado")
        except Exception as e:
            print(f"[STARTUP] JobWorkerDaemon nao iniciado: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Para servicos no shutdown..."""
    try:
        job_daemon.stop()
        print("[SHUTDOWN] JobWorkerDaemon parado")
    except Exception as e:
        print(f"[SHUTDOWN] Erro ao parar JobWorkerDaemon: {e}")
```

### Correcao Recomendada

```python
# app/main.py - SUBSTITUIR eventos por lifespan

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicacao.
    Substitui @app.on_event("startup"/"shutdown") depreciados.
    """
    global classifier_service, background_service, tech_sheet_service, storage_service

    # === STARTUP ===
    print("[STARTUP] Iniciando Frida Orchestrator v0.5.4...")

    # Validacao de configuracoes obrigatorias
    if not settings.GEMINI_API_KEY:
        raise StartupError("[STARTUP] FALHA CRITICA: GEMINI_API_KEY nao configurada!")

    # Inicializacao de servicos
    try:
        background_service = BackgroundRemoverService()
        classifier_service = ClassifierService()
        tech_sheet_service = TechSheetService()
        print("[STARTUP] Servicos criticos inicializados")
    except Exception as e:
        raise StartupError(f"[STARTUP] FALHA CRITICA: {e}")

    # Storage opcional
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            storage_service = StorageService()
            print("[STARTUP] StorageService inicializado")
        except Exception:
            print("[STARTUP] StorageService nao inicializado (opcional)")

        # Iniciar Job Worker Daemon (PRD-04)
        try:
            job_daemon.start()
            print("[STARTUP] JobWorkerDaemon iniciado")
        except Exception as e:
            print(f"[STARTUP] JobWorkerDaemon nao iniciado: {e}")

    print("[STARTUP] Servidor pronto!")

    yield  # === APLICACAO RODANDO ===

    # === SHUTDOWN ===
    print("[SHUTDOWN] Encerrando servicos...")

    try:
        job_daemon.stop()
        print("[SHUTDOWN] JobWorkerDaemon parado")
    except Exception as e:
        print(f"[SHUTDOWN] Erro ao parar JobWorkerDaemon: {e}")

# Criar app com lifespan
app = FastAPI(
    title="Frida Orchestrator",
    description="Backend de processamento de imagens e IA para produtos de moda",
    version="0.5.4",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # NOVO - substitui on_event
)
```

---

## 2. Daemon Thread - Graceful Shutdown Limitado

**Severidade:** Media
**Arquivo:** `app/services/job_worker.py`
**Linhas:** 379-455

### Problema

O `JobWorkerDaemon` usa `threading.Thread(daemon=True)` que termina abruptamente quando o processo principal encerra. O `stop()` atual usa `join(timeout=10)` mas nao ha garantia de que o job atual sera finalizado corretamente.

### Codigo Atual

```python
# app/services/job_worker.py:402-424
def start(self):
    """Inicia daemon em thread separada."""
    if self.running:
        return

    self.running = True
    self.thread = threading.Thread(
        target=self._run_loop,
        daemon=True,  # Thread termina com processo principal
        name="JobWorkerDaemon"
    )
    self.thread.start()

def stop(self):
    """Para o daemon gracefully."""
    if not self.running:
        return

    self.running = False

    if self.thread:
        self.thread.join(timeout=10)  # Espera ate 10s
```

### Melhoria Recomendada

```python
# app/services/job_worker.py - Adicionar sinal de interrupcao

import signal
import threading

class JobWorkerDaemon:
    def __init__(self, poll_interval: int = 2):
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
        self.worker = JobWorker()
        self.jobs_processed = 0
        self.jobs_failed = 0
        self._current_job_id = None  # Track job atual
        self._stop_event = threading.Event()  # Evento de parada

    def start(self):
        """Inicia daemon em thread separada."""
        if self.running:
            return

        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=False,  # NAO daemon - permite graceful shutdown
            name="JobWorkerDaemon"
        )
        self.thread.start()
        print(f"[DAEMON] Iniciado (poll_interval={self.poll_interval}s)")

    def stop(self, timeout: int = 30):
        """
        Para o daemon gracefully.

        Args:
            timeout: Tempo maximo para aguardar job atual (default 30s)
        """
        if not self.running:
            return

        print("[DAEMON] Parando (aguardando job atual)...")
        self.running = False
        self._stop_event.set()

        if self.thread:
            self.thread.join(timeout=timeout)

            if self.thread.is_alive():
                print(f"[DAEMON] Timeout! Job {self._current_job_id} ainda processando")
            else:
                print(f"[DAEMON] Parado (processados={self.jobs_processed})")

    def _run_loop(self):
        """Loop principal com verificacao de stop event."""
        while self.running and not self._stop_event.is_set():
            try:
                job = get_next_queued_job()

                if job:
                    self._current_job_id = job["id"]
                    success = self.worker.process_job(job["id"])
                    self._current_job_id = None

                    if success:
                        self.jobs_processed += 1
                    else:
                        self.jobs_failed += 1

                    # Verificar stop entre jobs
                    if self._stop_event.is_set():
                        break
                else:
                    # Aguardar com stop event (interruptivel)
                    self._stop_event.wait(timeout=self.poll_interval)

            except Exception as e:
                print(f"[DAEMON] Erro: {str(e)}")
                self._stop_event.wait(timeout=self.poll_interval)
```

---

## 3. Itens Verificados - OK

### 3.1 State Machine Jobs - Implementacao Correta

**Arquivo:** `SQL para o SUPABASE/07_create_jobs_table.sql`
**Status:** OK

A state machine esta corretamente implementada:
- Estados: `queued` -> `processing` -> `completed` / `failed`
- CHECK constraints garantem valores validos
- Trigger auto-preenche `started_at` e `completed_at`

```sql
-- CORRETO
status TEXT NOT NULL DEFAULT 'queued' CHECK (
    status IN ('queued', 'processing', 'completed', 'failed')
)
```

### 3.2 Retry Logic com Exponential Backoff - Implementacao Correta

**Arquivo:** `app/services/job_worker.py`
**Linhas:** 71-73, 342-372

```python
# CORRETO
RETRY_DELAYS = [2, 4, 8]  # segundos - exponential backoff
MAX_ATTEMPTS = 3

def _get_retry_delay(self, job_id: str) -> int:
    """Calcula delay para proxima tentativa."""
    job = get_job(job_id)
    attempts = job.get("attempts", 0) if job else 0
    delay_index = min(attempts, len(self.RETRY_DELAYS) - 1)
    return self.RETRY_DELAYS[delay_index]
```

### 3.3 Provider Fallback - Estrutura Correta

**Arquivo:** `app/services/job_worker.py`
**Linhas:** 264-292

```python
# CORRETO - Fallback preparado para extensao
def _segment_with_fallback(self, image_bytes: bytes, job_id: str):
    providers = [
        ("rembg", self._segment_rembg),
        # ("remove.bg", self._segment_removebg),  # Futuro
    ]

    for provider_name, provider_func in providers:
        try:
            result = provider_func(image_bytes)
            return result, provider_name
        except Exception as e:
            continue
```

### 3.4 RLS Policies Jobs - Dual Mode Implementado

**Arquivo:** `SQL para o SUPABASE/07_create_jobs_table.sql`
**Linhas:** 175-261

As 4 policies (SELECT, INSERT, UPDATE, DELETE) seguem o padrao dual-mode:
- Dev mode: `auth.uid() IS NULL`
- User mode: `created_by = auth.uid()`
- Admin mode: `users.role = 'admin'`

```sql
-- CORRETO
CREATE POLICY "jobs_select_policy" ON public.jobs
    FOR SELECT
    USING (
        auth.uid() IS NULL  -- Dev mode
        OR created_by = auth.uid()  -- Proprio usuario
        OR EXISTS (SELECT 1 FROM public.users WHERE ...)  -- Admin
    );
```

### 3.5 GRANTS para service_role - Aplicado

**Arquivo:** `SQL para o SUPABASE/07_create_jobs_table.sql`
**Linhas:** 264-275

```sql
-- CORRETO
GRANT ALL ON public.jobs TO service_role;
GRANT ALL ON public.jobs TO authenticated;
GRANT SELECT ON public.jobs TO anon;
```

### 3.6 Supabase Client - Padrao Correto

**Arquivo:** `app/services/job_worker.py`
**Linhas:** 80-82

O worker cria novo client por operacao, evitando problemas de cache:

```python
# CORRETO
def _get_client(self):
    """Cria novo client Supabase (evita cache)."""
    return get_supabase_client()
```

### 3.7 Endpoints REST - Padrao Correto

**Arquivo:** `app/main.py`
**Linhas:** 552-846

| Endpoint | Descricao | Status |
|----------|-----------|--------|
| `POST /process-async` | Enfileira job, retorna imediatamente | OK |
| `GET /jobs/{job_id}` | Polling de status com progress bar | OK |
| `GET /jobs` | Lista jobs do usuario | OK |

---

## 4. Pontos de Atencao (Nao-Criticos)

### 4.1 Memory Management no Worker

**Arquivo:** `app/services/job_worker.py`
**Status:** OK (ja corrigido PRD 03)

O worker usa `ImageComposer` e `HuskLayer` que ja foram corrigidos para fechar recursos corretamente (ver Revisao do codigo 1.MD).

### 4.2 Timeout de Jobs Longos

**Status:** Nao Implementado (opcional)

Atualmente nao ha timeout maximo para um job individual. Um job preso pode bloquear o daemon indefinidamente.

**Sugestao para futuro:**
```python
# Adicionar timeout ao process_job
import signal

def process_job_with_timeout(self, job_id: str, timeout: int = 300):
    """Processa job com timeout de 5 minutos."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Job {job_id} excedeu timeout de {timeout}s")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        return self.process_job(job_id)
    finally:
        signal.alarm(0)
```

### 4.3 Metricas e Observabilidade

**Status:** Basico Implementado

O daemon tem `jobs_processed` e `jobs_failed` mas nao expoe metricas estruturadas.

**Sugestao para futuro:**
- Endpoint `/metrics` com Prometheus format
- Integracao com logging estruturado (JSON)

---

## Checklist de Acoes

- [x] **PRD 4** - Jobs Async implementado com sucesso
- [x] **SQL** - Tabela jobs com state machine e RLS
- [x] **CRUD** - 9 funcoes no database.py
- [x] **Endpoints** - 3 endpoints REST funcionais
- [x] **Worker** - JobWorker + JobWorkerDaemon
- [x] **Retry** - Exponential backoff implementado
- [x] **ALTA** - Migrar `@app.on_event` para `lifespan` ✅ APLICADO (2026-01-14 01:45)
- [x] **MEDIA** - Melhorar graceful shutdown do daemon ✅ APLICADO (2026-01-14 01:45)
- [ ] **BAIXA** - Adicionar timeout de jobs
- [ ] **BAIXA** - Endpoint de metricas

---

## Testes PRD 4

### Script de Teste

**Arquivo:** `scripts/test_prd04_jobs.py`

### Categorias de Teste

| Categoria | Descricao |
|-----------|-----------|
| `--test-db` | Testa funcoes CRUD do banco |
| `--test-worker` | Testa worker isolado |
| `--test-api` | Testa endpoints via HTTP |
| `--all` | Executa todos os testes |

### Comando de Execucao

```bash
# Teste completo
python scripts/test_prd04_jobs.py --all

# Apenas endpoints (requer servidor rodando)
python scripts/test_prd04_jobs.py --test-api
```

---

## Conclusao

**PRD 4 (Async Jobs) foi implementado com SUCESSO.**

A implementacao segue os requisitos:
- State machine com 4 estados
- Retry com exponential backoff
- Provider fallback preparado
- RLS dual-mode
- Endpoints REST completos

**Correcoes aplicadas (v0.5.4):**
- ✅ Migracao `@app.on_event` → `lifespan` context manager
- ✅ Graceful shutdown do daemon com `threading.Event`

---

## Referencias

- [FastAPI Lifespan Documentation](https://fastapi.tiangolo.com/advanced/events/)
- [Supabase Python Client](https://supabase.com/docs/reference/python/)
- [Python Threading Best Practices](https://docs.python.org/3/library/threading.html)
- Context7 Library Documentation (2026-01-14)

---

**Fim do Documento**
**Ultima atualizacao:** 2026-01-14 10:30 BRT
**Implementado por:** Claude (Anthropic)
