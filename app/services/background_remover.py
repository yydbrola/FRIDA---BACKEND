"""
Frida Orchestrator - Background Remover Service
Remoção de fundo e aplicação de fundo branco puro (#FFFFFF).
"""

import io
from PIL import Image
from rembg import remove

from app.config import settings
from app.utils import image_to_bytes, resize_image


class BackgroundRemoverService:
    """
    Serviço de remoção de fundo usando rembg.
    Garante fundo branco puro (#FFFFFF) para imagens de e-commerce.
    """
    
    def __init__(self):
        """Inicializa o serviço."""
        self.output_size = settings.OUTPUT_SIZE
    
    def remover_fundo(self, image_bytes: bytes) -> Image.Image:
        """
        Remove o fundo de uma imagem.
        
        Args:
            image_bytes: Bytes da imagem original
            
        Returns:
            Imagem PIL com fundo transparente
        """
        # Remove o fundo usando rembg
        output_bytes = remove(image_bytes)
        
        # Converte para PIL Image
        image = Image.open(io.BytesIO(output_bytes))
        
        return image
    
    def aplicar_fundo_branco(self, image: Image.Image) -> Image.Image:
        """
        Aplica fundo branco puro (#FFFFFF) em uma imagem.
        
        Args:
            image: Imagem PIL (preferencialmente com fundo transparente)
            
        Returns:
            Imagem com fundo branco
        """
        # Garante modo RGBA
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        
        # Cria fundo branco
        white_bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
        
        # Compõe a imagem sobre o fundo branco
        composite = Image.alpha_composite(white_bg, image)
        
        # Converte para RGB (remove canal alpha)
        return composite.convert("RGB")
    
    def processar(self, image_bytes: bytes, redimensionar: bool = True) -> tuple[Image.Image, bytes]:
        """
        Pipeline completo: remove fundo, aplica branco e redimensiona.
        
        Args:
            image_bytes: Bytes da imagem original
            redimensionar: Se True, redimensiona para tamanho padrão
            
        Returns:
            Tuple com (imagem PIL, bytes da imagem)
        """
        # 1. Remove o fundo
        image_sem_fundo = self.remover_fundo(image_bytes)
        
        # 2. Aplica fundo branco
        image_fundo_branco = self.aplicar_fundo_branco(image_sem_fundo)
        
        # 3. Redimensiona se necessário
        if redimensionar:
            image_final = resize_image(image_fundo_branco, self.output_size)
        else:
            image_final = image_fundo_branco
        
        # 4. Converte para bytes
        output_bytes = image_to_bytes(image_final, format="PNG")
        
        return image_final, output_bytes
    
    def processar_com_ia_premium(
        self, 
        image_bytes: bytes, 
        classificacao: dict
    ) -> tuple[Image.Image, bytes]:
        """
        Processa imagem com foco em qualidade premium.
        Para sketches, faz apenas remoção de fundo e fundo branco.
        
        Args:
            image_bytes: Bytes da imagem original
            classificacao: Resultado da classificação (item, estilo)
            
        Returns:
            Tuple com (imagem PIL, bytes da imagem)
        """
        # Por enquanto, usa o pipeline padrão
        # Futuramente pode adicionar lógica específica para sketches vs fotos
        return self.processar(image_bytes)
