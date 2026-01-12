"""
Frida Orchestrator - FastAPI Main Application
Ponto de entrada da API e definição das rotas de upload e processamento.
"""

import io
import base64
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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

# CORS para permitir requests do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
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
    categoria: str
    estilo: str
    confianca: float
    imagem_base64: str
    ficha_tecnica: Optional[dict] = None
    mensagem: Optional[str] = None


class HealthResponse(BaseModel):
    """Resposta do health check com status detalhado."""
    status: str
    version: str
    gemini_configured: bool
    services: dict  # Status de cada serviço
    ready: bool  # True se todos os serviços críticos estão OK


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
    
    return HealthResponse(
        status=status,
        version="0.5.0",
        gemini_configured=bool(settings.GEMINI_API_KEY),
        services=services_status,
        ready=all_critical_ok
    )


@app.post("/process", response_model=ProcessResponse)
def processar_produto(
    file: UploadFile = File(..., description="Imagem do produto para processar"),
    gerar_ficha: bool = Form(False, description="Se True, gera ficha técnica premium")
):
    """
    Endpoint principal de processamento de produtos.
    
    Pipeline:
    1. Recebe a imagem
    2. Classifica o item (bolsa/lancheira/garrafa) e estilo (sketch/foto)
    3. Remove o fundo e aplica branco puro (#FFFFFF)
    4. Opcionalmente gera ficha técnica premium
    5. Retorna imagem processada em base64 e dados
    
    NOTA: Esta rota é definida como `def` (síncrona) intencionalmente.
    O FastAPI executa automaticamente funções síncronas em um ThreadPool,
    evitando o bloqueio do Event Loop durante operações CPU-bound como
    rembg e Pillow.
    """
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
            print(f"[PROCESS] Classificando imagem: {file.filename}")
            classificacao = classifier_service.classificar(content, file.content_type)
            print(f"[PROCESS] Resultado: {classificacao}")
        else:
            print("[PROCESS] Serviço de classificação não disponível (GEMINI_API_KEY não configurada)")
        
        # 4. Processa a imagem (remove fundo + fundo branco)
        if background_service:
            print("[PROCESS] Processando imagem...")
            imagem_final, imagem_bytes = background_service.processar(content)
            print("[PROCESS] Imagem processada com sucesso")
        else:
            raise HTTPException(
                status_code=500,
                detail="Serviço de processamento de imagem não disponível"
            )
        
        # 5. Gera ficha técnica (opcional)
        ficha = None
        if gerar_ficha and tech_sheet_service:
            print("[PROCESS] Gerando ficha técnica...")
            ficha = tech_sheet_service.gerar_ficha_completa(
                imagem_final, 
                classificacao["item"]
            )
            print("[PROCESS] Ficha técnica gerada")
        
        # 6. Converte imagem para base64
        imagem_base64 = base64.b64encode(imagem_bytes).decode("utf-8")
        
        # 7. Registra no Supabase para auditoria (opcional, não bloqueante)
        storage_url = None
        if storage_service:
            try:
                print("[PROCESS] Registrando no Supabase para auditoria...")
                storage_result = storage_service.processar_e_registrar(
                    image_bytes=imagem_bytes,
                    categoria=classificacao["item"],
                    estilo=classificacao["estilo"],
                    confianca=classificacao["confianca"],
                    ficha_tecnica=ficha,
                    original_filename=file.filename
                )
                if storage_result["success"]:
                    storage_url = storage_result["image_url"]
                    print(f"[PROCESS] ✓ Registrado: {storage_result['record_id']}")
                else:
                    print(f"[PROCESS] ⚠ Falha no registro: {storage_result['error']}")
            except Exception as e:
                print(f"[PROCESS] ⚠ Erro no storage (não bloqueante): {e}")
        
        return ProcessResponse(
            status="sucesso",
            categoria=classificacao["item"],
            estilo=classificacao["estilo"],
            confianca=classificacao["confianca"],
            imagem_base64=imagem_base64,
            ficha_tecnica=ficha,
            mensagem="Imagem processada com sucesso!"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PROCESS] Erro: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar imagem: {str(e)}"
        )


@app.post("/classify")
def classificar_apenas(
    file: UploadFile = File(..., description="Imagem para classificar")
):
    """
    Endpoint para apenas classificar uma imagem (sem processar).
    Útil para testes rápidos da classificação.
    
    NOTA: Rota síncrona para evitar bloqueio do Event Loop.
    """
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
    
    return {
        "status": "sucesso",
        "classificacao": resultado
    }


@app.post("/remove-background")
def remover_fundo_apenas(
    file: UploadFile = File(..., description="Imagem para remover fundo")
):
    """
    Endpoint para apenas remover o fundo de uma imagem.
    Retorna a imagem com fundo branco em base64.
    
    NOTA: Rota síncrona para evitar bloqueio do Event Loop.
    """
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
    
    return {
        "status": "sucesso",
        "imagem_base64": imagem_base64
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
