"""
Schema v2 para fichas técnicas de bolsas.
FRIDA v0.5.2 - P0 Backend

Este módulo implementa o schema expandido de 30 campos em 7 categorias,
com suporte a migração automática de fichas v1 existentes.

Retrocompatibilidade:
- is_v1_schema(): Detecta fichas no formato antigo
- migrate_v1_to_v2(): Converte v1 → v2 preservando dados
- validate_ranges(): Valida limites numéricos

Uso:
    from app.schemas.sheet_schema import SheetDataV2, is_v1_schema, migrate_v1_to_v2
    
    if is_v1_schema(data):
        data = migrate_v1_to_v2(data)
    
    sheet = SheetDataV2(**data)
"""

from typing import Optional, List, Literal, Tuple
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS (Literal types for Pydantic v2 compatibility)
# =============================================================================

Season = Literal['SS25', 'FW25', 'SS26', 'FW26', 'Resort', 'Pre-Fall', 'Continuado']
HardwareFinish = Literal['Dourado', 'Prateado', 'Rose Gold', 'Níquel', 'Fosco', 'Outro']
ClosureType = Literal['Zíper', 'Magnético', 'Botão', 'Fivela', 'Aberto', 'Outro']


# =============================================================================
# SUB-SCHEMAS
# =============================================================================

class IdentificationSchema(BaseModel):
    """Dados de identificação do produto."""
    style_number: Optional[str] = Field(None, max_length=50, description="SKU/Código")
    style_name: Optional[str] = Field(None, max_length=100, description="Nome do modelo")
    season: Optional[Season] = Field(None, description="Temporada")
    collection: Optional[str] = Field(None, max_length=100, description="Coleção")
    
    class Config:
        extra = "allow"  # Permite campos adicionais para flexibilidade


class DimensionsSchema(BaseModel):
    """Dimensões físicas do produto em centímetros."""
    width_top_cm: Optional[float] = Field(None, ge=1, le=100, description="Largura superior")
    width_bottom_cm: Optional[float] = Field(None, ge=1, le=100, description="Largura inferior")
    height_cm: Optional[float] = Field(None, ge=1, le=80, description="Altura")
    depth_cm: Optional[float] = Field(None, ge=1, le=50, description="Profundidade")
    strap_drop_cm: Optional[float] = Field(None, ge=5, le=150, description="Queda da alça")
    strap_length_cm: Optional[float] = Field(None, ge=10, le=200, description="Comprimento da alça")
    strap_width_cm: Optional[float] = Field(None, ge=0.5, le=15, description="Largura da alça")
    
    class Config:
        extra = "allow"


class PrimaryMaterialSchema(BaseModel):
    """Material principal."""
    type: Optional[str] = Field(None, max_length=100, description="Tipo de material")
    color: Optional[str] = Field(None, max_length=50, description="Cor")
    pantone: Optional[str] = Field(None, max_length=20, description="Código Pantone")
    supplier: Optional[str] = Field(None, max_length=100, description="Fornecedor")
    
    class Config:
        extra = "allow"


class LiningSchema(BaseModel):
    """Forro."""
    type: Optional[str] = Field(None, max_length=100, description="Tipo de forro")
    color: Optional[str] = Field(None, max_length=50, description="Cor do forro")
    
    class Config:
        extra = "allow"


class HardwareSchema(BaseModel):
    """Metais e ferragens."""
    type: Optional[str] = Field(None, max_length=100, description="Tipo de metal")
    finish: Optional[HardwareFinish] = Field(None, description="Acabamento")
    items: List[str] = Field(default_factory=list, description="Lista de itens")
    
    class Config:
        extra = "allow"


class MaterialsSchema(BaseModel):
    """Materiais do produto."""
    primary: Optional[PrimaryMaterialSchema] = Field(None, description="Material principal")
    lining: Optional[LiningSchema] = Field(None, description="Forro")
    hardware: Optional[HardwareSchema] = Field(None, description="Metais")
    
    class Config:
        extra = "allow"


