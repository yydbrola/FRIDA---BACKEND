"""
Serviço de auto-preenchimento de fichas técnicas usando Gemini Vision.
FRIDA Backend - P1

Analisa imagens de produtos e sugere valores para campos vazios
da ficha técnica usando IA.
"""

import json
import base64
import httpx
import google.generativeai as genai
from typing import Any, Optional

from app.config import settings
from app.utils import get_nested_value, set_nested_value, deep_merge
from app.schemas.sheet_schema import VALIDATION_RANGES


# =============================================================================
# CONFIGURATION
# =============================================================================

# Todos os campos do schema v2
ALL_FIELD_PATHS = [
    # Identification
    "identification.style_number",
    "identification.style_name", 
    "identification.season",
    "identification.collection",
    # Dimensions
    "dimensions.width_top_cm",
    "dimensions.width_bottom_cm",
    "dimensions.height_cm",
    "dimensions.depth_cm",
    "dimensions.strap_drop_cm",
    "dimensions.strap_length_cm",
    "dimensions.strap_width_cm",
    # Materials
    "materials.primary.type",
    "materials.primary.color",
    "materials.primary.pantone",
    "materials.primary.supplier",
    "materials.lining.type",
    "materials.lining.color",
    "materials.hardware.type",
    "materials.hardware.finish",
    "materials.hardware.items",
    # Construction
    "construction.stitch_type",
    "construction.stitch_per_inch",
    "construction.edge_finish",
    "construction.reinforcement_areas",
    # Compartments
    "compartments.external_pockets",
    "compartments.internal_pockets",
    "compartments.closure_type",
    "compartments.special_pockets",
    # Additional
    "additional.weight_grams",
    "additional.country_of_origin",
    "additional.care_instructions",
]


AUTOFILL_PROMPT = """Você é um especialista em análise de produtos de moda (bolsas e acessórios).
Analise esta imagem e extraia informações técnicas.

EXTRAIA APENAS os seguintes campos que estão vazios:
{empty_fields}

RETORNE APENAS JSON válido no formato:
{{
  "campo.subcampo": "valor",
  ...
}}

REGRAS:
1. Apenas campos da lista acima
2. Dimensões em centímetros (números inteiros ou decimais)
3. Peso em gramas (número inteiro)
4. Cores em português
5. Se não conseguir determinar com confiança, OMITA o campo
6. Não invente valores - use apenas o que é visível na imagem

RANGES VÁLIDOS:
- dimensions.width_top_cm: 1-100
- dimensions.width_bottom_cm: 1-100
- dimensions.height_cm: 1-80
- dimensions.depth_cm: 1-50
- dimensions.strap_drop_cm: 5-150
- dimensions.strap_length_cm: 10-200
- dimensions.strap_width_cm: 0.5-15
- additional.weight_grams: 50-5000
- construction.stitch_per_inch: 4-20
- compartments.external_pockets: 0-10
- compartments.internal_pockets: 0-10

ENUMS VÁLIDOS:
- identification.season: SS25, FW25, SS26, FW26, Resort, Pre-Fall, Continuado
- materials.hardware.finish: Dourado, Prateado, Rose Gold, Níquel, Fosco, Outro
- compartments.closure_type: Zíper, Magnético, Botão, Fivela, Aberto, Outro
"""


# =============================================================================
# SERVICE CLASS
# =============================================================================

