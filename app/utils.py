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


# =============================================================================
# Sheet Data Utilities (P0 - Schema v2)
# =============================================================================

def deep_merge(base: dict, updates: dict) -> dict:
    """
    Merge profundo de dicionários.
    
    Combina recursivamente dicts aninhados, onde valores de 'updates'
    sobrescrevem valores de 'base' no mesmo caminho.
    
    Args:
        base: Dicionário base (não modificado)
        updates: Dicionário com atualizações
        
    Returns:
        Novo dicionário mesclado
        
    Example:
        >>> base = {"a": {"b": 1, "c": 2}, "d": 3}
        >>> updates = {"a": {"b": 10}}
        >>> deep_merge(base, updates)
        {"a": {"b": 10, "c": 2}, "d": 3}
    """
    if base is None:
        base = {}
    if updates is None:
        return base.copy()
    
    result = base.copy()
    
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Merge recursivo para dicts aninhados
            result[key] = deep_merge(result[key], value)
        else:
            # Sobrescreve valor
            result[key] = value
    
    return result


def apply_na_to_empty(data: dict, na_value: str = "N/A") -> dict:
    """
    Substitui None e strings vazias por 'N/A' para exibição.
    
    Preserva metadados que começam com '_' (ex: _version, _schema).
    Útil para preparar dados para exibição em PDFs e templates.
    
    Args:
        data: Dicionário a processar
        na_value: Valor a usar para campos vazios (default: "N/A")
        
    Returns:
        Novo dicionário com valores vazios substituídos
        
    Example:
        >>> apply_na_to_empty({"name": None, "_version": 2})
        {"name": "N/A", "_version": 2}
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    
    for key, value in data.items():
        # Preserva metadados
        if key.startswith("_"):
            result[key] = value
        elif isinstance(value, dict):
            result[key] = apply_na_to_empty(value, na_value)
        elif isinstance(value, list):
            # Preserva listas como estão
            result[key] = value
        elif value is None or value == "":
            result[key] = na_value
        else:
            result[key] = value
    
    return result


def remove_na_values(data: dict) -> dict:
    """
    Remove valores 'N/A' convertendo para None antes de salvar.
    
    Operação inversa de apply_na_to_empty().
    Use antes de salvar no banco para manter dados limpos.
    
    Args:
        data: Dicionário a processar
        
    Returns:
        Novo dicionário com 'N/A' convertido para None
        
    Example:
        >>> remove_na_values({"name": "N/A", "color": "preto"})
        {"name": None, "color": "preto"}
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = remove_na_values(value)
        elif value == "N/A":
            result[key] = None
        else:
            result[key] = value
    
    return result


def get_nested_value(data: dict, path: str):
    """
    Obtém valor de caminho aninhado usando notação de ponto.
    
    Args:
        data: Dicionário a buscar
        path: Caminho separado por pontos (ex: 'dimensions.height_cm')
        
    Returns:
        Valor encontrado ou None se caminho não existir
        
    Example:
        >>> get_nested_value({"a": {"b": {"c": 42}}}, "a.b.c")
        42
    """
    if not data or not path:
        return None
    
    keys = path.split(".")
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    
    return current


def set_nested_value(data: dict, path: str, value) -> None:
    """
    Define valor em caminho aninhado, criando dicts intermediários se necessário.
    
    Modifica o dicionário in-place.
    
    Args:
        data: Dicionário a modificar
        path: Caminho separado por pontos (ex: 'dimensions.height_cm')
        value: Valor a definir
        
    Example:
        >>> d = {}
        >>> set_nested_value(d, "a.b.c", 42)
        >>> d
        {"a": {"b": {"c": 42}}}
    """
    if not path:
        return
    
    keys = path.split(".")
    current = data
    
    # Navega/cria até o penúltimo nível
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    
    # Define o valor no último nível
    current[keys[-1]] = value

