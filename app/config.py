"""
Frida Orchestrator - Configuration Module
Gerenciamento centralizado de variáveis de ambiente e configurações.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings:
    """Configurações globais do orquestrador."""
    
    # Google Gemini - Modelos por tarefa
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_CLASSIFIER: str = "gemini-2.0-flash-lite"    # Classificação (rápido/barato)
    GEMINI_MODEL_TECH_SHEET: str = "gemini-2.0-flash-lite"    # Ficha técnica
    GEMINI_MODEL_IMAGE_GEN: str = "gemini-2.0-flash-exp"      # Geração de imagem (experimental)
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "processed-images")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Image Processing
    OUTPUT_SIZE: tuple[int, int] = (1080, 1080)
    BACKGROUND_COLOR: str = "#FFFFFF"
    
    @classmethod
    def validate(cls) -> list[str]:
        """Valida se as variáveis obrigatórias estão configuradas."""
        errors = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY não configurada")
        
        return errors


settings = Settings()
