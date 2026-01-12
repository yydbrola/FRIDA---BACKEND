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
from app.utils import validate_image_file, generate_filename
from app.services.classifier import ClassifierService
from app.services.background_remover import BackgroundRemoverService
from app.services.tech_sheet import TechSheetService


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
    """Resposta do health check."""
    status: str
    version: str
    gemini_configured: bool


# =============================================================================
# Service Instances
# =============================================================================

classifier_service: Optional[ClassifierService] = None
background_service: Optional[BackgroundRemoverService] = None
tech_sheet_service: Optional[TechSheetService] = None


@app.on_event("startup")
async def startup_event():
    """Inicializa os serviços no startup."""
    global classifier_service, background_service, tech_sheet_service
    
    # Valida configurações
    errors = settings.validate()
    if errors:
        print(f"[STARTUP] Avisos de configuração: {errors}")
    
    try:
        if settings.GEMINI_API_KEY:
            classifier_service = ClassifierService()
            tech_sheet_service = TechSheetService()
        
        background_service = BackgroundRemoverService()
        print("[STARTUP] Serviços inicializados com sucesso")
    except Exception as e:
        print(f"[STARTUP] Erro ao inicializar serviços: {e}")


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
    """Verifica o status da API."""
    return HealthResponse(
        status="healthy",
        version="0.5.0",
        gemini_configured=bool(settings.GEMINI_API_KEY)
    )


@app.post("/process", response_model=ProcessResponse)
async def processar_produto(
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
    """
    # Valida o arquivo
    if not file.content_type or not validate_image_file(file.content_type):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie uma imagem (JPEG, PNG, WebP ou GIF)."
        )
    
    try:
        # 1. Lê o conteúdo do arquivo
        content = await file.read()
        
        # 2. Classifica a imagem
        classificacao = {"item": "desconhecido", "estilo": "desconhecido", "confianca": 0.0}
        
        if classifier_service:
            print(f"[PROCESS] Classificando imagem: {file.filename}")
            classificacao = classifier_service.classificar(content, file.content_type)
            print(f"[PROCESS] Resultado: {classificacao}")
        else:
            print("[PROCESS] Serviço de classificação não disponível (GEMINI_API_KEY não configurada)")
        
        # 3. Processa a imagem (remove fundo + fundo branco)
        if background_service:
            print("[PROCESS] Processando imagem...")
            imagem_final, imagem_bytes = background_service.processar(content)
            print("[PROCESS] Imagem processada com sucesso")
        else:
            raise HTTPException(
                status_code=500,
                detail="Serviço de processamento de imagem não disponível"
            )
        
        # 4. Gera ficha técnica (opcional)
        ficha = None
        if gerar_ficha and tech_sheet_service:
            print("[PROCESS] Gerando ficha técnica...")
            ficha = tech_sheet_service.gerar_ficha_completa(
                imagem_final, 
                classificacao["item"]
            )
            print("[PROCESS] Ficha técnica gerada")
        
        # 5. Converte imagem para base64
        imagem_base64 = base64.b64encode(imagem_bytes).decode("utf-8")
        
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
async def classificar_apenas(
    file: UploadFile = File(..., description="Imagem para classificar")
):
    """
    Endpoint para apenas classificar uma imagem (sem processar).
    Útil para testes rápidos da classificação.
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
    
    content = await file.read()
    resultado = classifier_service.classificar(content, file.content_type)
    
    return {
        "status": "sucesso",
        "classificacao": resultado
    }


@app.post("/remove-background")
async def remover_fundo_apenas(
    file: UploadFile = File(..., description="Imagem para remover fundo")
):
    """
    Endpoint para apenas remover o fundo de uma imagem.
    Retorna a imagem com fundo branco em base64.
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
    
    content = await file.read()
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
