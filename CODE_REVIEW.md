# Code Review - Frida Orchestrator

**Versao:** 0.5.1
**Data:** 2026-01-13 (Revisao 2)
**Revisor:** Claude Code (Opus 4.5)
**Status do Projeto:** Em desenvolvimento (64% testes passando)

---

## Changelog da Revisao

### Atualizacoes desde 2026-01-12

| Mudanca | Tipo | Arquivo(s) |
|---------|------|------------|
| Novos endpoints `/products` e `/products/{id}` | Feature | `main.py` |
| Funcoes `create_product`, `get_user_products`, `create_image` | Feature | `database.py` |
| Tabelas `products` e `images` com RLS | Schema | `04_create_products.sql`, `05_create_images.sql` |
| Model `AuthUser` com role para RBAC | Enhancement | `auth/supabase.py` |
| GEMINI.md atualizado para v0.5.1 | Docs | `GEMINI.md` |
| Integracao de product_id no fluxo `/process` | Enhancement | `main.py`, `storage.py` |

### Bugs Criticos - Status

| Bug | Status | Observacao |
|-----|--------|------------|
| JSON Parsing (regex) | ❌ NAO CORRIGIDO | `utils.py:62` |
| RBAC Decorators | ❌ NAO CORRIGIDO | `permissions.py:39` |

---

## Resumo Executivo

O **Frida Orchestrator** e um backend FastAPI bem estruturado para processamento de imagens de produtos de moda. Apresenta arquitetura solida com padrao de camada de servicos, mas possui algumas falhas tecnicas que devem ser corrigidas antes de producao.

| Aspecto | Avaliacao |
|---------|-----------|
| Arquitetura | ★★★★★ Excelente |
| Qualidade de Codigo | ★★★★☆ Boa |
| Seguranca | ★★★☆☆ Adequada |
| Testes | ★★★☆☆ Parcial (64%) |
| Documentacao | ★★★★★ Excelente |
| **Score Geral** | **7.5/10** |

---

## 1. Arquitetura e Design

### 1.1 Pontos Fortes

#### Service Layer Pattern Bem Implementado
- Separacao clara entre rotas (`main.py`) e logica de negocio (`services/`)
- Cada servico com responsabilidade unica
- Facilita testes e manutencao

```
FastAPI Routes (main.py)
    ↓
Service Layer (app/services/)
    ↓
External Dependencies (Gemini, rembg, Supabase)
```

#### Fail-Fast Startup Pattern
- Servidor nao inicia sem `GEMINI_API_KEY`
- Servicos criticos validados no startup
- Erros de configuracao detectados no deploy, nao em runtime

**Localizacao:** `main.py:92-184`

#### Validacao Multi-camada de Imagens
```
Content-Type → Magic Numbers → Pillow Integrity
```
- Protecao contra spoofing e corrupcao de arquivos
- Tres camadas de defesa

**Localizacao:** `utils.py:161-229`

#### Structured Output do Gemini
- Uso de `response_mime_type="application/json"` + `response_schema`
- Garante JSON valido sem parsing regex
- Evita alucinacoes e erros de parsing

**Localizacao:** `classifier.py:100-104`

### 1.2 Pontos Fracos

#### Magic Strings Espalhados
Strings como "bolsa", "lancheira", "garrafa_termica" aparecem em varios arquivos sem centralizacao.

**Recomendacao:** Usar Enums para consistencia:

```python
# Sugerido - criar enums.py ou adicionar em config.py
from enum import Enum

class ProductCategory(str, Enum):
    BOLSA = "bolsa"
    LANCHEIRA = "lancheira"
    GARRAFA_TERMICA = "garrafa_termica"
    DESCONHECIDO = "desconhecido"

class ProductStyle(str, Enum):
    SKETCH = "sketch"
    FOTO = "foto"
    DESCONHECIDO = "desconhecido"
```

#### Rotas Sincronas
- Decisao correta para operacoes CPU-bound (rembg)
- Porem, operacoes de banco poderiam ser async para melhor throughput

---

