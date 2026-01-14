"""
Frida Orchestrator - Configuration Module
Gerenciamento centralizado de variáveis de ambiente e configurações.
"""

import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv


# =============================================================================
# Versão do Aplicativo (Centralizada)
# =============================================================================

APP_VERSION = "0.5.4"
# Enums para categorias e estilos de produtos
# =============================================================================

class ProductCategory(str, Enum):
    """Categorias de produtos suportadas pelo classificador."""
    BOLSA = "bolsa"
    LANCHEIRA = "lancheira"
    GARRAFA_TERMICA = "garrafa_termica"
    DESCONHECIDO = "desconhecido"

    @classmethod
    def values(cls) -> list[str]:
        """Retorna lista de valores válidos."""
        return [e.value for e in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Verifica se um valor é uma categoria válida."""
        return value in cls.values()


class ProductStyle(str, Enum):
    """Estilos de imagem suportados pelo classificador."""
    SKETCH = "sketch"
    FOTO = "foto"
    DESCONHECIDO = "desconhecido"

    @classmethod
    def values(cls) -> list[str]:
        """Retorna lista de valores válidos."""
        return [e.value for e in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Verifica se um valor é um estilo válido."""
        return value in cls.values()


class ProductStatus(str, Enum):
    """Status do workflow de produto."""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"

    @classmethod
    def values(cls) -> list[str]:
        """Retorna lista de valores válidos."""
        return [e.value for e in cls]


class ImageType(str, Enum):
    """Tipos de imagem no pipeline de processamento."""
    ORIGINAL = "original"
    SEGMENTED = "segmented"
    PROCESSED = "processed"

    @classmethod
    def values(cls) -> list[str]:
        """Retorna lista de valores válidos."""
        return [e.value for e in cls]

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
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    
    # Authentication
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Image Processing
    OUTPUT_SIZE: tuple[int, int] = (1080, 1080)
    BACKGROUND_COLOR: str = "#FFFFFF"

    # DoS Protection - Limites de arquivo
    MAX_FILE_SIZE_MB: int = 10  # Tamanho máximo do arquivo em MB
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024  # 10MB em bytes
    MAX_IMAGE_DIMENSION: int = 8000  # Dimensão máxima (largura ou altura) em pixels
    
    @classmethod
    def validate(cls) -> list[str]:
        """Valida se as variáveis obrigatórias estão configuradas."""
        errors = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY não configurada")
        
        return errors


settings = Settings()
