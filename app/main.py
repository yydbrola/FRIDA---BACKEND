"""
Frida Orchestrator - FastAPI Main Application
Ponto de entrada da API e definição das rotas de upload e processamento.
"""

import io
import base64
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings, APP_VERSION
from app.utils import validate_image_file, validate_image_deep, generate_filename
from app.services.classifier import ClassifierService
from app.services.background_remover import BackgroundRemoverService
from app.services.tech_sheet import TechSheetService
from app.services.storage import StorageService
from app.services.image_pipeline import image_pipeline_sync
from app.auth import get_current_user, AuthUser
from app.database import (
    create_product, get_user_products, create_image, get_supabase_client,
    create_job, get_job, get_user_jobs,
    # Technical Sheets CRUD (PRD-05)
    create_technical_sheet, get_technical_sheet, get_sheet_by_product,
    update_technical_sheet, update_sheet_status,
    get_sheet_versions, get_sheet_version, delete_technical_sheet
)
from app.services.job_worker import job_daemon
from app.services.pdf_generator import pdf_generator


# =============================================================================
# App Initialization
# =============================================================================

# FastAPI app criado sem lifespan (será configurado após definição)
# O lifespan é definido após os Response Models
app = FastAPI(
    title="Frida Orchestrator",
    description="Backend de processamento de imagens e IA para produtos de moda",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate Limiting Configuration
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS para permitir requests do frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js dev
        "http://127.0.0.1:3000",      # Next.js dev (alt)
        "https://*.vercel.app",       # Vercel preview/prod
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Response Models
# =============================================================================

class ProcessResponse(BaseModel):
    """Resposta do endpoint de processamento."""
    status: str
    product_id: Optional[str] = None
    categoria: str
    estilo: str
    confianca: float
    imagem_base64: Optional[str] = None  # Base64 da imagem processada (fallback local)
    imagem_url: Optional[str] = None  # URL da imagem no storage (pipeline completo)
    ficha_tecnica: Optional[dict] = None
    mensagem: Optional[str] = None
    # Novos campos para pipeline v0.5.3
    images: Optional[dict] = None  # {original, segmented, processed}
    quality_score: Optional[int] = None  # 0-100
    quality_passed: Optional[bool] = None  # score >= 80


class ProcessAsyncResponse(BaseModel):
    """Resposta do endpoint de processamento assíncrono."""
    status: str  # "processing"
    job_id: str
    product_id: str
    classification: dict
    message: str


class JobStatusResponse(BaseModel):
    """Response para GET /jobs/{job_id}"""
    job_id: str
    product_id: str
    status: str  # queued, processing, completed, failed
    current_step: Optional[str] = None
    progress: int = 0
    attempts: int = 0
    max_attempts: int = 3
    
    # Timestamps
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    
    # Para status = "completed"
    images: Optional[Dict[str, Any]] = None
    quality_score: Optional[int] = None
    quality_passed: Optional[bool] = None
    
    # Para status = "failed"
    last_error: Optional[str] = None
    can_retry: bool = False


class JobListItem(BaseModel):
    """Item resumido para listagem de jobs."""
    job_id: str
    product_id: str
    status: str
    progress: int
    current_step: Optional[str] = None
    created_at: str


class JobListResponse(BaseModel):
    """Response para GET /jobs"""
    jobs: List[JobListItem]
    total: int


class HealthResponse(BaseModel):
    """Resposta do health check com status detalhado."""
    status: str
    version: str
    gemini_configured: bool
    services: dict  # Status de cada serviço
    ready: bool  # True se todos os serviços críticos estão OK
    configuration: dict  # Status de configurações
    warnings: Optional[list] = None  # Avisos de configuração


class StartupError(Exception):
    """Exceção para falhas críticas durante inicialização."""
    pass


# =============================================================================
# Service Instances
# =============================================================================

classifier_service: Optional[ClassifierService] = None
background_service: Optional[BackgroundRemoverService] = None
tech_sheet_service: Optional[TechSheetService] = None
storage_service: Optional[StorageService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação usando lifespan context manager.
    
    Substitui @app.on_event("startup") e @app.on_event("shutdown") depreciados.
    Esta é a abordagem recomendada pelo FastAPI para gerenciar lifecycle.
    
    Comportamento:
    - Se GEMINI_API_KEY não estiver configurada: FALHA CRÍTICA
    - Se BackgroundRemoverService falhar: FALHA CRÍTICA
    - Se ClassifierService falhar: FALHA CRÍTICA
    
    A API NÃO inicia em estado inconsistente.
    """
    global classifier_service, background_service, tech_sheet_service, storage_service
    
    # =========================================================================
    # STARTUP
    # =========================================================================
    print(f"[STARTUP] Iniciando Frida Orchestrator v{APP_VERSION}...")
    
    # -------------------------------------------------------------------------
    # 1. Validação de Configurações OBRIGATÓRIAS (Fail Fast)
    # -------------------------------------------------------------------------
    
    if not settings.GEMINI_API_KEY:
        error_msg = (
            "[STARTUP] FALHA CRÍTICA: GEMINI_API_KEY não configurada!\n"
            "  A API do Gemini é obrigatória para o funcionamento do Frida.\n"
            "  Configure a variável de ambiente no arquivo .env:\n"
            "    GEMINI_API_KEY=sua_chave_aqui\n"
            "  Obtenha sua chave em: https://aistudio.google.com/apikey"
        )
        print(error_msg)
        raise StartupError(error_msg)
    
    print("[STARTUP] ✓ GEMINI_API_KEY configurada")
    
    # -------------------------------------------------------------------------
    # 2. Inicialização de Serviços CRÍTICOS (Fail Fast)
    # -------------------------------------------------------------------------
    
    # 2.1 BackgroundRemoverService (obrigatório para /process)
    try:
        background_service = BackgroundRemoverService()
        print("[STARTUP] ✓ BackgroundRemoverService inicializado")
    except Exception as e:
        error_msg = f"[STARTUP] FALHA CRÍTICA: BackgroundRemoverService não pôde ser inicializado: {e}"
        print(error_msg)
        raise StartupError(error_msg) from e
    
    # 2.2 ClassifierService (obrigatório para classificação IA)
    try:
        classifier_service = ClassifierService()
        print("[STARTUP] ✓ ClassifierService inicializado")
    except Exception as e:
        error_msg = f"[STARTUP] FALHA CRÍTICA: ClassifierService não pôde ser inicializado: {e}"
        print(error_msg)
        raise StartupError(error_msg) from e
    
    # 2.3 TechSheetService (obrigatório para fichas técnicas)
    try:
        tech_sheet_service = TechSheetService()
        print("[STARTUP] ✓ TechSheetService inicializado")
    except Exception as e:
        error_msg = f"[STARTUP] FALHA CRÍTICA: TechSheetService não pôde ser inicializado: {e}"
        print(error_msg)
        raise StartupError(error_msg) from e
    
    # -------------------------------------------------------------------------
    # 3. Validações Opcionais (Avisos, não bloqueantes)
    # -------------------------------------------------------------------------
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        print("[STARTUP] ⚠ Supabase não configurado (storage e auditoria desabilitados)")
    else:
        try:
            storage_service = StorageService()
            print("[STARTUP] ✓ StorageService inicializado")
        except Exception as e:
            print(f"[STARTUP] ⚠ StorageService não inicializado (opcional): {e}")
            # Não bloqueia - storage é opcional
    
    print("[STARTUP] ======================================")
    print("[STARTUP] ✓ Todos os serviços inicializados com sucesso!")
    print(f"[STARTUP] ✓ Servidor pronto em http://{settings.HOST}:{settings.PORT}")
    
    # Status de autenticação
    if settings.AUTH_ENABLED:
        if settings.SUPABASE_JWT_SECRET:
            print("[STARTUP] ✓ Authentication ENABLED with JWT validation")
        else:
            print("[STARTUP] ⚠ AUTH_ENABLED=true but SUPABASE_JWT_SECRET not set!")
    else:
        print("[STARTUP] ⚠ Authentication DISABLED (development mode)")
    
    print("[STARTUP] ======================================")
    
    # -------------------------------------------------------------------------
    # 4. Iniciar Job Worker Daemon (PRD-04)
    # -------------------------------------------------------------------------
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            job_daemon.start()
            print("[STARTUP] ✓ JobWorkerDaemon iniciado (processamento async)")
        except Exception as e:
            print(f"[STARTUP] ⚠ JobWorkerDaemon não iniciado (opcional): {e}")
    else:
        print("[STARTUP] ⚠ JobWorkerDaemon não iniciado (Supabase não configurado)")
    
    print("[STARTUP] ======================================")
    
    # =========================================================================
    # YIELD - Aplicação rodando
    # =========================================================================
    yield
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    print("[SHUTDOWN] Encerrando serviços...")
    
    # Parar Job Worker Daemon
    try:
        job_daemon.stop()
        print("[SHUTDOWN] ✓ JobWorkerDaemon parado")
    except Exception as e:
        print(f"[SHUTDOWN] ⚠ Erro ao parar JobWorkerDaemon: {e}")
    
    print("[SHUTDOWN] ✓ Encerramento completo")


# Atribuir lifespan ao app (definido após a função para evitar forward reference)
app.router.lifespan_context = lifespan


# =============================================================================
# Routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Página inicial com informações da API."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Frida Orchestrator</title>
        <style>
            body { font-family: 'Helvetica Neue', sans-serif; max-width: 600px; margin: 100px auto; padding: 20px; }
            h1 { font-weight: 300; letter-spacing: 4px; }
            a { color: #000; }
        </style>
    </head>
    <body>
        <h1>FRIDA ORCHESTRATOR</h1>
        <p>Backend de processamento de imagens e IA v{APP_VERSION}</p>
        <p><a href="/docs">📖 Documentação Swagger</a></p>
        <p><a href="/health">💚 Health Check</a></p>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Verifica o status da API e seus serviços.
    
    Retorna:
    - status: "healthy" se todos os serviços críticos estão OK
    - status: "degraded" se algum serviço opcional está indisponível
    - status: "unhealthy" se serviços críticos estão indisponíveis
    - ready: True/False indicando se a API pode processar requests
    - services: Status detalhado de cada serviço
    
    NOTA: Com Fail Fast, o status nunca deve ser "unhealthy" pois a API
    não inicia se houver falhas críticas. Este campo é mantido para
    compatibilidade com sistemas de monitoramento.
    """
    services_status = {
        "classifier": "ok" if classifier_service else "unavailable",
        "background_remover": "ok" if background_service else "unavailable",
        "tech_sheet": "ok" if tech_sheet_service else "unavailable",
        "storage": "ok" if storage_service else "not_configured",
        "supabase": "ok" if (settings.SUPABASE_URL and settings.SUPABASE_KEY) else "not_configured"
    }
    
    # Serviços críticos que devem estar OK
    critical_services = ["classifier", "background_remover"]
    all_critical_ok = all(services_status[s] == "ok" for s in critical_services)
    
    # Determina status geral
    if all_critical_ok:
        status = "healthy"
    elif any(services_status[s] == "ok" for s in critical_services):
        status = "degraded"
    else:
        status = "unhealthy"
    
    # Status de configurações
    configuration = {
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "supabase_configured": bool(settings.SUPABASE_URL),
        "auth_enabled": settings.AUTH_ENABLED,
        "jwt_secret_configured": bool(settings.SUPABASE_JWT_SECRET)
    }
    
    # Validação de warnings
    warnings = []
    if settings.AUTH_ENABLED and not settings.SUPABASE_JWT_SECRET:
        warnings.append("AUTH_ENABLED=true mas SUPABASE_JWT_SECRET não configurado")
    
    return HealthResponse(
        status=status,
        version=APP_VERSION,
        gemini_configured=bool(settings.GEMINI_API_KEY),
        services=services_status,
        ready=all_critical_ok,
        configuration=configuration,
        warnings=warnings if warnings else None
    )


@limiter.limit("5/minute")
@app.post("/process", response_model=ProcessResponse)
def processar_produto(
    request: Request,
    file: UploadFile = File(..., description="Imagem do produto para processar"),
    gerar_ficha: bool = Form(False, description="Se True, gera ficha técnica premium"),
    product_id: Optional[str] = Form(None, description="ID do produto para organizar storage"),
    user: AuthUser = Depends(get_current_user)
):
    """
    Endpoint principal de processamento de produtos.
    
    Pipeline:
    1. Recebe a imagem
    2. Classifica o item (bolsa/lancheira/garrafa) e estilo (sketch/foto)
    3. Remove o fundo e aplica branco puro (#FFFFFF)
    4. Opcionalmente gera ficha técnica premium
    5. Registra no Supabase para auditoria (se configurado)
    6. Retorna imagem processada em base64 e dados
    
    **Novo:** Suporta product_id opcional para organizar storage.
    
    NOTA: Esta rota é definida como `def` (síncrona) intencionalmente.
    O FastAPI executa automaticamente funções síncronas em um ThreadPool,
    evitando o bloqueio do Event Loop durante operações CPU-bound como
    rembg e Pillow.
    
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    # Extrair user_id do AuthUser para uso no código existente
    user_id = user.user_id
    
    # Validação rápida do Content-Type (primeira camada)
    if not file.content_type or not validate_image_file(file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie uma imagem (JPEG, PNG, WebP ou GIF)."
        )
    
    try:
        # 1. Lê o conteúdo do arquivo (síncrono via SpooledTemporaryFile)
        content = file.file.read()
        
        # 2. Validação PROFUNDA: magic numbers + integridade Pillow
        is_valid, validation_msg = validate_image_deep(content, file.content_type)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Imagem inválida: {validation_msg}"
            )
        
        # 3. Classifica a imagem
        classificacao = {"item": "desconhecido", "estilo": "desconhecido", "confianca": 0.0}
        
        if classifier_service:
            print(f"[PROCESS] Classificando imagem para user {user_id}: {file.filename}")
            classificacao = classifier_service.classificar(content, file.content_type)
            print(f"[PROCESS] Resultado: {classificacao}")
        else:
            print("[PROCESS] Serviço de classificação não disponível (GEMINI_API_KEY não configurada)")
        
        # ============================================================
        # NOVO: Salvar produto no banco após classificação
        # ============================================================
        db_product_id = None
        try:
            product = create_product(
                name=f"{classificacao['item'].title()} - {file.filename or 'Upload'}",
                category=classificacao['item'],
                classification=classificacao,
                user_id=user_id
            )
            db_product_id = product['id']
            print(f"[DATABASE] ✓ Produto salvo: {db_product_id}")
        except Exception as e:
            print(f"[DATABASE] ❌ Erro ao salvar produto: {str(e)}")
            # Continue processamento mesmo se falhar
        
        # ============================================================
        # 4. Executar Pipeline Completo (v0.5.2)
        # Pipeline: original → segmented → processed + quality validation
        # ============================================================
        pipeline_images = {}
        quality_score = None
        quality_passed = None
        imagem_bytes = None
        
        if db_product_id:
            print("[PIPELINE] Executando pipeline completo...")
            try:
                pipeline_result = image_pipeline_sync.process_image(
                    image_bytes=content,
                    product_id=db_product_id,
                    user_id=user_id,
                    filename=file.filename or "upload.png"
                )
                
                if pipeline_result.success:
                    pipeline_images = pipeline_result.images
                    if pipeline_result.quality_report:
                        quality_score = pipeline_result.quality_report.score
                        quality_passed = pipeline_result.quality_report.passed
                    print(f"[PIPELINE] ✓ Completo! Score: {quality_score}/100")
                else:
                    print(f"[PIPELINE] ⚠️ Falhou: {pipeline_result.error}")
                    # Manter imagens parciais se houver
                    pipeline_images = pipeline_result.images
                    
            except Exception as e:
                print(f"[PIPELINE] ❌ Erro: {str(e)}")
                # Continue sem imagens do pipeline
        
        # 5. Fallback: processar com background_service se pipeline falhou
        if not pipeline_images.get("processed") and background_service:
            print("[PROCESS] Fallback: usando background_service...")
            imagem_final, imagem_bytes = background_service.processar(content)
            print("[PROCESS] ✓ Imagem processada (fallback)")
        elif pipeline_images.get("processed"):
            # Usar URL da imagem processada do pipeline
            imagem_bytes = None  # Imagem já está no storage
        
        # 6. Gera ficha técnica (opcional)
        ficha = None
        if gerar_ficha and tech_sheet_service:
            print("[PROCESS] Gerando ficha técnica...")
            # Se tiver imagem do fallback, usar ela
            if imagem_bytes:
                from PIL import Image
                from io import BytesIO
                imagem_final = Image.open(BytesIO(imagem_bytes))
            else:
                # Carregar imagem original para ficha técnica
                from PIL import Image
                from io import BytesIO
                imagem_final = Image.open(BytesIO(content))
            
            ficha = tech_sheet_service.gerar_ficha_completa(
                imagem_final, 
                classificacao["item"]
            )
            print("[PROCESS] ✓ Ficha técnica gerada")
        
        # 7. Preparar resposta de imagem (separando base64 de URL)
        # API v0.5.3: campos separados para evitar breaking change
        imagem_base64 = None
        imagem_url = None

        if imagem_bytes:
            # Fallback: temos bytes locais, retornar como base64
            imagem_base64 = base64.b64encode(imagem_bytes).decode("utf-8")
        elif pipeline_images.get("processed", {}).get("url"):
            # Pipeline: imagem está no storage, retornar URL
            imagem_url = pipeline_images["processed"]["url"]
        else:
            # Fallback final: retornar original como base64
            imagem_base64 = base64.b64encode(content).decode("utf-8")

        # Log de auditoria final
        print(f"[PROCESS] ✓ Concluído para user {user_id}: {classificacao['item']} ({classificacao['confianca']:.2%})")
        if quality_score is not None:
            status_emoji = "✅" if quality_passed else "❌"
            print(f"[PROCESS] → Quality: {quality_score}/100 {status_emoji}")

        return ProcessResponse(
            status="sucesso",
            product_id=db_product_id,
            categoria=classificacao["item"],
            estilo=classificacao["estilo"],
            confianca=classificacao["confianca"],
            imagem_base64=imagem_base64,
            imagem_url=imagem_url,
            ficha_tecnica=ficha,
            mensagem=f"Imagem processada com sucesso! user_id={user_id}",
            images=pipeline_images if pipeline_images else None,
            quality_score=quality_score,
            quality_passed=quality_passed
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PROCESS] Erro para user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar imagem: {str(e)}"
        )


# =============================================================================
# Async Processing Endpoint (PRD-04)
# =============================================================================

@limiter.limit("10/minute")
@app.post("/process-async", response_model=ProcessAsyncResponse)
def processar_produto_async(
    request: Request,
    file: UploadFile = File(..., description="Imagem do produto para processar"),
    user: AuthUser = Depends(get_current_user)
):
    """
    Endpoint de processamento ASSÍNCRONO de produtos.
    
    Retorna imediatamente (< 2s) após:
    1. Validar o arquivo
    2. Classificar com Gemini
    3. Criar produto no banco
    4. Upload da imagem original para bucket 'raw'
    5. Criar job na fila de processamento
    
    O processamento pesado (segmentação, composição, validação) é feito
    por um worker em background. Use GET /jobs/{job_id} para acompanhar.
    
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    user_id = user.user_id
    
    # ============================================================
    # ETAPA 1: Validação do arquivo (3 camadas)
    # ============================================================
    if not file.content_type or not validate_image_file(file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie uma imagem (JPEG, PNG, WebP ou GIF)."
        )
    
    try:
        content = file.file.read()
        
        # Validação profunda: magic numbers + Pillow integrity
        is_valid, validation_msg = validate_image_deep(content, file.content_type)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Imagem inválida: {validation_msg}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: {str(e)}")
    
    # ============================================================
    # ETAPA 2: Classificação com Gemini (rápido ~1s)
    # ============================================================
    if not classifier_service:
        raise HTTPException(
            status_code=503,
            detail="Serviço de classificação não disponível. Configure GEMINI_API_KEY."
        )
    
    try:
        print(f"[ASYNC] Classificando imagem para user {user_id}: {file.filename}")
        classificacao = classifier_service.classificar(content, file.content_type)
        print(f"[ASYNC] Classificação: {classificacao['item']} ({classificacao['confianca']:.0%})")
        
        # Verificar produto válido
        if classificacao.get("item") == "desconhecido":
            raise HTTPException(
                status_code=400,
                detail="Imagem não reconhecida como produto válido (bolsa, lancheira ou garrafa)"
            )
        
        # Verificar confiança mínima
        if classificacao.get("confianca", 0) < 0.5:
            raise HTTPException(
                status_code=400,
                detail=f"Confiança muito baixa: {classificacao.get('confianca', 0):.0%}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na classificação: {str(e)}")
    
    # ============================================================
    # ETAPA 3: Criar produto no banco
    # ============================================================
    product_name = f"{classificacao['item'].capitalize()} - {file.filename or 'Upload'}"
    
    try:
        product = create_product(
            name=product_name,
            category=classificacao["item"],
            classification=classificacao,
            user_id=user_id
        )
        db_product_id = product["id"]
        print(f"[ASYNC] ✓ Produto criado: {db_product_id}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao criar produto: {str(e)}"
        )
    
    # ============================================================
    # ETAPA 4: Upload imagem original para 'raw'
    # ============================================================
    try:
        original_filename = file.filename or "original"
        extension = original_filename.split(".")[-1] if "." in original_filename else "jpg"
        storage_path = f"{user_id}/{db_product_id}/original.{extension}"
        
        # Upload para Supabase Storage
        client = get_supabase_client()
        
        upload_response = client.storage.from_("raw").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )
        
        # Obter URL pública
        original_url = client.storage.from_("raw").get_public_url(storage_path)
        
        print(f"[ASYNC] ✓ Original uploaded: {storage_path}")
        
    except Exception as e:
        print(f"[ASYNC] ✗ Erro no upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Falha no upload da imagem: {str(e)}"
        )
    
    # ============================================================
    # ETAPA 5: Registrar imagem original no banco
    # ============================================================
    try:
        original_image = create_image(
            product_id=db_product_id,
            type="original",
            bucket="raw",
            path=storage_path,
            user_id=user_id
        )
        original_image_id = original_image["id"]
        print(f"[ASYNC] ✓ Imagem registrada: {original_image_id}")
    except Exception as e:
        print(f"[ASYNC] ⚠ Erro ao registrar imagem: {str(e)}")
        original_image_id = None
    
    # ============================================================
    # ETAPA 6: Criar job na fila
    # ============================================================
    input_data = {
        "original_path": storage_path,
        "original_url": original_url,
        "original_image_id": original_image_id,
        "classification": classificacao,
        "filename": file.filename
    }
    
    job_id = create_job(
        product_id=db_product_id,
        user_id=user_id,
        input_data=input_data
    )
    
    if not job_id:
        raise HTTPException(
            status_code=500,
            detail="Falha ao criar job de processamento"
        )
    
    print(f"[ASYNC] ✓ Job criado: {job_id}")
    print(f"[ASYNC] ✓ Processamento enfileirado para user {user_id}")
    
    # ============================================================
    # RESPOSTA IMEDIATA
    # ============================================================
    return ProcessAsyncResponse(
        status="processing",
        job_id=job_id,
        product_id=db_product_id,
        classification={
            "item": classificacao["item"],
            "estilo": classificacao["estilo"],
            "confianca": classificacao["confianca"]
        },
        message="Processamento iniciado. Use GET /jobs/{job_id} para acompanhar o progresso."
    )


# =============================================================================
# Jobs Status Endpoints (PRD-04)
# =============================================================================

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Retorna status atual de um job de processamento.
    
    Use para polling após POST /process-async.
    Recomendado: poll a cada 2 segundos.
    
    Status possíveis:
    - queued: Aguardando na fila
    - processing: Em processamento (ver current_step e progress)
    - completed: Concluído com sucesso (ver images e quality_score)
    - failed: Falhou (ver last_error e can_retry)
    
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    # Buscar job no banco
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job não encontrado: {job_id}"
        )
    
    # Verificar permissão (user só vê próprios jobs, admin vê todos)
    if user.role != "admin" and job["created_by"] != user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado a este job"
        )
    
    # Montar response base
    response_data = {
        "job_id": job["id"],
        "product_id": job["product_id"],
        "status": job["status"],
        "current_step": job.get("current_step"),
        "progress": job.get("progress", 0),
        "attempts": job.get("attempts", 0),
        "max_attempts": job.get("max_attempts", 3),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "created_at": job.get("created_at"),
        "can_retry": False
    }
    
    # Adicionar campos específicos por status
    if job["status"] == "completed":
        output_data = job.get("output_data", {})
        response_data["images"] = output_data.get("images")
        response_data["quality_score"] = output_data.get("quality_score")
        response_data["quality_passed"] = output_data.get("quality_passed")
    
    elif job["status"] == "failed":
        response_data["last_error"] = job.get("last_error")
        # Pode retry se attempts < max_attempts
        response_data["can_retry"] = job.get("attempts", 0) < job.get("max_attempts", 3)
    
    return JobStatusResponse(**response_data)