## 2. Bugs e Issues Criticos

### 2.1 Bug no JSON Parsing

**Severidade:** 🔴 Alta
**Arquivo:** `utils.py:50-71`
**Linha:** 66

```python
# Regex atual - INCORRETO para JSON aninhado
match = re.search(r'\{[^{}]*\}', texto)
```

**Problema:** A regex `r'\{[^{}]*\}'` nao captura objetos com aninhamento.

**Exemplo de falha:**
```json
{"nome": "Bolsa", "dimensoes": {"altura": "30cm"}}
// Regex retorna apenas: {"altura": "30cm"}
```

**Impacto:** Pode corromper dados de ficha tecnica que contem objetos aninhados como `dimensoes`.

**Solucao Recomendada:**

```python
import json

def safe_json_parse(texto: str) -> dict:
    """
    Extrai JSON de texto misto de forma segura.
    Suporta objetos aninhados.
    """
    if not texto:
        return {}

    # Tentar parse direto primeiro
    try:
        return json.loads(texto.strip())
    except json.JSONDecodeError:
        pass

    # Encontrar JSON em texto misto usando contagem de chaves
    start = texto.find('{')
    if start == -1:
        return {}

    depth = 0
    for i, char in enumerate(texto[start:], start):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        if depth == 0:
            try:
                return json.loads(texto[start:i+1])
            except json.JSONDecodeError:
                return {}

    return {}
```

---

### 2.2 Decorators de RBAC Nao Funcionais

**Severidade:** 🔴 Alta
**Arquivo:** `permissions.py:18-47`
**Linha:** 39

```python
# Pattern incompativel com FastAPI
def wrapper(*args, user: AuthUser = Depends(get_current_user), **kwargs):
    # FastAPI nao consegue injetar Depends() em funcao com *args
```

**Problema:** FastAPI nao consegue resolver `Depends()` quando a funcao usa `*args`.

**Impacto:** Os decorators `@require_admin`, `@require_user`, `@require_any` **nao protegem as rotas**.

**Mitigacao Atual:** As rotas usam `Depends(get_current_user)` diretamente, mas a verificacao de role nao ocorre.

**Solucao Recomendada:**

```python
from functools import wraps
from fastapi import Depends, HTTPException

def require_role(*allowed_roles: str):
    """
    Cria uma dependencia que valida o role do usuario.

    Uso:
        @app.delete("/users/{id}")
        def delete_user(user: AuthUser = Depends(require_role("admin"))):
            ...
    """
    async def role_checker(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado. Role '{user.role}' nao autorizado. "
                       f"Roles permitidos: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker

# Aliases para conveniencia
require_admin = require_role("admin")
require_user = require_role("user")
require_any = require_role("admin", "user")
```

---

### 2.3 Issue Conhecida: Segmentacao com Modelos

**Severidade:** 🟡 Media
**Arquivo:** `background_remover.py`
**Status:** Documentado, sem solucao implementada

**Problema:** O rembg inclui pessoas/modelos na segmentacao quando presentes na imagem.

**Impacto:** Fotos lifestyle (produto + modelo) ficam distorcidas ao compor em 1080x1080.

**Possiveis Solucoes:**
1. Usar Gemini Vision para detectar bounding box do produto antes do rembg
2. Adicionar crop automatico baseado em deteccao de objeto
3. Validar aspect ratio e rejeitar imagens com proporcoes invalidas
4. Oferecer opcao manual de crop na API

---

## 3. Seguranca

### 3.1 Implementado Corretamente

| Aspecto | Status | Localizacao |
|---------|--------|-------------|
| JWT Validation (HS256) | ✅ | `auth/supabase.py:68-120` |
| Audience Claim Check | ✅ | `auth/supabase.py:85` |
| Expiration Validation | ✅ | `auth/supabase.py:86` |
| RLS no Supabase | ✅ | `SQL para o SUPABASE/*.sql` |
| WWW-Authenticate Header | ✅ | `auth/supabase.py:112` |
| Magic Number Validation | ✅ | `utils.py:100-140` |
| Pillow Integrity Check | ✅ | `utils.py:180-200` |