class ConstructionSchema(BaseModel):
    """Detalhes de construção."""
    stitch_type: Optional[str] = Field(None, max_length=100, description="Tipo de costura")
    stitch_per_inch: Optional[int] = Field(None, ge=4, le=20, description="Pontos por polegada")
    edge_finish: Optional[str] = Field(None, max_length=100, description="Acabamento de borda")
    reinforcement_areas: List[str] = Field(default_factory=list, description="Áreas de reforço")
    
    class Config:
        extra = "allow"


class CompartmentsSchema(BaseModel):
    """Compartimentos e bolsos."""
    external_pockets: Optional[int] = Field(None, ge=0, le=10, description="Bolsos externos")
    internal_pockets: Optional[int] = Field(None, ge=0, le=10, description="Bolsos internos")
    closure_type: Optional[ClosureType] = Field(None, description="Tipo de fechamento")
    special_pockets: List[str] = Field(default_factory=list, description="Bolsos especiais")
    
    class Config:
        extra = "allow"


class AdditionalInfoSchema(BaseModel):
    """Informações adicionais."""
    weight_grams: Optional[int] = Field(None, ge=50, le=5000, description="Peso em gramas")
    country_of_origin: Optional[str] = Field(None, max_length=50, description="País de origem")
    care_instructions: Optional[str] = Field(None, max_length=500, description="Instruções de cuidado")
    
    class Config:
        extra = "allow"


# =============================================================================
# MAIN SCHEMA
# =============================================================================

class SheetDataV2(BaseModel):
    """
    Schema principal v2 - 30 campos em 7 categorias.
    
    Estrutura JSONB para armazenamento em Supabase.
    Todos os campos são opcionais para suportar preenchimento parcial.
    """
    identification: Optional[IdentificationSchema] = None
    dimensions: Optional[DimensionsSchema] = None
    materials: Optional[MaterialsSchema] = None
    construction: Optional[ConstructionSchema] = None
    compartments: Optional[CompartmentsSchema] = None
    additional: Optional[AdditionalInfoSchema] = None
    
    class Config:
        extra = "allow"  # Permite _version e _schema


# =============================================================================
# FUNÇÕES DE MIGRAÇÃO
# =============================================================================

def is_v1_schema(data: dict) -> bool:
    """
    Detecta se dados são schema v1.
    
    Critérios:
    - Dados vazios ou None → considera v1
    - _schema == "bag_v1" → v1
    - _schema não definido → v1 (legacy)
    - _schema == "bag_v2" → NÃO é v1
    
    Args:
        data: Dados JSONB da ficha técnica
        
    Returns:
        True se é v1 ou legacy, False se é v2
    """
    if not data:
        return True
    
    schema = data.get("_schema", "")
    
    # Explicitamente v2
    if schema == "bag_v2":
        return False
    
    # v1 explícito ou sem schema (legacy)
    return schema == "bag_v1" or not schema


def migrate_v1_to_v2(v1_data: dict) -> dict:
    """
    Converte schema v1 para v2 preservando dados existentes.
    
    Mapeamento v1 → v2:
    - name → identification.style_name
    - sku → identification.style_number
    - dimensions.height_cm → dimensions.height_cm
    - dimensions.width_cm → dimensions.width_top_cm
    - dimensions.depth_cm → dimensions.depth_cm
    - materials.primary → materials.primary.type
    - materials.secondary → materials.lining.type
    - materials.hardware → materials.hardware.type
    - colors[0] → materials.primary.color
    - weight_grams → additional.weight_grams
    - care_instructions → additional.care_instructions
    - supplier.name → additional.country_of_origin
    
    Args:
        v1_data: Dados no formato v1
        
    Returns:
        Dados convertidos para v2 (limpos de objetos vazios)
    """
    if not v1_data:
        return {"_version": 2, "_schema": "bag_v2"}
    
    # Extrair dados v1
    dimensions_v1 = v1_data.get("dimensions", {}) or {}
    materials_v1 = v1_data.get("materials", {}) or {}
    colors_v1 = v1_data.get("colors", []) or []
    supplier_v1 = v1_data.get("supplier", {}) or {}
    
    # Construir v2
    v2_data = {
        "_version": 2,
        "_schema": "bag_v2",
        "identification": {
            "style_name": v1_data.get("name"),
            "style_number": v1_data.get("sku"),
        },
        "dimensions": {
            "height_cm": dimensions_v1.get("height_cm"),
            "width_top_cm": dimensions_v1.get("width_cm"),
            "depth_cm": dimensions_v1.get("depth_cm"),
        },
        "materials": {
            "primary": {
                "type": materials_v1.get("primary"),
                "color": colors_v1[0] if colors_v1 else None,
            },
            "lining": {
                "type": materials_v1.get("secondary"),
            },
            "hardware": {
                "type": materials_v1.get("hardware"),
            },
        },
        "additional": {
            "weight_grams": v1_data.get("weight_grams"),
            "care_instructions": v1_data.get("care_instructions"),
            "country_of_origin": supplier_v1.get("name") if isinstance(supplier_v1, dict) else None,
        },
    }
    
    # Limpar objetos vazios para não poluir o JSONB
    return _clean_empty_nested(v2_data)