class AutofillService:
    """
    Serviço de auto-preenchimento usando Gemini Vision.
    
    Usage:
        service = AutofillService()
        result = await service.analyze_image(image_url, current_sheet_data)
    """
    
    def __init__(self):
        """Inicializa o serviço com Gemini."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY não configurada")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Usar modelo configurado no projeto
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL_TECH_SHEET)
        
        print(f"[AutofillService] ✓ Inicializado com modelo {settings.GEMINI_MODEL_TECH_SHEET}")
    
    def get_empty_fields(self, sheet_data: dict) -> list[str]:
        """Retorna lista de campos vazios no sheet."""
        empty = []
        for path in ALL_FIELD_PATHS:
            value = get_nested_value(sheet_data, path)
            if value is None or value == '' or value == []:
                empty.append(path)
        return empty
    
    def validate_suggestion(self, field: str, value: Any) -> bool:
        """Valida se sugestão está dentro dos ranges permitidos."""
        if field not in VALIDATION_RANGES:
            return True
        
        if not isinstance(value, (int, float)):
            return True
        
        min_val, max_val = VALIDATION_RANGES[field]
        return min_val <= value <= max_val
    
    async def download_image_as_base64(self, image_url: str) -> tuple[str, str]:
        """Baixa imagem e retorna como base64 com mime type."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', 'image/jpeg')
            # Normalizar content type
            if 'jpeg' in content_type or 'jpg' in content_type:
                content_type = 'image/jpeg'
            elif 'png' in content_type:
                content_type = 'image/png'
            elif 'webp' in content_type:
                content_type = 'image/webp'
            else:
                content_type = 'image/jpeg'  # fallback
            
            image_data = base64.b64encode(response.content).decode('utf-8')
            
            return image_data, content_type
    
    def _parse_ai_response(self, response_text: str) -> dict:
        """Parse da resposta do Gemini, removendo markdown se presente."""
        text = response_text.strip()
        
        # Remover markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove primeira e última linha (```json e ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        
        return json.loads(text)
    
    async def analyze_image(
        self, 
        image_url: str, 
        current_sheet: dict
    ) -> dict:
        """
        Analisa imagem com Gemini e retorna sugestões de preenchimento.
        
        Args:
            image_url: URL pública da imagem do produto
            current_sheet: Dados atuais da ficha técnica
            
        Returns:
            {
                "suggestions": [{"field": str, "value": any, "confidence": float}],
                "analyzed_image": str,
                "empty_fields_count": int,
                "suggestions_count": int,
                "error": str (optional)
            }
        """
        # 1. Identificar campos vazios
        empty_fields = self.get_empty_fields(current_sheet)
        
        if not empty_fields:
            return {
                "suggestions": [],
                "analyzed_image": image_url,
                "empty_fields_count": 0,
                "suggestions_count": 0,
                "message": "Todos os campos já estão preenchidos"
            }
        
        try:
            # 2. Baixar imagem
            print(f"[AutofillService] Baixando imagem: {image_url[:50]}...")
            image_data, mime_type = await self.download_image_as_base64(image_url)
            
            # 3. Construir prompt
            prompt = AUTOFILL_PROMPT.format(
                empty_fields="\n".join(f"- {f}" for f in empty_fields)
            )
            
            # 4. Chamar Gemini
            print(f"[AutofillService] Analisando {len(empty_fields)} campos vazios...")
            response = self.model.generate_content([
                {
                    "mime_type": mime_type,
                    "data": image_data
                },
                prompt
            ])
            
            # 5. Parse da resposta
            parsed = self._parse_ai_response(response.text)
            
        except httpx.HTTPError as e:
            print(f"[AutofillService] ❌ Erro ao baixar imagem: {e}")
            return {
                "suggestions": [],
                "analyzed_image": image_url,
                "empty_fields_count": len(empty_fields),
                "suggestions_count": 0,
                "error": f"Erro ao baixar imagem: {str(e)}"
            }
        except json.JSONDecodeError as e:
            print(f"[AutofillService] ❌ Erro ao parsear resposta: {e}")
            return {
                "suggestions": [],
                "analyzed_image": image_url,
                "empty_fields_count": len(empty_fields),
                "suggestions_count": 0,
                "error": "Falha ao interpretar resposta da IA"
            }
        except Exception as e:
            print(f"[AutofillService] ❌ Erro na análise: {e}")
            return {
                "suggestions": [],
                "analyzed_image": image_url,
                "empty_fields_count": len(empty_fields),
                "suggestions_count": 0,
                "error": str(e)
            }
        
        # 6. Validar e formatar sugestões
        suggestions = []
        for field, value in parsed.items():
            # Verificar se campo é válido
            if field not in ALL_FIELD_PATHS:
                continue
            
            # Verificar se estava na lista de vazios
            if field not in empty_fields:
                continue
            
            # Validar range
            if not self.validate_suggestion(field, value):
                print(f"[AutofillService] ⚠ Valor fora do range: {field}={value}")
                continue
            
            suggestions.append({
                "field": field,
                "value": value,
                "confidence": 0.8  # Confiança padrão
            })
        
        print(f"[AutofillService] ✓ {len(suggestions)} sugestões geradas")
        
        return {
            "suggestions": suggestions,
            "analyzed_image": image_url,
            "empty_fields_count": len(empty_fields),
            "suggestions_count": len(suggestions)
        }


def apply_suggestions_to_sheet(
    sheet_data: dict, 
    suggestions: list[dict],
    selected_fields: list[str]
) -> dict:
    """
    Aplica sugestões selecionadas ao sheet.
    
    Args:
        sheet_data: Dados atuais da ficha
        suggestions: Lista de sugestões do autofill
        selected_fields: Lista de campos que o usuário aceitou
        
    Returns:
        Dados atualizados com as sugestões aplicadas
    """
    updates = {}
    
    for suggestion in suggestions:
        if suggestion["field"] in selected_fields:
            set_nested_value(updates, suggestion["field"], suggestion["value"])
    
    return deep_merge(sheet_data, updates)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Instância global (lazy initialization)
_autofill_service: Optional[AutofillService] = None


def get_autofill_service() -> AutofillService:
    """Retorna instância singleton do AutofillService."""
    global _autofill_service
    if _autofill_service is None:
        _autofill_service = AutofillService()
    return _autofill_service