### 3.2 Ausente ou Incompleto

| Aspecto | Status | Risco | Recomendacao |
|---------|--------|-------|--------------|
| Rate Limiting | ❌ Ausente | Alto | Implementar com slowapi ou Redis |
| Token Revocation | ❌ Ausente | Medio | Blacklist para tokens comprometidos |
| CORS Configuravel | ⚠️ Hardcoded | Baixo | Mover para env vars |
| Input Sanitization | ⚠️ Basico | Medio | Validacao mais rigorosa |
| Request Size Limit | ⚠️ Default | Medio | Configurar limite explicito |

### 3.3 Observacao sobre Dev Mode

```python
# auth/supabase.py
DEV_USER_ID = "00000000-0000-0000-0000-000000000000"

# Dev mode retorna role="admin" - TODOS tem acesso admin
if not Settings.AUTH_ENABLED:
    return AuthUser(
        user_id=DEV_USER_ID,
        email="dev@frida.com",
        role="admin",  # ← Risco se ativado em producao
        name="Dev User"
    )
```

**Risco:** Se `AUTH_ENABLED=false` acidentalmente em producao, todos os requests terao acesso admin.

**Recomendacao:** Adicionar warning em logs quando dev mode esta ativo:

```python
if not Settings.AUTH_ENABLED:
    logger.warning("⚠️ AUTH DESABILITADO - Modo desenvolvimento ativo!")
```

---

## 4. Qualidade de Codigo

### 4.1 Metricas

| Arquivo | Linhas | Funcao | Mudanca |
|---------|--------|--------|---------|
| main.py | ~720 | Rotas e orquestracao | +2 endpoints |
| supabase.py | 251 | Autenticacao JWT + AuthUser | Enhanced |
| database.py | ~280 | Acesso a dados + CRUD produtos | +3 funcoes |
| utils.py | 241 | Utilitarios e validacao | - |
| tech_sheet.py | 219 | Extracao + renderizacao | - |
| classifier.py | 183 | Classificacao Gemini | - |
| storage.py | ~260 | Supabase storage | Enhanced |
| background_remover.py | 112 | Processamento de imagem | - |
| permissions.py | 54 | RBAC (com bugs) | - |
| config.py | 54 | Configuracao | - |
| **Total Python** | **~2,500** | | +200 linhas |

### 4.2 Novos Endpoints (v0.5.1)

#### GET /products
Lista todos os produtos do usuario autenticado.

```python
@app.get("/products")
def list_products(user: AuthUser = Depends(get_current_user)):
    products = get_user_products(user.user_id)
    return {"status": "sucesso", "total": len(products), "products": products}
```

**Response:**
```json
{
  "status": "sucesso",
  "total": 5,
  "products": [
    {"id": "uuid", "name": "Bolsa Premium", "category": "bolsa", "status": "draft", ...}
  ],
  "user_id": "uuid"
}
```

#### GET /products/{product_id}
Retorna detalhes de um produto especifico.

```python
@app.get("/products/{product_id}")
def get_product(product_id: str, user: AuthUser = Depends(get_current_user)):
    # Validacao de ownership: usuario deve ser criador ou admin
    ...
```

**Validacao de Acesso:**
- Usuario comum: apenas seus proprios produtos
- Admin: acesso a todos os produtos

### 4.3 Novas Funcoes de Database (v0.5.1)

| Funcao | Descricao | Tabela |
|--------|-----------|--------|
| `create_product(name, category, classification, user_id)` | Cria produto no banco | products |
| `get_user_products(user_id)` | Lista produtos do usuario | products |
| `create_image(product_id, type, bucket, path, user_id)` | Registra imagem | images |

**Integracao com /process:**
O endpoint `/process` agora cria automaticamente um registro na tabela `products` apos classificacao bem-sucedida.

### 4.4 Boas Praticas Observadas