def _clean_empty_nested(data: dict) -> dict:
    """
    Remove objetos aninhados que estão vazios ou contêm apenas None.
    
    Preserva valores primitivos (incluindo 0, "", False).
    Remove apenas dicts que ficaram vazios após limpeza recursiva.
    
    Args:
        data: Dicionário a limpar
        
    Returns:
        Dicionário limpo
    """
    result = {}
    
    for key, value in data.items():
        if isinstance(value, dict):
            cleaned = _clean_empty_nested(value)
            # Só inclui se não ficou vazio
            if cleaned:
                result[key] = cleaned
        elif value is not None:
            # Preserva valores não-None (incluindo 0, "", False, [])
            result[key] = value
    
    return result


# =============================================================================
# VALIDAÇÃO DE RANGES
# =============================================================================

VALIDATION_RANGES = {
    "dimensions.width_top_cm": (1, 100),
    "dimensions.width_bottom_cm": (1, 100),
    "dimensions.height_cm": (1, 80),
    "dimensions.depth_cm": (1, 50),
    "dimensions.strap_drop_cm": (5, 150),
    "dimensions.strap_length_cm": (10, 200),
    "dimensions.strap_width_cm": (0.5, 15),
    "additional.weight_grams": (50, 5000),
    "construction.stitch_per_inch": (4, 20),
    "compartments.external_pockets": (0, 10),
    "compartments.internal_pockets": (0, 10),
}


def validate_ranges(data: dict) -> Tuple[bool, List[str]]:
    """
    Valida ranges numéricos dos campos.
    
    Verifica apenas campos que estão presentes e não são None.
    Campos ausentes não geram erro (preenchimento parcial permitido).
    
    Args:
        data: Dados da ficha técnica (estrutura v2)
        
    Returns:
        Tuple (is_valid, errors)
        - is_valid: True se todos os valores estão nos ranges
        - errors: Lista de mensagens de erro (vazia se válido)
        
    Example:
        >>> data = {"dimensions": {"width_top_cm": 500}}
        >>> is_valid, errors = validate_ranges(data)
        >>> print(is_valid, errors)
        False ['dimensions.width_top_cm: 500 fora do range [1, 100]']
    """
    errors = []
    
    def get_nested(obj: dict, path: str):
        """Obtém valor de caminho aninhado."""
        keys = path.split(".")
        current = obj
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    for field_path, (min_val, max_val) in VALIDATION_RANGES.items():
        value = get_nested(data, field_path)
        
        # Ignora campos não preenchidos
        if value is None:
            continue
        
        # Valida tipo numérico
        if not isinstance(value, (int, float)):
            errors.append(f"{field_path}: deve ser numérico, recebeu {type(value).__name__}")
            continue
        
        # Valida range
        if value < min_val or value > max_val:
            errors.append(f"{field_path}: {value} fora do range [{min_val}, {max_val}]")
    
    return len(errors) == 0, errors
