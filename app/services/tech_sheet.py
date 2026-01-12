"""
Frida Orchestrator - Tech Sheet Service
Geração de fichas técnicas premium usando Gemini e Jinja2.
"""

import io
import base64
from pathlib import Path
from PIL import Image
from jinja2 import Environment, FileSystemLoader
import google.generativeai as genai
from typing import TypedDict, Optional

from app.config import settings
from app.utils import safe_json_parse, image_to_bytes


class TechSheetData(TypedDict):
    """Dados extraídos para a ficha técnica."""
    nome: str
    categoria: str
    descricao: str
    materiais: list[str]
    cores: list[str]
    dimensoes: dict
    detalhes: list[str]


class TechSheetService:
    """
    Serviço de geração de fichas técnicas premium.
    Usa Gemini para extrair dados e Jinja2 para renderizar HTML.
    """
    
    PROMPT_TEMPLATE = """
Analise esta imagem de {categoria} e extraia informações técnicas detalhadas para um catálogo de luxo.

Responda APENAS com um JSON válido no seguinte formato:
{{
    "nome": "Nome sugerido para o produto",
    "categoria": "{categoria}",
    "descricao": "Descrição elegante e detalhada do produto em 2-3 frases",
    "materiais": ["material1", "material2"],
    "cores": ["cor1", "cor2"],
    "dimensoes": {{
        "altura": "XX cm",
        "largura": "XX cm",
        "profundidade": "XX cm"
    }},
    "detalhes": ["detalhe de design 1", "detalhe de design 2", "acabamento especial"]
}}

Seja criativo mas realista. Use terminologia de moda de luxo.
IMPORTANTE: Responda APENAS com o JSON, sem texto adicional.
"""
    
    def __init__(self):
        """Inicializa o serviço."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY não configurada")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL_TECH_SHEET)
        
        # Configura Jinja2
        templates_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True
        )
    
    def extrair_dados(
        self, 
        image_bytes: bytes, 
        categoria: str,
        mime_type: str = "image/png"
    ) -> TechSheetData:
        """
        Extrai dados técnicos de uma imagem usando Gemini.
        
        Args:
            image_bytes: Bytes da imagem
            categoria: Categoria do produto (bolsa, lancheira, etc)
            mime_type: Tipo MIME da imagem
            
        Returns:
            TechSheetData com informações extraídas
        """
        try:
            prompt = self.PROMPT_TEMPLATE.format(categoria=categoria)
            
            image_part = {
                "mime_type": mime_type,
                "data": image_bytes
            }
            
            response = self.model.generate_content([prompt, image_part])
            result = safe_json_parse(response.text)
            
            if result is None:
                return self._default_data(categoria)
            
            return self._normalize_data(result, categoria)
            
        except Exception as e:
            print(f"[TechSheetService] Erro ao extrair dados: {e}")
            return self._default_data(categoria)
    
    def renderizar_html(
        self, 
        dados: TechSheetData, 
        image_base64: Optional[str] = None
    ) -> str:
        """
        Renderiza a ficha técnica em HTML usando template Jinja2.
        
        Args:
            dados: Dados da ficha técnica
            image_base64: Imagem em base64 para incluir no HTML
            
        Returns:
            HTML renderizado
        """
        try:
            template = self.jinja_env.get_template("tech_sheet_premium.html")
            return template.render(
                dados=dados,
                image_base64=image_base64
            )
        except Exception as e:
            print(f"[TechSheetService] Erro ao renderizar HTML: {e}")
            return self._fallback_html(dados)
    
    def gerar_ficha_completa(
        self,
        image: Image.Image,
        categoria: str
    ) -> dict:
        """
        Gera a ficha técnica completa: extrai dados e renderiza HTML.
        
        Args:
            image: Imagem PIL do produto
            categoria: Categoria do produto
            
        Returns:
            Dict com dados e HTML da ficha
        """
        # Converte imagem para bytes
        image_bytes = image_to_bytes(image, format="PNG")
        
        # Converte para base64 para embedding no HTML
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Extrai dados usando Gemini
        dados = self.extrair_dados(image_bytes, categoria)
        
        # Renderiza HTML
        html = self.renderizar_html(dados, image_base64)
        
        return {
            "dados": dados,
            "html": html
        }
    
    def _normalize_data(self, result: dict, categoria: str) -> TechSheetData:
        """Normaliza os dados extraídos."""
        return TechSheetData(
            nome=result.get("nome", f"{categoria.title()} Premium"),
            categoria=categoria,
            descricao=result.get("descricao", "Produto de design exclusivo."),
            materiais=result.get("materiais", ["Couro sintético premium"]),
            cores=result.get("cores", ["Preto"]),
            dimensoes=result.get("dimensoes", {
                "altura": "N/A",
                "largura": "N/A",
                "profundidade": "N/A"
            }),
            detalhes=result.get("detalhes", ["Design moderno"])
        )
    
    def _default_data(self, categoria: str) -> TechSheetData:
        """Retorna dados padrão em caso de erro."""
        return TechSheetData(
            nome=f"{categoria.title()} Premium",
            categoria=categoria,
            descricao="Produto de design exclusivo com acabamento premium.",
            materiais=["Material premium"],
            cores=["Variadas"],
            dimensoes={
                "altura": "N/A",
                "largura": "N/A",
                "profundidade": "N/A"
            },
            detalhes=["Design moderno", "Acabamento premium"]
        )
    
    def _fallback_html(self, dados: TechSheetData) -> str:
        """HTML de fallback caso o template falhe."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Ficha Técnica - {dados['nome']}</title>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px; }}
                h1 {{ font-weight: 300; text-transform: uppercase; letter-spacing: 4px; }}
            </style>
        </head>
        <body>
            <h1>{dados['nome']}</h1>
            <p><strong>Categoria:</strong> {dados['categoria']}</p>
            <p><strong>Descrição:</strong> {dados['descricao']}</p>
            <p><strong>Materiais:</strong> {', '.join(dados['materiais'])}</p>
        </body>
        </html>
        """
