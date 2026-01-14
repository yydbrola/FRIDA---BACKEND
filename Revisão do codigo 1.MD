# REVIEW.MD - Code Review com Context7  ( PRD 0,1,2 e 3)

**Data da Revisao:** 2026-01-13
**Versao do Projeto:** 0.5.3
**Ferramenta:** Context7 (Documentacao Atualizada)
**Revisor:** Claude Opus 4.5

---

## Resumo Executivo

| Categoria | Status | Prioridade |
|-----------|--------|------------|
| FastAPI Lifecycle | DEPRECADO | Alta |
| Pillow Memory Leak | PROBLEMA | Alta |
| Versao Desatualizada | INCONSISTENCIA | Media |
| PyJWT | OK | - |
| Pillow Resampling | OK | - |
| CORS Configuration | OK | - |

---

## 1. FastAPI - `@app.on_event` DEPRECADO

**Severidade:** Alta
**Arquivo:** `app/main.py`
**Linha:** 98

### Problema

O decorator `@app.on_event("startup")` esta **depreciado** na versao atual do FastAPI. A documentacao oficial recomenda usar o `lifespan` async context manager.

### Evidencia (Context7)

> "on_startup (Optional[Sequence[Callable]]) - **Deprecated**. A list of startup event handler functions. **Use lifespan instead.**"
>
> "This approach is the recommended way going forward for handling application initialization and cleanup logic."

### Codigo Atual (Problematico)

```python
# app/main.py:98
@app.on_event("startup")
async def startup_event():
    """Inicializa os servicos no startup..."""
    global classifier_service, background_service, tech_sheet_service, storage_service
    # ... codigo de inicializacao
```

### Correcao Recomendada

```python
# app/main.py - SUBSTITUIR linhas 98-190

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicacao.
    Substitui @app.on_event("startup") depreciado.
    """
    global classifier_service, background_service, tech_sheet_service, storage_service

    print("[STARTUP] Iniciando Frida Orchestrator v0.5.3...")

    # Validacao de configuracoes obrigatorias
    if not settings.GEMINI_API_KEY:
        raise StartupError("[STARTUP] FALHA CRITICA: GEMINI_API_KEY nao configurada!")

    print("[STARTUP] GEMINI_API_KEY configurada")

    # Inicializacao de servicos
    try:
        background_service = BackgroundRemoverService()
        classifier_service = ClassifierService()
        tech_sheet_service = TechSheetService()
        print("[STARTUP] Servicos criticos inicializados")
    except Exception as e:
        raise StartupError(f"[STARTUP] FALHA CRITICA: {e}")

    # Storage opcional
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            storage_service = StorageService()
            print("[STARTUP] StorageService inicializado")
        except Exception:
            print("[STARTUP] StorageService nao inicializado (opcional)")

    print("[STARTUP] Servidor pronto!")

    yield  # Aplicacao rodando

    # Shutdown logic (se necessario)
    print("[SHUTDOWN] Encerrando servicos...")

# Passar lifespan ao criar o app
app = FastAPI(
    title="Frida Orchestrator",
    description="Backend de processamento de imagens e IA para produtos de moda",
    version="0.5.3",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # NOVO
)
```

---

## 2. Pillow - Memory Leak em `validate_image_deep()`

**Severidade:** Alta
**Arquivo:** `app/utils.py`
**Linhas:** 242, 248

### Problema

A funcao `validate_image_deep()` abre imagens com `Image.open()` mas nunca fecha explicitamente os objetos `Image`. Em uso intensivo (muitas validacoes), isso pode causar memory leak.

### Codigo Atual (Problematico)

```python
# app/utils.py:241-252
try:
    image = Image.open(io.BytesIO(file_bytes))  # Linha 242 - NAO FECHA

    # Forca leitura completa para detectar arquivos corrompidos
    image.verify()

    # Reabre para obter formato (verify() invalida o objeto)
    image = Image.open(io.BytesIO(file_bytes))  # Linha 248 - NAO FECHA
    pil_format = image.format

except Exception as e:
    return False, f"Arquivo corrompido ou nao e uma imagem valida: {str(e)}"
```

### Correcao Recomendada

```python
# app/utils.py:241-260 - SUBSTITUIR por:
try:
    # Primeira abertura para verify()
    with io.BytesIO(file_bytes) as buffer1:
        image1 = Image.open(buffer1)
        try:
            image1.verify()
        finally:
            image1.close()

    # Segunda abertura para obter formato
    with io.BytesIO(file_bytes) as buffer2:
        image2 = Image.open(buffer2)
        try:
            pil_format = image2.format
        finally:
            image2.close()

except Exception as e:
    return False, f"Arquivo corrompido ou nao e uma imagem valida: {str(e)}"
```

