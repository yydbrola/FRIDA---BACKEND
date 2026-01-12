"""
Frida Orchestrator - Utility Functions
Funções auxiliares para manipulação de imagens e validações.
"""

import io
import json
import re
from PIL import Image
from typing import Optional


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Converte uma imagem PIL para bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()


def bytes_to_image(image_bytes: bytes) -> Image.Image:
    """Converte bytes para uma imagem PIL."""
    return Image.open(io.BytesIO(image_bytes))


def resize_image(image: Image.Image, size: tuple[int, int] = (1080, 1080)) -> Image.Image:
    """
    Redimensiona a imagem para o tamanho padrão de e-commerce.
    Mantém aspect ratio e centraliza em fundo branco.
    """
    # Cria uma nova imagem com fundo branco
    new_image = Image.new("RGBA", size, (255, 255, 255, 255))
    
    # Calcula o tamanho proporcional
    image.thumbnail(size, Image.Resampling.LANCZOS)
    
    # Centraliza a imagem
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    
    # Cola a imagem no centro
    if image.mode == "RGBA":
        new_image.paste(image, (x, y), image)
    else:
        new_image.paste(image, (x, y))
    
    return new_image


def safe_json_parse(text: str) -> Optional[dict]:
    """
    Parse seguro de JSON retornado pela IA.
    Tenta extrair JSON mesmo que venha com texto extra.
    """
    try:
        # Tenta parse direto
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Tenta extrair JSON de dentro do texto
    json_pattern = r'\{[^{}]*\}'
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    return None


def validate_image_file(content_type: str) -> bool:
    """Valida se o arquivo é uma imagem suportada."""
    valid_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif"
    ]
    return content_type in valid_types


def generate_filename(categoria: str, extension: str = "png") -> str:
    """Gera um nome de arquivo único para a imagem processada."""
    import uuid
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    
    return f"{categoria}_{timestamp}_{unique_id}.{extension}"