@app.get("/jobs", response_model=JobListResponse)
def list_user_jobs_endpoint(
    user: AuthUser = Depends(get_current_user),
    limit: int = 20
):
    """
    Lista jobs do usuário autenticado (mais recentes primeiro).
    
    Args:
        limit: Máximo de jobs (default 20, max 100)
    
    Returns:
        Lista de jobs ordenada por created_at DESC
    
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    # Validar limit
    limit = min(max(1, limit), 100)
    
    # Buscar jobs
    jobs = get_user_jobs(user.user_id, limit=limit)
    
    # Mapear para response
    job_items = [
        JobListItem(
            job_id=job["id"],
            product_id=job["product_id"],
            status=job["status"],
            progress=job.get("progress", 0),
            current_step=job.get("current_step"),
            created_at=job.get("created_at", "")
        )
        for job in jobs
    ]
    
    return JobListResponse(
        jobs=job_items,
        total=len(job_items)
    )


@limiter.limit("10/minute")
@app.post("/classify")
def classificar_apenas(
    request: Request,
    file: UploadFile = File(..., description="Imagem para classificar"),
    user: AuthUser = Depends(get_current_user)
):
    """
    Endpoint para apenas classificar uma imagem (sem processar).
    Útil para testes rápidos da classificação.
    
    NOTA: Rota síncrona para evitar bloqueio do Event Loop.
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    # Extrair user_id do AuthUser
    user_id = user.user_id
    
    if not classifier_service:
        raise HTTPException(
            status_code=503,
            detail="Serviço de classificação não disponível. Configure GEMINI_API_KEY."
        )
    
    if not file.content_type or not validate_image_file(file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie uma imagem."
        )
    
    content = file.file.read()
    
    # Validação profunda
    is_valid, validation_msg = validate_image_deep(content, file.content_type)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Imagem inválida: {validation_msg}"
        )
    
    resultado = classifier_service.classificar(content, file.content_type)
    
    # Log de auditoria
    print(f"[CLASSIFY] Classification by user {user_id}: {resultado['item']} ({resultado['confianca']:.2%})")
    
    return {
        "status": "sucesso",
        "classificacao": resultado,
        "user_id": user_id
    }