1. **Type Hints** - Uso consistente de TypedDict e tipos
2. **Docstrings** - Funcoes principais documentadas
3. **Error Handling** - Try/except abrangente com logging
4. **Logging** - Logs em pontos-chave do fluxo
5. **Singleton Pattern** - Cliente Supabase reutilizado
6. **Ownership Validation** - Novos endpoints validam propriedade do recurso
7. **Workflow Status** - Produtos com lifecycle (draft → pending → approved → rejected → published)

### 4.5 Melhorias Sugeridas

#### config.py - validate() nunca chamado

```python
# Linha 49 - metodo existe mas nao e usado
@classmethod
def validate(cls):
    """Valida configuracoes criticas."""
    if not cls.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY nao configurada")
```

**Recomendacao:** Chamar `Settings.validate()` no startup ou remover metodo morto.

#### Constantes Hardcoded

```python
# Atual - espalhado pelo codigo
output_size = (1080, 1080)
background_color = (255, 255, 255)

# Sugerido - centralizar em config.py
class Settings:
    # Image Processing
    OUTPUT_SIZE = (1080, 1080)
    BACKGROUND_COLOR = "#FFFFFF"
    MAX_FILE_SIZE_MB = 10
```

---

## 5. Testes

### 5.1 Status Atual: 64% (16/25)

| Categoria | Testes | Status | Cobertura |
|-----------|--------|--------|-----------|
| 1. Health & Connectivity | 3/3 | ✅ | 100% |
| 2. Auth Dev Mode | 2/2 | ✅ | 100% |
| 3. Classification | 3/3 | ✅ | 100% |
| 4. Processing | 4/4 | ✅ | 100% |
| 5. Security/Validation | 4/4 | ✅ | 100% |
| 6. Storage (Supabase) | 0/3 | ⏳ | 0% |
| 7. Edge Cases | 0/5 | ⏳ | 0% |
| 8. Config/Startup | 0/2 | ⏳ | 0% |

### 5.2 Testes Pendentes

#### Categoria 6: Storage
- Upload para bucket Supabase
- Audit trail em `historico_geracoes`
- Geracao de URL publica

**Requisito:** Configurar `SUPABASE_URL` e `SUPABASE_KEY`

#### Categoria 7: Edge Cases
- Arquivo maior que limite (>10MB)
- Requests concorrentes
- Content-Type invalido
- Arquivo corrompido
- Timeout de API externa

#### Categoria 8: Startup
- Inicializacao sem GEMINI_API_KEY
- Configuracao invalida de Supabase

### 5.3 Recomendacoes

1. **Criar ambiente de teste Supabase** para Cat. 6
2. **Implementar testes de carga** com locust ou k6
3. **Adicionar pytest-cov** para metricas de cobertura
4. **CI/CD pipeline** com GitHub Actions

---

## 6. Database Schema

### 6.1 Estrutura Completa (v0.5.1)

```
users (id, email, name, role, created_at)
  │
  ├── products (id, name, sku, category, classification_result, status, created_by, created_at, updated_at)
  │     │
  │     └── images (id, product_id, type, storage_bucket, storage_path, quality_score, created_by, created_at)
  │
  └── historico_geracoes (audit trail - storage service)
```

### 6.2 Tabela Products (NOVA em v0.5.1)

**Arquivo:** `SQL para o SUPABASE/04_create_products.sql`

```sql
CREATE TABLE public.products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sku TEXT UNIQUE,
  category TEXT,
  classification_result JSONB,  -- Resultado do Gemini
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'published')),
  created_by UUID REFERENCES public.users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Workflow de Status:**
```
draft → pending → approved → published
                ↘ rejected
```

**Indices:**
- `idx_products_created_by` - Busca por usuario
- `idx_products_status` - Filtro por status
- `idx_products_category` - Filtro por categoria
- `idx_products_sku` - Busca por SKU

### 6.3 Tabela Images (NOVA em v0.5.1)

**Arquivo:** `SQL para o SUPABASE/05_create_images.sql`

```sql
CREATE TABLE public.images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
  type TEXT CHECK (type IN ('original', 'segmented', 'processed')) NOT NULL,
  storage_bucket TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  quality_score INTEGER CHECK (quality_score >= 0 AND quality_score <= 100),
  created_by UUID REFERENCES public.users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Tipos de Imagem:**