---

## 3. Pillow - Memory Leak em `remover_fundo()`

**Severidade:** Alta
**Arquivo:** `app/services/background_remover.py`
**Linha:** 38

### Problema

A funcao `remover_fundo()` abre uma imagem com `Image.open()` mas nunca fecha. O objeto retornado pode acumular em memoria.

### Codigo Atual (Problematico)

```python
# app/services/background_remover.py:34-40
def remover_fundo(self, image_bytes: bytes) -> Image.Image:
    # Remove o fundo usando rembg
    output_bytes = remove(image_bytes)

    # Converte para PIL Image
    image = Image.open(io.BytesIO(output_bytes))  # NUNCA FECHA

    return image
```

### Correcao Recomendada

Opcao 1: Fechar no caller (responsabilidade do chamador)
```python
# Atualizar docstring para alertar o caller
def remover_fundo(self, image_bytes: bytes) -> Image.Image:
    """
    Remove o fundo de uma imagem.

    IMPORTANTE: O caller e responsavel por fechar a imagem retornada
    com image.close() apos o uso.

    ...
    """
```

Opcao 2: Retornar bytes em vez de Image
```python
# app/services/background_remover.py:24-40 - SUBSTITUIR por:
def remover_fundo(self, image_bytes: bytes) -> bytes:
    """
    Remove o fundo de uma imagem.

    Args:
        image_bytes: Bytes da imagem original

    Returns:
        Bytes da imagem com fundo removido (PNG com transparencia)
    """
    # Remove o fundo usando rembg
    output_bytes = remove(image_bytes)
    return output_bytes
```

---

## 4. Pillow - Memory Leak em `validate_from_bytes()`

**Severidade:** Media
**Arquivo:** `app/services/husk_layer.py`
**Linha:** 135

### Problema

A funcao `validate_from_bytes()` abre imagem mas nao fecha apos uso.

### Codigo Atual (Problematico)

```python
# app/services/husk_layer.py:125-136
def validate_from_bytes(self, image_bytes: bytes) -> QualityReport:
    """Versao para API: valida imagem a partir de bytes."""
    image = Image.open(BytesIO(image_bytes))  # NAO FECHA
    return self.calculate_quality_score(image)
```

### Correcao Recomendada

```python
# app/services/husk_layer.py:125-140 - SUBSTITUIR por:
def validate_from_bytes(self, image_bytes: bytes) -> QualityReport:
    """
    Versao para API: valida imagem a partir de bytes.

    Args:
        image_bytes: Imagem em bytes (PNG/JPEG)

    Returns:
        QualityReport com resultado da validacao
    """
    with BytesIO(image_bytes) as buffer:
        image = Image.open(buffer)
        try:
            return self.calculate_quality_score(image)
        finally:
            image.close()
```

---

## 5. Versao Desatualizada em Multiplos Locais

**Severidade:** Media
**Arquivo:** `app/main.py`
**Linhas:** 32, 113, 213, 272, 681

### Problema

A versao exibida em varios locais e "0.5.0" mas o CLAUDE.md indica versao atual "0.5.3".

### Locais a Atualizar

| Linha | Codigo Atual | Correcao |
|-------|--------------|----------|
| 32 | `version="0.5.0"` | `version="0.5.3"` |
| 113 | `v0.5.0...` | `v0.5.3...` |
| 213 | `v0.5.0` | `v0.5.3` |
| 272 | `version="0.5.0"` | `version="0.5.3"` |
| 681 | `"version": "0.5.0"` | `"version": "0.5.3"` |

### Sugestao de Melhoria

Centralizar a versao em `config.py`:

```python
# app/config.py - ADICIONAR
APP_VERSION = "0.5.3"
```

E usar em todos os locais:
```python
# app/main.py
from app.config import settings, APP_VERSION

app = FastAPI(
    title="Frida Orchestrator",
    version=APP_VERSION,  # Centralizado
    ...
)
```

---

## 6. Itens Verificados - OK

### 6.1 PyJWT - Implementacao Correta

**Arquivo:** `app/auth/supabase.py`
**Linhas:** 100-110

O codigo esta seguindo as melhores praticas documentadas:
- Usa `algorithms=[JWT_ALGORITHM]` explicitamente (seguranca)
- Valida `audience` corretamente
- Usa `options` para configurar verificacao