# =============================================================================
# Products Endpoints
# =============================================================================

@app.get("/products")
def listar_produtos(user: AuthUser = Depends(get_current_user)):
    """
    Lista todos os produtos do usuário autenticado.
    
    Returns:
        JSON com status, total e lista de produtos
    """
    try:
        products = get_user_products(user.user_id)
        
        return {
            "status": "sucesso",
            "total": len(products),
            "products": products,
            "user_id": user.user_id
        }
        
    except Exception as e:
        print(f"[PRODUCTS] ❌ Erro ao listar produtos: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar produtos"
        )


@app.get("/products/{product_id}")
def obter_produto(
    product_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Obtém detalhes de um produto específico.
    
    Args:
        product_id: UUID do produto
        
    Returns:
        JSON com status e dados do produto
    """
    try:
        client = get_supabase_client()
        result = client.table('products').select('*').eq('id', product_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Produto não encontrado"
            )
        
        product = result.data[0]
        
        # Verificar ownership (RLS já faz isso, mas validação adicional)
        if product['created_by'] != user.user_id and user.role != 'admin':
            raise HTTPException(
                status_code=403,
                detail="Acesso negado a este produto"
            )
        
        return {
            "status": "sucesso",
            "product": product
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PRODUCTS] ❌ Erro ao obter produto: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter produto"
        )


@limiter.limit("5/minute")
@app.post("/remove-background")
def remover_fundo_apenas(
    request: Request,
    file: UploadFile = File(..., description="Imagem para remover fundo"),
    user: AuthUser = Depends(get_current_user)
):
    """
    Endpoint para apenas remover o fundo de uma imagem.
    Retorna a imagem com fundo branco em base64.
    
    NOTA: Rota síncrona para evitar bloqueio do Event Loop.
    Requer autenticação JWT (se AUTH_ENABLED=true).
    """
    # Extrair user_id do AuthUser
    user_id = user.user_id
    
    if not background_service:
        raise HTTPException(
            status_code=503,
            detail="Serviço de remoção de fundo não disponível."
        )
    
    if not file.content_type or not validate_image_file(file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie uma imagem."
        )
    
    content = file.file.read()
    
    # Validação profunda
    is_valid, validation_msg = validate_image_deep(content, file.content_type)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Imagem inválida: {validation_msg}"
        )
    
    _, imagem_bytes = background_service.processar(content)
    imagem_base64 = base64.b64encode(imagem_bytes).decode("utf-8")
    
    # Log de auditoria
    print(f"[REMOVE-BG] Background removed for user {user_id}")
    
    return {
        "status": "sucesso",
        "imagem_base64": imagem_base64,
        "user_id": user_id
    }


# =============================================================================
# Auth Test Endpoints
# =============================================================================

@app.get("/auth/test")
def test_auth(user: AuthUser = Depends(get_current_user)):
    """
    Endpoint para testar autenticação.
    
    Uso:
    curl -H "Authorization: Bearer YOUR_JWT" http://localhost:8000/auth/test
    
    Com AUTH_ENABLED=false: Retorna user_id fake (dev mode)
    Com AUTH_ENABLED=true: Requer token JWT válido + cadastro
    """
    return {
        "status": "authenticated",
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "message": "Token JWT válido! Usuário cadastrado no sistema."
    }


@app.get("/public/ping")
def public_ping():
    """
    Endpoint público (sem auth) para testar conectividade.
    
    Uso:
    curl http://localhost:8000/public/ping
    """
    return {
        "status": "pong",
        "service": "Frida Orchestrator",
        "version": APP_VERSION,
        "auth_required": settings.AUTH_ENABLED
    }


# =============================================================================
# TECHNICAL SHEETS ENDPOINTS (PRD-05)
# =============================================================================

# --- Pydantic Models ---

class SheetDataInput(BaseModel):
    """Dados da ficha técnica."""
    dimensions: Optional[Dict[str, Any]] = None  # altura, largura, profundidade
    materials: Optional[Dict[str, Any]] = None  # couro, forro, metal
    colors: Optional[List[str]] = None
    weight_grams: Optional[int] = None
    supplier: Optional[Dict[str, Any]] = None
    care_instructions: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Permite campos adicionais


class SheetCreateRequest(BaseModel):
    """Request para criar ficha técnica."""
    data: Optional[SheetDataInput] = None


class SheetUpdateRequest(BaseModel):
    """Request para atualizar ficha técnica."""
    data: SheetDataInput
    change_summary: Optional[str] = None


class SheetStatusUpdateRequest(BaseModel):
    """Request para atualizar status."""
    status: str
    rejection_comment: Optional[str] = None


class SheetResponse(BaseModel):
    """Response de ficha técnica."""
    sheet_id: str
    product_id: str
    version: int
    data: Dict[str, Any]
    status: str
    created_by: str
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_comment: Optional[str] = None


class SheetVersionResponse(BaseModel):
    """Response de versão."""
    version: int
    data: Dict[str, Any]
    changed_by: str
    changed_at: str
    change_summary: Optional[str] = None


class SheetVersionsListResponse(BaseModel):
    """Response de lista de versões."""
    sheet_id: str
    current_version: int
    versions: List[SheetVersionResponse]
    total: int


# --- Endpoints ---

@app.post("/products/{product_id}/sheet", response_model=SheetResponse)
def create_or_get_sheet(
    product_id: str,
    request: SheetCreateRequest = None,
    user: AuthUser = Depends(get_current_user)
):
    """
    Cria ficha técnica para produto ou retorna existente.
    
    - Se já existe ficha, retorna a existente
    - Se não existe, cria nova com status 'draft'
    """
    # Verificar se ficha já existe
    existing = get_sheet_by_product(product_id)
    if existing:
        return SheetResponse(
            sheet_id=existing["id"],
            product_id=existing["product_id"],
            version=existing["version"],
            data=existing["data"],
            status=existing["status"],
            created_by=existing["created_by"],
            created_at=str(existing["created_at"]),
            updated_at=str(existing["updated_at"]),
            approved_by=existing.get("approved_by"),
            approved_at=str(existing["approved_at"]) if existing.get("approved_at") else None,
            rejection_comment=existing.get("rejection_comment")
        )
    
    # Preparar dados iniciais
    initial_data = None
    if request and request.data:
        initial_data = request.data.dict(exclude_none=True)
        initial_data["_version"] = 1
        initial_data["_schema"] = "bag_v1"
    
    # Criar nova ficha
    sheet_id = create_technical_sheet(product_id, user.user_id, initial_data)
    if not sheet_id:
        raise HTTPException(status_code=500, detail="Falha ao criar ficha técnica")
    
    # Buscar ficha criada
    sheet = get_technical_sheet(sheet_id)
    if not sheet:
        raise HTTPException(status_code=500, detail="Ficha criada mas não encontrada")
    
    return SheetResponse(
        sheet_id=sheet["id"],
        product_id=sheet["product_id"],
        version=sheet["version"],
        data=sheet["data"],
        status=sheet["status"],
        created_by=sheet["created_by"],
        created_at=str(sheet["created_at"]),
        updated_at=str(sheet["updated_at"]),
        approved_by=sheet.get("approved_by"),
        approved_at=str(sheet["approved_at"]) if sheet.get("approved_at") else None,
        rejection_comment=sheet.get("rejection_comment")
    )


@app.get("/products/{product_id}/sheet", response_model=SheetResponse)
def get_product_sheet(
    product_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Retorna ficha técnica do produto."""
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    return SheetResponse(
        sheet_id=sheet["id"],
        product_id=sheet["product_id"],
        version=sheet["version"],
        data=sheet["data"],
        status=sheet["status"],
        created_by=sheet["created_by"],
        created_at=str(sheet["created_at"]),
        updated_at=str(sheet["updated_at"]),
        approved_by=sheet.get("approved_by"),
        approved_at=str(sheet["approved_at"]) if sheet.get("approved_at") else None,
        rejection_comment=sheet.get("rejection_comment")
    )


@app.put("/products/{product_id}/sheet", response_model=SheetResponse)
def update_product_sheet(
    product_id: str,
    request: SheetUpdateRequest,
    user: AuthUser = Depends(get_current_user)
):
    """Atualiza dados da ficha técnica (incrementa versão automaticamente)."""
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    # Preparar dados para atualização
    new_data = request.data.dict(exclude_none=True)
    
    # Atualizar
    success = update_technical_sheet(
        sheet["id"],
        new_data,
        user.user_id,
        request.change_summary
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao atualizar ficha")
    
    # Buscar atualizada
    updated = get_technical_sheet(sheet["id"])
    if not updated:
        raise HTTPException(status_code=500, detail="Ficha atualizada mas não encontrada")
    
    return SheetResponse(
        sheet_id=updated["id"],
        product_id=updated["product_id"],
        version=updated["version"],
        data=updated["data"],
        status=updated["status"],
        created_by=updated["created_by"],
        created_at=str(updated["created_at"]),
        updated_at=str(updated["updated_at"]),
        approved_by=updated.get("approved_by"),
        approved_at=str(updated["approved_at"]) if updated.get("approved_at") else None,
        rejection_comment=updated.get("rejection_comment")
    )


@app.patch("/products/{product_id}/sheet/status", response_model=SheetResponse)
def update_product_sheet_status(
    product_id: str,
    request: SheetStatusUpdateRequest,
    user: AuthUser = Depends(get_current_user)
):
    """Atualiza status da ficha técnica."""
    valid_statuses = ["draft", "pending", "approved", "rejected", "published"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Válidos: {valid_statuses}"
        )
    
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    success = update_sheet_status(
        sheet["id"],
        request.status,
        user.user_id,
        request.rejection_comment
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao atualizar status")
    
    updated = get_technical_sheet(sheet["id"])
    
    return SheetResponse(
        sheet_id=updated["id"],
        product_id=updated["product_id"],
        version=updated["version"],
        data=updated["data"],
        status=updated["status"],
        created_by=updated["created_by"],
        created_at=str(updated["created_at"]),
        updated_at=str(updated["updated_at"]),
        approved_by=updated.get("approved_by"),
        approved_at=str(updated["approved_at"]) if updated.get("approved_at") else None,
        rejection_comment=updated.get("rejection_comment")
    )


@app.get("/products/{product_id}/sheet/versions", response_model=SheetVersionsListResponse)
def list_sheet_versions(
    product_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """Lista histórico de versões da ficha."""
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    versions_data = get_sheet_versions(sheet["id"])
    
    versions = [
        SheetVersionResponse(
            version=v["version"],
            data=v["data"],
            changed_by=v["changed_by"],
            changed_at=str(v["changed_at"]),
            change_summary=v.get("change_summary")
        )
        for v in versions_data
    ]
    
    return SheetVersionsListResponse(
        sheet_id=sheet["id"],
        current_version=sheet["version"],
        versions=versions,
        total=len(versions)
    )


@app.get("/products/{product_id}/sheet/versions/{version}", response_model=SheetVersionResponse)
def get_sheet_version_endpoint(
    product_id: str,
    version: int,
    user: AuthUser = Depends(get_current_user)
):
    """Retorna versão específica da ficha."""
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    version_data = get_sheet_version(sheet["id"], version)
    if not version_data:
        raise HTTPException(status_code=404, detail=f"Versão {version} não encontrada")
    
    return SheetVersionResponse(
        version=version_data["version"],
        data=version_data["data"],
        changed_by=version_data["changed_by"],
        changed_at=str(version_data["changed_at"]),
        change_summary=version_data.get("change_summary")
    )


@app.delete("/products/{product_id}/sheet")
def delete_product_sheet(
    product_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Deleta ficha técnica.
    
    Só permite deletar se status = 'draft'.
    """
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    if sheet["status"] != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Só é possível deletar fichas com status 'draft'. Status atual: {sheet['status']}"
        )
    
    success = delete_technical_sheet(sheet["id"])
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao deletar ficha")
    
    return {
        "message": "Ficha técnica deletada com sucesso",
        "sheet_id": sheet["id"],
        "product_id": product_id
    }


@app.get("/products/{product_id}/sheet/export/pdf")
def export_sheet_pdf(
    product_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Exporta ficha técnica como PDF.
    
    Gera documento PDF formatado com todas as informações da ficha.
    """
    # Buscar ficha do produto
    sheet = get_sheet_by_product(product_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Ficha técnica não encontrada")
    
    # Buscar dados do produto
    try:
        client = get_supabase_client()
        product_response = client.table("products")\
            .select("*")\
            .eq("id", product_id)\
            .single()\
            .execute()
        
        if not product_response.data:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        product = product_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar produto: {str(e)}")
    
    # Buscar URL da imagem processada (se existir)
    processed_url = None
    try:
        images_response = client.table("images")\
            .select("*")\
            .eq("product_id", product_id)\
            .eq("type", "processed")\
            .execute()
        
        if images_response.data and len(images_response.data) > 0:
            image = images_response.data[0]
            bucket = image.get("storage_bucket", "processed-images")
            path = image.get("storage_path", "")
            if path:
                processed_url = client.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        print(f"[PDF] ⚠ Não foi possível obter imagem: {str(e)}")
        # Continua sem imagem
    
    # Preparar dados para o PDF
    sheet_data = sheet.get("data", {})
    sheet_data["status"] = sheet.get("status", "draft")
    sheet_data["_version"] = sheet.get("version", 1)
    
    # Gerar PDF
    try:
        pdf_buffer = pdf_generator.generate(
            sheet_data=sheet_data,
            product_data=product,
            processed_image_url=processed_url
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {str(e)}")
    
    # Montar nome do arquivo
    category = product.get("category", "produto").replace(" ", "_")
    version = sheet.get("version", 1)
    filename = f"ficha_tecnica_{category}_v{version}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# =============================================================================
# Run with Uvicorn
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