| Tipo | Descricao |
|------|-----------|
| `original` | Imagem enviada pelo usuario |
| `segmented` | Imagem apos rembg (fundo removido) |
| `processed` | Imagem final (fundo branco, 1080x1080) |

### 6.4 Boas Praticas Implementadas

| Aspecto | Status | Observacao |
|---------|--------|------------|
| UUIDs como primary keys | ✅ | gen_random_uuid() |
| RLS policies | ✅ | Usuarios veem apenas seus dados |
| Indices em campos de busca | ✅ | 4 indices em products, 3 em images |
| Trigger de auto-update | ✅ | updated_at em products |
| ON DELETE CASCADE | ✅ | Images deletadas com produto |
| CHECK constraints | ✅ | status, type, quality_score |
| JSONB para dados flexiveis | ✅ | classification_result |

### 6.5 Sugestoes de Melhoria

#### Indice Composto para Queries Frequentes

```sql
-- Otimizar busca de produtos por usuario e status
CREATE INDEX idx_products_user_status
ON products(created_by, status);

-- Otimizar busca de imagens por tipo
CREATE INDEX idx_images_product_type
ON images(product_id, type);
```

#### Soft Delete

```sql
-- Permitir recuperacao de produtos deletados
ALTER TABLE products ADD COLUMN deleted_at TIMESTAMPTZ;

-- Atualizar RLS para ignorar deletados
CREATE POLICY "Ignore deleted" ON products
FOR SELECT USING (deleted_at IS NULL);
```

#### Full-Text Search (Futuro)

```sql
-- Busca em nome e descricao de produtos
ALTER TABLE products ADD COLUMN search_vector tsvector;
CREATE INDEX idx_products_search ON products USING GIN(search_vector);
```

---

## 7. Documentacao

### 7.1 Excelente Cobertura

| Arquivo | Linhas | Conteudo |
|---------|--------|----------|
| CLAUDE.md | ~500 | Arquitetura, endpoints, contratos |
| FASE_DE_TESTES.md | ~200 | Protocolos de teste |
| GEMINI.md | ~100 | Contexto para IA |
| README.md | ~50 | Quick start |

### 7.2 Faltando

- [ ] Guia de deploy (Docker, cloud providers)
- [ ] Diagrama de arquitetura visual
- [ ] API changelog / versioning
- [ ] Guia de contribuicao
- [ ] Troubleshooting guide

---

## 8. Performance

### 8.1 Pontos de Atencao

| Operacao | Tempo | Observacao |
|----------|-------|------------|
| rembg processing | 2-3s | Sem cache, reprocessa cada request |
| U2NET model load | ~170MB | Download na primeira execucao |
| Gemini API | 0.5-2s | Sem rate limiting |
| Supabase queries | <100ms | Sync (poderia ser async) |

### 8.2 Otimizacoes Recomendadas

#### Pre-carregar Modelo rembg no Docker

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Instalar dependencias
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-carregar modelo U2NET (~170MB)
RUN python -c "from rembg import remove; import io; remove(io.BytesIO(b''))"

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/classify")
@limiter.limit("10/minute")
def classify_image(...):
    ...

@app.post("/process")
@limiter.limit("5/minute")
def process_image(...):
    ...
```

#### Cache de Classificacao

```python
import hashlib
from functools import lru_cache

def get_image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

# Cache baseado em hash da imagem
@lru_cache(maxsize=100)
def classify_cached(image_hash: str, image_bytes: bytes):
    return classifier.classify(image_bytes)
