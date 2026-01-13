"""
Frida Orchestrator - FastAPI Main Application
Ponto de entrada da API e definição das rotas de upload e processamento.
"""

import io
import base64
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.utils import validate_image_file, validate_image_deep, generate_filename
from app.services.classifier import ClassifierService
from app.services.background_remover import BackgroundRemoverService
from app.services.tech_sheet import TechSheetService
from app.services.storage import StorageService
from app.services.image_pipeline import image_pipeline_sync
from app.auth import get_current_user, AuthUser
from app.database import create_product, get_user_products, create_image, get_supabase_client


# =============================================================================
# App Initialization
# =============================================================================

app = FastAPI(
    title="Frida Orchestrator",
    description="Backend de processamento de imagens e IA para produtos de moda",
    version="0.5.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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


@app.on_event("startup")
async def startup_event():
    """
    Inicializa os serviços no startup com abordagem FAIL FAST.
    
    Comportamento:
    - Se GEMINI_API_KEY não estiver configurada: FALHA CRÍTICA
    - Se BackgroundRemoverService falhar: FALHA CRÍTICA
    - Se ClassifierService falhar: FALHA CRÍTICA
    
    A API NÃO inicia em estado inconsistente. Isso garante que problemas
    de configuração sejam detectados imediatamente no deploy.
    """
    global classifier_service, background_service, tech_sheet_service, storage_service
    
    print("[STARTUP] Iniciando Frida Orchestrator v0.5.0...")
    
    # ==========================================================================
    # 1. Validação de Configurações OBRIGATÓRIAS (Fail Fast)
    # ==========================================================================
    
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
    
    # ==========================================================================
    # 2. Inicialização de Serviços CRÍTICOS (Fail Fast)
    # ==========================================================================
    
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
    
    # ==========================================================================
    # 3. Validações Opcionais (Avisos, não bloqueantes)
    # ==========================================================================
    
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
        <p>Backend de processamento de imagens e IA v0.5.0</p>
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
        version="0.5.0",
        gemini_configured=bool(settings.GEMINI_API_KEY),
        services=services_status,
        ready=all_critical_ok,
        configuration=configuration,
        warnings=warnings if warnings else None
    )


@app.post("/process", response_model=ProcessResponse)
def processar_produto(
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


@app.post("/classify")
def classificar_apenas(
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


@app.post("/remove-background")
def remover_fundo_apenas(
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
        "version": "0.5.0",
        "auth_required": settings.AUTH_ENABLED
    }


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