```python
# CORRETO - Nenhuma alteracao necessaria
payload = jwt.decode(
    token,
    settings.SUPABASE_JWT_SECRET,
    algorithms=[JWT_ALGORITHM],  # Explicito - CORRETO
    audience=JWT_AUDIENCE,        # Valida audience - CORRETO
    options={
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True
    }
)
```

### 6.2 Pillow Resampling - Atualizado

**Arquivos:** `app/services/image_composer.py:95`, `app/utils.py:34`

O codigo usa a forma atualizada `Image.Resampling.LANCZOS` em vez da depreciada `Image.LANCZOS`:

```python
# CORRETO - app/services/image_composer.py:95
product_resized = product.resize(
    (new_w, new_h),
    Image.Resampling.LANCZOS  # Forma atualizada - CORRETO
)

# CORRETO - app/utils.py:34
image.thumbnail(size, Image.Resampling.LANCZOS)  # Forma atualizada - CORRETO
```

### 6.3 CORS Configuration - Adequada

**Arquivo:** `app/main.py:38-48`

A configuracao CORS esta adequada para o caso de uso:

```python
# CORRETO - Nenhuma alteracao necessaria
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Sugestoes de Melhoria (Nao-Criticas)

### 7.1 Supabase Client - Considerar Singleton com TTL

**Arquivo:** `app/database.py:17-46`

O codigo atual cria um novo cliente a cada chamada. Embora funcional, pode ser otimizado com um singleton com TTL para renovacao periodica.

**Status:** Funcional, otimizacao opcional.

### 7.2 Rate Limiting - Nao Implementado

Conforme documentado no CLAUDE.md, rate limiting ainda nao foi implementado. Este e o unico blocker de seguranca restante.

**Recomendacao:** Implementar com `slowapi` conforme sugerido no CLAUDE.md.

---

## Checklist de Acoes

- [x] **ALTA** - ~~Migrar `@app.on_event("startup")` para `lifespan` context manager~~ (ADIADO - depreciado mas funcional)
- [x] **ALTA** - Corrigir memory leak em `utils.py:validate_image_deep()` ✅ APLICADO
- [x] **ALTA** - Corrigir memory leak em `background_remover.py:remover_fundo()` ✅ DOCUMENTADO
- [x] **MEDIA** - Corrigir memory leak em `husk_layer.py:validate_from_bytes()` ✅ APLICADO
- [x] **MEDIA** - Atualizar versao de 0.5.0 para 0.5.3 em todos os locais ✅ APLICADO
- [x] **BAIXA** - Centralizar versao em `config.py` ✅ APLICADO
- [ ] **BAIXA** - Implementar rate limiting com slowapi

---

## Implementacao das Correcoes (Claude - 2026-01-13)

### Correcao 1: Memory Leak em `validate_image_deep()`
**Arquivo:** `app/utils.py` | **Linhas:** 240-260
- Adicionado `try/finally` com `image.close()` para ambas aberturas
- Usado context manager para BytesIO buffers

### Correcao 2: Memory Leak em `validate_from_bytes()`
**Arquivo:** `app/services/husk_layer.py` | **Linhas:** 125-140
- Context manager `with BytesIO()` + `try/finally` com `image.close()`

### Correcao 3: Docstring Warning em `remover_fundo()`
**Arquivo:** `app/services/background_remover.py` | **Linhas:** 24-43
- Adicionado warning: "O caller e responsavel por fechar a imagem"
- Mantido retorno `Image.Image` para evitar breaking change

### Correcao 4: Versao Centralizada
**Arquivos:** `app/config.py`, `app/main.py`
- `APP_VERSION = "0.5.3"` centralizado em config.py
- `FastAPI(version=APP_VERSION)` no main.py

### Correcao 5: Lifespan Migration (ADIADA)
- `@app.on_event` depreciado mas funcional
- Migrar na versao 0.6.0

---

## Verificacao Pos-Aplicacao

```
✅ APP_VERSION: 0.5.3
✅ FastAPI version: 0.5.3
✅ All imports successful
```

---

## Referencias

- [FastAPI Lifespan Documentation](https://fastapi.tiangolo.com/advanced/events/)
- [Pillow Best Practices](https://pillow.readthedocs.io/en/stable/)
- [PyJWT Security](https://pyjwt.readthedocs.io/en/stable/usage.html)
- Context7 Library Documentation (2026-01-13)

---

**Fim do Documento**
**Ultima atualizacao:** 2026-01-13 23:12 BRT
**Implementado por:** Claude (Anthropic)