```

---

## 9. Acoes Prioritarias

### 9.1 Alta Prioridade (Antes de Producao)

| # | Acao | Arquivo | Esforco |
|---|------|---------|---------|
| 1 | Corrigir bug de JSON parsing | `utils.py:66` | 30 min |
| 2 | Corrigir/remover decorators RBAC | `permissions.py` | 1 hora |
| 3 | Implementar rate limiting | `main.py` | 2 horas |
| 4 | Completar testes Storage (Cat. 6) | `tests/` | 3 horas |

### 9.2 Media Prioridade

| # | Acao | Arquivo | Esforco |
|---|------|---------|---------|
| 5 | Criar Enums para categorias | `config.py` | 1 hora |
| 6 | Tornar CORS configuravel | `main.py`, `.env` | 30 min |
| 7 | Completar testes Edge Cases | `tests/` | 4 horas |
| 8 | Customizar campos ficha tecnica | `tech_sheet.py` | 2 horas |

### 9.3 Baixa Prioridade

| # | Acao | Arquivo | Esforco |
|---|------|---------|---------|
| 9 | Migrar DB calls para async | `database.py` | 4 horas |
| 10 | Adicionar Sentry | `main.py` | 1 hora |
| 11 | Cache de classificacao | `classifier.py` | 2 horas |
| 12 | Documentacao de deploy | `DEPLOY.md` | 3 horas |

---

## 10. Conclusao

O **Frida Orchestrator** demonstra engenharia solida com arquitetura bem planejada e separacao de responsabilidades clara. O codigo e legivel, bem documentado e segue boas praticas de desenvolvimento Python.

### Evolucao desde v0.5.0

A versao 0.5.1 trouxe melhorias significativas:

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Gestao de Produtos | Apenas processamento | CRUD completo com lifecycle |
| Rastreamento de Imagens | Nenhum | Tabela dedicada com tipos |
| Autenticacao | user_id apenas | AuthUser completo com role |
| Integracao DB | Basica | Produtos criados automaticamente |

### Principais Riscos (Ainda Presentes)

1. **Bug de JSON parsing** - Pode corromper dados de ficha tecnica com objetos aninhados
   - **Status:** ❌ NAO CORRIGIDO em `utils.py:62`

2. **RBAC nao funcional** - Decorators nao protegem rotas conforme esperado
   - **Status:** ❌ NAO CORRIGIDO em `permissions.py:39`

3. **Sem rate limiting** - Vulneravel a abuso e custos excessivos de API
   - **Status:** ❌ NAO IMPLEMENTADO

### Veredicto

O projeto evoluiu bem com a adicao de gestao de produtos e integracao mais profunda com o banco de dados. **Porem, os dois bugs criticos identificados na revisao anterior ainda nao foram corrigidos** e devem ser priorizados antes do deploy em producao.

Com as correcoes dos itens de alta prioridade, o projeto estara pronto para producao. A qualidade do codigo e documentacao continua acima da media.

---

**Score Final: 7.8/10** (↑0.3 desde v0.5.0)

| Categoria | Nota | Mudanca |
|-----------|------|---------|
| Arquitetura | 9/10 | - |
| Codigo | 7.5/10 | ↑0.5 (novos endpoints bem estruturados) |
| Seguranca | 6/10 | - (bugs ainda presentes) |
| Testes | 6/10 | - |
| Documentacao | 9/10 | - |
| Performance | 7/10 | - |
| **Database** | **9/10** | **NOVO** (schema bem desenhado) |

---

## 11. Proximos Passos Recomendados

### Imediato (Bloqueadores de Producao)

1. ⚠️ **Corrigir `safe_json_parse()`** em `utils.py:62`
2. ⚠️ **Refatorar RBAC decorators** em `permissions.py` ou remover codigo morto
3. ⚠️ **Adicionar rate limiting** com slowapi

### Curto Prazo

4. Completar testes de Storage (Categoria 6)
5. Adicionar testes para novos endpoints `/products`
6. Implementar endpoint DELETE `/products/{id}`

### Medio Prazo

7. Adicionar paginacao em `GET /products`
8. Implementar busca/filtro de produtos
9. Dashboard de metricas

---

*Revisao gerada por Claude Code (Opus 4.5)*
*Primeira revisao: 2026-01-12*
*Atualizacao: 2026-01-13 (v0.5.1)*
