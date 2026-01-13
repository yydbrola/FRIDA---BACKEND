"""
Image Composer Service - FRIDA v0.5.2

Compõe imagens segmentadas (PNG com transparência) em fundo branco
padrão DIGS para catálogo de moda.

Features:
- Fundo branco puro #FFFFFF
- Produto centralizado ocupando 80-90% do frame
- Sombra suave projetada abaixo do produto
- Output mínimo 1200x1200px
"""

from PIL import Image, ImageFilter, ImageDraw
from io import BytesIO
from typing import Tuple, Optional


class ImageComposer:
    """
    Compositor de imagens para padrão DIGS.
    
    Recebe imagem PNG com transparência (já segmentada) e compõe
    em fundo branco com sombra suave.
    """
    
    # ==========================================================================
    # Configurações
    # ==========================================================================
    
    TARGET_SIZE: int = 1200  # Tamanho mínimo do output (px)
    PRODUCT_COVERAGE: float = 0.85  # Produto ocupa 85% do frame
    BACKGROUND_COLOR: Tuple[int, int, int] = (255, 255, 255)  # Branco puro
    SHADOW_OPACITY: int = 40  # Opacidade da sombra (0-255)
    SHADOW_BLUR: int = 15  # Blur gaussiano da sombra
    SHADOW_OFFSET: Tuple[int, int] = (0, 10)  # Offset X, Y da sombra
    
    # ==========================================================================
    # Métodos Públicos
    # ==========================================================================
    
    def compose_white_background(
        self, 
        segmented_image: Image.Image, 
        target_size: Optional[int] = None
    ) -> Image.Image:
        """
        Compõe imagem segmentada em fundo branco com sombra.
        
        Args:
            segmented_image: Imagem PNG com transparência (modo RGBA)
            target_size: Tamanho do output (usa TARGET_SIZE se None)
            
        Returns:
            Imagem RGB com fundo branco, produto centralizado e sombra
            
        Raises:
            ValueError: Se imagem não tiver canal alpha
        """
        target = target_size or self.TARGET_SIZE
        
        # Garantir modo RGBA
        if segmented_image.mode != 'RGBA':
            if segmented_image.mode == 'RGB':
                raise ValueError(
                    "Imagem não possui transparência. "
                    "Use uma imagem PNG com canal alpha."
                )
            segmented_image = segmented_image.convert('RGBA')
        
        # 1. Encontrar bounding box do conteúdo
        bbox = self._get_content_bbox(segmented_image)
        if bbox is None:
            # Imagem completamente transparente
            print("[COMPOSER] ⚠️ Imagem sem conteúdo visível")
            canvas = Image.new('RGB', (target, target), self.BACKGROUND_COLOR)
            return canvas
        
        # 2. Recortar produto (apenas área com conteúdo)
        product = segmented_image.crop(bbox)
        product_w, product_h = product.size
        
        print(f"[COMPOSER] Produto: {product_w}x{product_h}px")
        
        # 3. Calcular escala para ocupar 85% do frame
        scale = self._calculate_scale(product_w, product_h, target)
        new_w = int(product_w * scale)
        new_h = int(product_h * scale)
        
        print(f"[COMPOSER] Redimensionando: {new_w}x{new_h}px (scale={scale:.2f})")
        
        # 4. Redimensionar produto com alta qualidade
        product_resized = product.resize(
            (new_w, new_h), 
            Image.Resampling.LANCZOS
        )
        
        # 5. Criar canvas branco
        canvas = Image.new('RGB', (target, target), self.BACKGROUND_COLOR)
        
        # 6. Calcular posição centralizada
        paste_x = (target - new_w) // 2
        paste_y = (target - new_h) // 2
        
        # 7. Criar e aplicar sombra
        shadow = self._create_shadow(product_resized, (target, target))
        shadow_x = paste_x + self.SHADOW_OFFSET[0]
        shadow_y = paste_y + self.SHADOW_OFFSET[1]
        
        # Compor sombra no canvas
        canvas.paste(shadow, (shadow_x, shadow_y), shadow)
        
        # 8. Colar produto sobre a sombra
        canvas.paste(product_resized, (paste_x, paste_y), product_resized)
        
        print(f"[COMPOSER] ✓ Composição completa: {target}x{target}px")
        
        return canvas
    
    def compose_from_bytes(
        self,
        image_bytes: bytes,
        target_size: Optional[int] = None
    ) -> bytes:
        """
        Versão para API: recebe e retorna bytes.

        Args:
            image_bytes: PNG com transparência (bytes)
            target_size: Tamanho do output

        Returns:
            PNG final composto (bytes)
        """
        # Carregar imagem com context manager para evitar leak
        with BytesIO(image_bytes) as input_buffer:
            input_image = Image.open(input_buffer)

            try:
                # Compor
                result = self.compose_white_background(input_image, target_size)

                # Converter para bytes
                with BytesIO() as output:
                    result.save(output, format='PNG', optimize=True)
                    return output.getvalue()
            finally:
                # Fechar imagens PIL explicitamente
                input_image.close()
                result.close()
    
    # ==========================================================================
    # Métodos Privados
    # ==========================================================================
    
    def _get_content_bbox(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """
        Encontra bounding box do conteúdo não-transparente.
        
        Args:
            image: Imagem RGBA
            
        Returns:
            Tuple (left, upper, right, lower) ou None se vazia
        """
        # Extrair canal alpha
        if image.mode != 'RGBA':
            return image.getbbox()
        
        # Usar canal alpha para encontrar bbox
        alpha = image.split()[-1]  # Canal A
        return alpha.getbbox()
    
    def _calculate_scale(
        self, 
        product_w: int, 
        product_h: int, 
        target_size: int
    ) -> float:
        """
        Calcula fator de escala para produto ocupar PRODUCT_COVERAGE do frame.
        
        Args:
            product_w: Largura atual do produto
            product_h: Altura atual do produto
            target_size: Tamanho do canvas
            
        Returns:
            Fator de escala (float)
        """
        # Área disponível para o produto
        available = target_size * self.PRODUCT_COVERAGE
        
        # Escalar pelo lado maior
        scale_w = available / product_w
        scale_h = available / product_h
        
        # Usar menor escala para manter proporção
        return min(scale_w, scale_h)
    
    def _create_shadow(
        self, 
        product: Image.Image, 
        canvas_size: Tuple[int, int]
    ) -> Image.Image:
        """
        Cria sombra suave do produto.
        
        Args:
            product: Imagem RGBA do produto redimensionado
            canvas_size: Tamanho do canvas (width, height)
            
        Returns:
            Imagem RGBA com sombra (para compor via paste com mask)
        """
        # Criar imagem para sombra (mesmo tamanho do produto)
        shadow = Image.new('RGBA', product.size, (0, 0, 0, 0))
        
        # Desenhar forma sólida preta onde tem conteúdo
        if product.mode == 'RGBA':
            # Usar alpha do produto como máscara
            alpha = product.split()[-1]
            
            # Criar sombra com opacidade configurada
            shadow_layer = Image.new('RGBA', product.size, (0, 0, 0, self.SHADOW_OPACITY))
            shadow.paste(shadow_layer, mask=alpha)
        else:
            # Fallback: preencher retângulo
            draw = ImageDraw.Draw(shadow)
            draw.rectangle(
                [(0, 0), product.size],
                fill=(0, 0, 0, self.SHADOW_OPACITY)
            )
        
        # Aplicar blur gaussiano
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=self.SHADOW_BLUR))
        
        return shadow


# =============================================================================
# Singleton Export
# =============================================================================

image_composer = ImageComposer()
