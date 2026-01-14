"""
Frida Orchestrator - Utility Functions
Funções auxiliares para manipulação de imagens e validações.
"""

import io
import json
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

    Suporta objetos aninhados usando algoritmo de contagem de chaves.

    Args:
        text: Texto que pode conter JSON

    Returns:
        dict parseado ou None se não encontrar JSON válido
    """
    if not text:
        return None

    # Tenta parse direto primeiro
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Encontra JSON em texto misto usando contagem de chaves
    # Isso resolve o problema de objetos aninhados que regex não captura
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(text[start:], start):
        # Lida com escape de caracteres dentro de strings
        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        # Alterna estado de string (ignora chaves dentro de strings)
        if char == '"':
            in_string = not in_string
            continue

        # Conta chaves apenas fora de strings
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1

            # Encontrou o fechamento do objeto raiz
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    # Continua procurando outro JSON válido
                    next_start = text.find('{', i + 1)
                    if next_start != -1:
                        return safe_json_parse(text[next_start:])
                    return None

    return None


# =============================================================================
# Magic Numbers (File Signatures)
# =============================================================================
# Referência: https://en.wikipedia.org/wiki/List_of_file_signatures

IMAGE_MAGIC_NUMBERS = {
    "jpeg": [
        b'\xff\xd8\xff\xe0',  # JPEG/JFIF
        b'\xff\xd8\xff\xe1',  # JPEG/EXIF
        b'\xff\xd8\xff\xe2',  # JPEG/ICC
        b'\xff\xd8\xff\xdb',  # JPEG raw
        b'\xff\xd8\xff\xee',  # JPEG IPTC
    ],
    "png": [b'\x89PNG\r\n\x1a\n'],  # PNG signature
    "gif": [b'GIF87a', b'GIF89a'],  # GIF87a ou GIF89a
    "webp": [b'RIFF'],  # WebP começa com RIFF (precisa verificar WEBP depois)
}

ALLOWED_CONTENT_TYPES = frozenset([
    "image/jpeg",
    "image/png", 
    "image/webp",
    "image/gif"
])

ALLOWED_PIL_FORMATS = frozenset(["JPEG", "PNG", "GIF", "WEBP"])


def validate_content_type(content_type: str) -> bool:
    """
    Validação RÁPIDA: Verifica apenas o header Content-Type.
    
    ⚠️ VULNERÁVEL a spoofing! Use apenas como primeira camada de filtro.
    Para validação segura, use validate_image_deep().
    
    Args:
        content_type: String do header Content-Type
        
    Returns:
        True se o content-type é de imagem suportada
    """
    return content_type in ALLOWED_CONTENT_TYPES


def validate_image_file(content_type: str) -> bool:
    """
    Alias para validate_content_type (compatibilidade retroativa).
    
    ⚠️ DEPRECATED: Prefira validate_image_deep() para validação segura.
    
    Args:
        content_type: String do header Content-Type
        
    Returns:
        True se o content-type é de imagem suportada
    """
    return validate_content_type(content_type)


def _check_magic_numbers(file_bytes: bytes) -> str | None:
    """
    Verifica os magic numbers (assinatura) do arquivo.
    
    Args:
        file_bytes: Primeiros bytes do arquivo (mínimo 12 bytes recomendado)
        
    Returns:
        Tipo da imagem detectado ('jpeg', 'png', 'gif', 'webp') ou None
    """
    if len(file_bytes) < 8:
        return None
    
    # Verifica cada formato
    for format_name, signatures in IMAGE_MAGIC_NUMBERS.items():
        for sig in signatures:
            if file_bytes.startswith(sig):
                # Verificação adicional para WebP
                if format_name == "webp":
                    # WebP: RIFF....WEBP
                    if len(file_bytes) >= 12 and file_bytes[8:12] == b'WEBP':
                        return "webp"
                else:
                    return format_name
    
    return None


def validate_image_deep(file_bytes: bytes, content_type: Optional[str] = None) -> tuple[bool, str]:
    """
    Validação PROFUNDA: Verifica magic numbers e integridade via Pillow.
    
    Esta função é SEGURA contra spoofing de Content-Type, pois valida
    os bytes reais do arquivo.
    
    Pipeline de validação:
    1. Verifica magic numbers (assinatura dos primeiros bytes)
    2. Tenta abrir com Pillow para validar integridade estrutural
    3. Confirma que o formato PIL está na lista permitida
    
    Args:
        file_bytes: Bytes completos do arquivo a validar
        content_type: Opcional. Se fornecido, valida consistência.
        
    Returns:
        Tuple (is_valid: bool, message: str)
        - is_valid: True se arquivo é imagem válida
        - message: Descrição do resultado ou erro
        
    Example:
        >>> with open("foto.jpg", "rb") as f:
        ...     is_valid, msg = validate_image_deep(f.read())
        >>> print(is_valid, msg)
        True "Imagem JPEG válida"
    """
    # Sanity check
    if not file_bytes or len(file_bytes) < 8:
        return False, "Arquivo vazio ou muito pequeno para ser uma imagem válida"
    
    # 1. Verifica magic numbers
    detected_format = _check_magic_numbers(file_bytes)
    if not detected_format:
        return False, "Assinatura de arquivo não corresponde a nenhum formato de imagem suportado"
    
    # 2. Tenta abrir com Pillow para validar integridade
    try:
        # Primeira abertura para verify()
        with io.BytesIO(file_bytes) as buffer1:
            image1 = Image.open(buffer1)
            try:
                image1.verify()
            finally:
                image1.close()
        
        # Segunda abertura para obter formato (verify() invalida o objeto)
        with io.BytesIO(file_bytes) as buffer2:
            image2 = Image.open(buffer2)
            try:
                pil_format = image2.format
            finally:
                image2.close()
        
    except Exception as e:
        return False, f"Arquivo corrompido ou não é uma imagem válida: {str(e)}"
    
    # 3. Verifica se formato PIL está na lista permitida
    if pil_format not in ALLOWED_PIL_FORMATS:
        return False, f"Formato '{pil_format}' não é suportado. Use: JPEG, PNG, GIF ou WebP"
    
    # 4. Validação opcional de consistência com Content-Type
    if content_type:
        expected_formats = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/gif": "GIF",
            "image/webp": "WEBP"
        }
        expected = expected_formats.get(content_type)
        if expected and pil_format != expected:
            # Apenas log, não bloqueia (Content-Type pode ser errado do browser)
            print(f"[WARN] Content-Type '{content_type}' não corresponde ao formato real '{pil_format}'")
    
    # 5. Tudo OK!
    return True, f"Imagem {pil_format} válida"


def generate_filename(categoria: str, extension: str = "png") -> str:
    """Gera um nome de arquivo único para a imagem processada."""
    import uuid
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    
    return f"{categoria}_{timestamp}_{unique_id}.{extension}"
