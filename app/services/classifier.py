"""
Frida Orchestrator - Classifier Service
Identificação automática de itens usando Gemini Vision.
"""

import google.generativeai as genai
from typing import TypedDict, Literal

from app.config import settings
from app.utils import safe_json_parse


class ClassificationResult(TypedDict):
    """Resultado da classificação de imagem."""
    item: Literal["bolsa", "lancheira", "garrafa_termica", "desconhecido"]
    estilo: Literal["sketch", "foto", "desconhecido"]
    confianca: float


class ClassifierService:
    """
    Serviço de classificação de imagens usando Gemini Vision.
    Identifica o tipo de item e se é sketch ou foto real.
    """
    
    PROMPT = """
Analise esta imagem de produto de moda e determine:

1. **Categoria do item**: Identifique se é uma bolsa, lancheira ou garrafa térmica.
2. **Estilo da imagem**: Determine se é um rascunho/sketch desenhado à mão ou uma foto de produto real.
3. **Confiança**: Indique sua confiança na classificação de 0.0 a 1.0.

Responda APENAS com um JSON válido no seguinte formato:
{
    "item": "bolsa" | "lancheira" | "garrafa_termica" | "desconhecido",
    "estilo": "sketch" | "foto" | "desconhecido",
    "confianca": 0.95
}

IMPORTANTE: Não inclua texto adicional, apenas o JSON.
"""
    
    def __init__(self):
        """Inicializa o serviço com a API do Gemini."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY não configurada")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL_CLASSIFIER)
    
    def classificar(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ClassificationResult:
        """
        Classifica uma imagem usando Gemini Vision.
        
        Args:
            image_bytes: Bytes da imagem a ser classificada
            mime_type: Tipo MIME da imagem
            
        Returns:
            ClassificationResult com item, estilo e confiança
        """
        try:
            # Prepara o conteúdo para o Gemini
            image_part = {
                "mime_type": mime_type,
                "data": image_bytes
            }
            
            # Gera a resposta
            response = self.model.generate_content([self.PROMPT, image_part])
            
            # Parse do JSON
            result = safe_json_parse(response.text)
            
            if result is None:
                return self._default_result()
            
            # Valida e normaliza o resultado
            return self._normalize_result(result)
            
        except Exception as e:
            print(f"[ClassifierService] Erro na classificação: {e}")
            return self._default_result()
    
    def _normalize_result(self, result: dict) -> ClassificationResult:
        """Normaliza o resultado para garantir campos válidos."""
        valid_items = ["bolsa", "lancheira", "garrafa_termica", "desconhecido"]
        valid_estilos = ["sketch", "foto", "desconhecido"]
        
        item = result.get("item", "desconhecido")
        estilo = result.get("estilo", "desconhecido")
        confianca = result.get("confianca", 0.0)
        
        return ClassificationResult(
            item=item if item in valid_items else "desconhecido",
            estilo=estilo if estilo in valid_estilos else "desconhecido",
            confianca=float(confianca) if isinstance(confianca, (int, float)) else 0.0
        )
    
    def _default_result(self) -> ClassificationResult:
        """Retorna resultado padrão em caso de erro."""
        return ClassificationResult(
            item="desconhecido",
            estilo="desconhecido",
            confianca=0.0
        )
