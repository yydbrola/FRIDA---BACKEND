"""
Frida Orchestrator - Classifier Service
Identificação automática de itens usando Gemini Vision com Structured Output.

IMPORTANTE: Esta implementação usa o recurso nativo de Structured Output do Gemini,
garantindo que a resposta seja sempre um JSON válido conforme o schema definido.
Não há dependência de parsers Regex ou heurísticas de extração.
"""

import json
import google.generativeai as genai
from typing import TypedDict, Literal

from app.config import settings


# =============================================================================
# Type Definitions (Contrato de Dados)
# =============================================================================

class ClassificationResult(TypedDict):
    """
    Resultado da classificação de imagem.
    
    CONTRATO DE DADOS:
    Este é o formato exato retornado por classificar() e esperado por main.py.
    Qualquer alteração aqui DEVE ser refletida no consumidor.
    
    Campos:
        item: Categoria do produto ("bolsa", "lancheira", "garrafa_termica", "desconhecido")
        estilo: Tipo de imagem ("sketch", "foto", "desconhecido")
        confianca: Nível de confiança da classificação (0.0 a 1.0)
    """
    item: Literal["bolsa", "lancheira", "garrafa_termica", "desconhecido"]
    estilo: Literal["sketch", "foto", "desconhecido"]
    confianca: float


# Schema para Gemini Structured Output
# O Gemini usa este schema para garantir que a resposta seja JSON válido
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "item": {
            "type": "string",
            "enum": ["bolsa", "lancheira", "garrafa_termica", "desconhecido"],
            "description": "Categoria do produto: bolsa, lancheira, garrafa_termica ou desconhecido"
        },
        "estilo": {
            "type": "string",
            "enum": ["sketch", "foto", "desconhecido"],
            "description": "Tipo da imagem: sketch (desenho) ou foto (produto real)"
        },
        "confianca": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Nível de confiança da classificação entre 0.0 e 1.0"
        }
    },
    "required": ["item", "estilo", "confianca"]
}


class ClassifierService:
    """
    Serviço de classificação de imagens usando Gemini Vision.
    
    Utiliza Structured Output nativo do Gemini (response_mime_type + response_schema)
    para garantir respostas JSON válidas e tipadas, sem necessidade de parsing Regex.
    """
    
    # Prompt simplificado - não precisa mais pedir formato JSON explicitamente
    # pois o Structured Output garante o formato
    PROMPT = """Analise esta imagem de produto de moda e classifique:

1. **item**: Identifique a categoria do produto.
   - "bolsa" para bolsas, mochilas, clutches, carteiras
   - "lancheira" para lancheiras, merendeiras, cooler bags
   - "garrafa_termica" para garrafas térmicas, squeezes, copos térmicos
   - "desconhecido" se não conseguir identificar

2. **estilo**: Determine o tipo de imagem.
   - "sketch" para rascunhos, desenhos à mão, ilustrações, croquis
   - "foto" para fotografias de produtos reais, renders 3D realistas
   - "desconhecido" se não conseguir determinar

3. **confianca**: Sua confiança na classificação (0.0 a 1.0).
   - 0.9+ para classificações muito confiantes
   - 0.7-0.9 para razoavelmente confiantes
   - abaixo de 0.7 para incertezas"""
    
    def __init__(self):
        """Inicializa o serviço com Gemini Structured Output."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY não configurada")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Configura o modelo com Structured Output
        self.generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=CLASSIFICATION_SCHEMA,
            temperature=0.1,  # Baixa temperatura para respostas mais consistentes
        )
        
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL_CLASSIFIER,
            generation_config=self.generation_config
        )
    
    def classificar(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> ClassificationResult:
        """
        Classifica uma imagem usando Gemini Vision com Structured Output.
        
        Args:
            image_bytes: Bytes da imagem a ser classificada
            mime_type: Tipo MIME da imagem
            
        Returns:
            ClassificationResult com item, estilo e confiança
            
        NOTA: O formato de retorno é IDÊNTICO à versão anterior.
        Nenhuma alteração no contrato de dados com main.py.
        """
        try:
            # Prepara o conteúdo para o Gemini
            image_part = {
                "mime_type": mime_type,
                "data": image_bytes
            }
            
            # Gera a resposta com Structured Output
            # O Gemini retorna diretamente JSON válido
            response = self.model.generate_content([self.PROMPT, image_part])
            
            # Parse direto do JSON (garantido pelo Structured Output)
            result = json.loads(response.text)
            
            # Valida e normaliza (safety check)
            return self._normalize_result(result)
            
        except json.JSONDecodeError as e:
            # Não deveria acontecer com Structured Output, mas safety first
            print(f"[ClassifierService] Erro de JSON (inesperado com Structured Output): {e}")
            return self._default_result()
        except Exception as e:
            print(f"[ClassifierService] Erro na classificação: {e}")
            return self._default_result()
    
    def _normalize_result(self, result: dict) -> ClassificationResult:
        """
        Normaliza o resultado para garantir campos válidos.
        
        Safety check adicional, mesmo com Structured Output garantindo o schema.
        """
        valid_items = frozenset(["bolsa", "lancheira", "garrafa_termica", "desconhecido"])
        valid_estilos = frozenset(["sketch", "foto", "desconhecido"])
        
        item = result.get("item", "desconhecido")
        estilo = result.get("estilo", "desconhecido")
        confianca = result.get("confianca", 0.0)
        
        # Clamp confiança entre 0.0 e 1.0
        try:
            confianca_float = float(confianca)
            confianca_float = max(0.0, min(1.0, confianca_float))
        except (TypeError, ValueError):
            confianca_float = 0.0
        
        return ClassificationResult(
            item=item if item in valid_items else "desconhecido",
            estilo=estilo if estilo in valid_estilos else "desconhecido",
            confianca=confianca_float
        )
    
    def _default_result(self) -> ClassificationResult:
        """Retorna resultado padrão em caso de erro."""
        return ClassificationResult(
            item="desconhecido",
            estilo="desconhecido",
            confianca=0.0
        )
