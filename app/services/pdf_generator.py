"""
FRIDA PDF Generator - Geração de PDFs de Fichas Técnicas (PRD-05)

Gera PDFs formatados das fichas técnicas de produtos usando ReportLab.

Uso:
    from app.services.pdf_generator import pdf_generator
    
    pdf_bytes = pdf_generator.generate(sheet_data, product_data, image_url)
"""

from io import BytesIO
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)


class TechnicalSheetPDFGenerator:
    """
    Gerador de PDFs para fichas técnicas de produtos.
    
    Features:
    - Layout profissional estilo FRIDA
    - Suporte a imagem do produto
    - Seções dinâmicas baseadas nos dados disponíveis
    - Formatação automática de datas e valores
    """
    
    # Cores da marca FRIDA
    FRIDA_BLACK = colors.HexColor("#1a1a1a")
    FRIDA_GRAY = colors.HexColor("#666666")
    FRIDA_BODY = colors.HexColor("#333333")
    FRIDA_LIGHT = colors.HexColor("#f5f5f5")
    FRIDA_BORDER = colors.HexColor("#e0e0e0")
    
    def __init__(self):
        """Inicializa estilos do PDF."""
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Cria estilos customizados para o PDF."""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='FridaTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.FRIDA_BLACK,
            alignment=TA_CENTER,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='FridaSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=self.FRIDA_GRAY,
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        # Cabeçalho de seção
        self.styles.add(ParagraphStyle(
            name='FridaSection',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=self.FRIDA_BLACK,
            fontName='Helvetica-Bold',
            spaceBefore=15,
            spaceAfter=8
        ))
        
        # Corpo do texto
        self.styles.add(ParagraphStyle(
            name='FridaBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.FRIDA_BODY,
            leading=14
        ))
        
        # Rodapé
        self.styles.add(ParagraphStyle(
            name='FridaFooter',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=self.FRIDA_GRAY,
            alignment=TA_CENTER
        ))
    
    def generate(
        self,
        sheet_data: Dict[str, Any],
        product_data: Dict[str, Any],
        processed_image_url: Optional[str] = None
    ) -> BytesIO:
        """
        Gera PDF da ficha técnica.
        
        Args:
            sheet_data: Dados da ficha (dict com dimensions, materials, etc)
            product_data: Dados do produto (category, name, etc)
            processed_image_url: URL da imagem processada (opcional)
        
        Returns:
            BytesIO com o conteúdo do PDF
        """
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        # === HEADER ===
        elements.append(Paragraph("FRIDA", self.styles['FridaTitle']))
        elements.append(Paragraph("Ficha Técnica de Produto", self.styles['FridaSubtitle']))
        
        # === IDENTIFICAÇÃO ===
        elements.append(Paragraph("Identificação", self.styles['FridaSection']))
        
        info_data = [
            ["Categoria", product_data.get("category", "N/A")],
            ["Nome", product_data.get("name", "N/A")],
            ["SKU", product_data.get("sku", "N/A")],
            ["Status", sheet_data.get("status", "draft").upper()],
            ["Versão", str(sheet_data.get("_version", 1))],
        ]
        
        # Adicionar created_at se disponível
        if product_data.get("created_at"):
            info_data.append(["Criado em", self._format_date(str(product_data["created_at"]))])
        
        elements.append(self._create_info_table(info_data))
        elements.append(Spacer(1, 0.5*cm))
        
        # === IMAGEM DO PRODUTO ===
        if processed_image_url:
            img = self._fetch_image(processed_image_url)
            if img:
                elements.append(Paragraph("Imagem do Produto", self.styles['FridaSection']))
                elements.append(img)
                elements.append(Spacer(1, 0.5*cm))
        
        # === DIMENSÕES ===
        data = sheet_data.get("data", sheet_data)  # Suporta nested ou flat
        
        if data.get("dimensions"):
            elements.append(Paragraph("Dimensões", self.styles['FridaSection']))
            dims = data["dimensions"]
            dim_data = []
            if dims.get("altura"):
                dim_data.append(["Altura", f"{dims['altura']} cm"])
            if dims.get("largura"):
                dim_data.append(["Largura", f"{dims['largura']} cm"])
            if dims.get("profundidade"):
                dim_data.append(["Profundidade", f"{dims['profundidade']} cm"])
            if dims.get("alca"):
                dim_data.append(["Alça", f"{dims['alca']} cm"])
            if dim_data:
                elements.append(self._create_info_table(dim_data))
        
        # === MATERIAIS ===
        if data.get("materials"):
            elements.append(Paragraph("Materiais", self.styles['FridaSection']))
            mats = data["materials"]
            mat_data = []
            if mats.get("principal"):
                mat_data.append(["Material Principal", mats["principal"]])
            if mats.get("forro"):
                mat_data.append(["Forro", mats["forro"]])
            if mats.get("ferragens"):
                mat_data.append(["Ferragens", mats["ferragens"]])
            if mats.get("ziper"):
                mat_data.append(["Zíper", mats["ziper"]])
            if mat_data:
                elements.append(self._create_info_table(mat_data))
        
        # === CORES ===
        if data.get("colors"):
            elements.append(Paragraph("Cores Disponíveis", self.styles['FridaSection']))
            colors_text = ", ".join(data["colors"])
            elements.append(Paragraph(colors_text, self.styles['FridaBody']))
            elements.append(Spacer(1, 0.3*cm))
        
        # === PESO ===
        if data.get("weight_grams"):
            elements.append(Paragraph("Peso", self.styles['FridaSection']))
            weight_kg = data["weight_grams"] / 1000
            elements.append(Paragraph(
                f"{data['weight_grams']}g ({weight_kg:.2f} kg)",
                self.styles['FridaBody']
            ))
            elements.append(Spacer(1, 0.3*cm))
        
        # === FORNECEDOR ===
        if data.get("supplier"):
            elements.append(Paragraph("Fornecedor", self.styles['FridaSection']))
            sup = data["supplier"]
            sup_data = []
            if sup.get("nome"):
                sup_data.append(["Nome", sup["nome"]])
            if sup.get("contato"):
                sup_data.append(["Contato", sup["contato"]])
            if sup.get("cnpj"):
                sup_data.append(["CNPJ", sup["cnpj"]])
            if sup.get("prazo_entrega"):
                sup_data.append(["Prazo de Entrega", sup["prazo_entrega"]])
            if sup_data:
                elements.append(self._create_info_table(sup_data))
        
        # === INSTRUÇÕES DE CUIDADO ===
        if data.get("care_instructions"):
            elements.append(Paragraph("Instruções de Cuidado", self.styles['FridaSection']))
            elements.append(Paragraph(
                data["care_instructions"],
                self.styles['FridaBody']
            ))
            elements.append(Spacer(1, 0.3*cm))
        
        # === CAMPOS CUSTOMIZADOS ===
        if data.get("custom_fields"):
            elements.append(Paragraph("Informações Adicionais", self.styles['FridaSection']))
            custom_data = [
                [str(k), str(v)]
                for k, v in data["custom_fields"].items()
            ]
            if custom_data:
                elements.append(self._create_info_table(custom_data))
        
        # === FOOTER ===
        elements.append(Spacer(1, 1*cm))
        generation_date = datetime.now().strftime("%d/%m/%Y às %H:%M")
        version = sheet_data.get("_version", 1)
        footer_text = f"Documento gerado em {generation_date} | Versão {version} | FRIDA v0.5.1"
        elements.append(Paragraph(footer_text, self.styles['FridaFooter']))
        
        # Gerar PDF
        doc.build(elements)
        buffer.seek(0)
        
        return buffer
    
    def _create_info_table(self, data: List[List[str]]) -> Table:
        """
        Cria tabela de informações (2 colunas: label + valor).
        
        Args:
            data: Lista de [label, valor]
        
        Returns:
            Table formatada
        """
        table = Table(data, colWidths=[4*cm, 10*cm])
        
        table.setStyle(TableStyle([
            # Header styling
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.FRIDA_BLACK),
            ('TEXTCOLOR', (1, 0), (1, -1), self.FRIDA_BODY),
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            # Borders
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, self.FRIDA_BORDER),
            # Background alternado
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, self.FRIDA_LIGHT]),
            # Alinhamento
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return table
    
    def _fetch_image(self, url: str, max_width: float = 10*cm) -> Optional[RLImage]:
        """
        Busca imagem de URL e formata para o PDF.
        
        Args:
            url: URL da imagem
            max_width: Largura máxima em cm
        
        Returns:
            Imagem formatada ou None se falhar
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            img_buffer = BytesIO(response.content)
            
            # Criar imagem e calcular proporções
            img = RLImage(img_buffer)
            
            # Manter aspect ratio
            aspect = img.imageHeight / img.imageWidth
            img.drawWidth = max_width
            img.drawHeight = max_width * aspect
            
            # Limitar altura máxima
            max_height = 12*cm
            if img.drawHeight > max_height:
                img.drawHeight = max_height
                img.drawWidth = max_height / aspect
            
            return img
            
        except Exception as e:
            print(f"[PDF] ⚠ Erro ao buscar imagem: {str(e)}")
            return None
    
    def _format_date(self, date_str: str) -> str:
        """
        Formata data ISO para DD/MM/YYYY.
        
        Args:
            date_str: Data em formato ISO
        
        Returns:
            Data formatada ou "N/A"
        """
        try:
            # Tenta vários formatos comuns
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(date_str[:19], fmt)
                    return dt.strftime("%d/%m/%Y")
                except ValueError:
                    continue
            return date_str[:10] if len(date_str) >= 10 else "N/A"
        except:
            return "N/A"


# =============================================================================
# Singleton
# =============================================================================

pdf_generator = TechnicalSheetPDFGenerator()
