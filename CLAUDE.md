# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Version:** 0.5.3
**Last Updated:** 2026-01-13
**Testing Status:** 64% Complete (16/25 tests passing)
**Production Ready:** Core features ✓ | Edge cases & Load testing pending
**Development Progress:** 65% (Micro-PRD 03 Complete)
**Code Review Score:** 9.2/10 (see CODE_REVIEW.md)

## Project Overview

Frida Orchestrator is a FastAPI backend for fashion product image processing (bags, lunchboxes, thermos). It provides:
- AI-powered product classification via Google Gemini 2.0 Flash Lite
- Background removal via rembg (U2NET model) with white background composition
- Technical specification generation with premium HTML templates
- Multi-format image support (JPEG, PNG, WebP)
- Deep security validation (magic numbers + Pillow integrity checks)
- Supabase integration for storage, database, and audit trail
- JWT authentication (Supabase Auth) with dev mode
- **NEW:** Role-Based Access Control (RBAC) with `admin` and `user` roles
- **NEW:** Database-backed user management via Supabase PostgreSQL
- **NEW:** Product catalog with workflow management (draft→pending→approved→rejected→published)
- **NEW:** Product and image tracking with full CRUD endpoints
- **NEW:** CORS configuration for Next.js frontend integration
- **NEW:** Image Pipeline with triple storage (original, segmented, processed)
- **NEW:** Quality validation system (Husk Layer) with 0-100 scoring
- **NEW:** Advanced image composition with shadow and centering

## Project Structure

```
componentes/
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── supabase.py              # JWT validation + AuthUser model
│   │   └── permissions.py           # RBAC dependency factories (require_admin, require_role)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py            # Gemini Vision + Structured Output
│   │   ├── background_remover.py    # rembg + Pillow composition (legacy)
│   │   ├── tech_sheet.py            # Jinja2 template rendering
│   │   ├── storage.py               # Supabase storage + audit trail
│   │   ├── image_composer.py        # Advanced composition with shadow (NEW)
│   │   ├── husk_layer.py            # Quality validation 0-100 (NEW)
│   │   └── image_pipeline.py        # Pipeline orchestration (NEW)
│   ├── templates/
│   │   └── tech_sheet_premium.html  # Premium tech sheet (Outfit font)
│   ├── main.py                      # FastAPI app + routes
│   ├── config.py                    # Settings management
│   ├── database.py                  # Supabase users table queries
│   ├── utils.py                     # Validation + image utilities
│   └── __init__.py
├── SQL para o SUPABASE/             # Database migration scripts
│   ├── 01_create_users_table.sql   # Users table + RLS policies
│   ├── 02_seed_admin_zero.sql      # Initial admin user
│   ├── 03_seed_team_members.sql    # Team members seed data
│   ├── 04_create_products.sql      # Products table + workflow
│   ├── 05_create_images.sql        # Images table + tracking
│   └── 06_rls_dual_mode.sql        # RLS policies dual mode (NEW)
├── scripts/                         # Utility scripts (NEW)
│   ├── test_pipeline.py            # Local pipeline testing
│   └── test_prd03_complete.py      # Complete PRD 03 test suite (61 tests)
├── test_images/                     # Test images for pipeline validation
│   ├── bolsa_teste.png             # Test input image
│   ├── bolsa_teste_segmented.png   # Segmented output
│   └── bolsa_teste_processed.png   # Processed output (1200x1200)
├── venv/                            # Python 3.12 virtual environment
├── .env                             # Environment variables (secrets)
├── .env.example                     # Template for .env
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
├── CLAUDE.md                        # This file
├── GEMINI.md                        # AI model context
├── FASE_DE_TESTES.md               # Testing protocols v0.5.0
├── CODE_REVIEW.md                   # Code review analysis (score: 9.2/10)
└── .gitignore
```

## Development Commands

```bash
# Setup (one-time)
cd componentes
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add GEMINI_API_KEY

# Run development server
uvicorn app.main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify -F "file=@image.jpg"
curl -X POST http://localhost:8000/process -F "file=@image.jpg" -F "gerar_ficha=true"
curl -X POST http://localhost:8000/remove-background -F "file=@image.jpg"
```

## Architecture

### Service Layer Pattern

All business logic lives in `app/services/`. The `main.py` handles HTTP routing and delegates to services:

- **ClassifierService** (`classifier.py`): Uses Gemini Structured Output for product classification. Returns `ClassificationResult` TypedDict with `item` (bolsa|lancheira|garrafa_termica|desconhecido), `estilo` (sketch|foto|desconhecido), `confianca` (0.0-1.0) fields.

- **BackgroundRemoverService** (`background_remover.py`): rembg (U2NET model) for background removal + Pillow for white background (#FFFFFF) composition + resizing to 1080x1080px.

- **TechSheetService** (`tech_sheet.py`): Gemini for structured data extraction + Jinja2 for HTML rendering with premium template (Outfit font, minimalist layout).

- **StorageService** (`storage.py`): Optional Supabase integration for audit trail. Uploads processed images to `processed-images` bucket with namespace `{user_id}/{product_id}/{timestamp}.png`. Logs metadata to `historico_geracoes` table.

- **Database Module** (`database.py`): Supabase client wrapper for database operations. Creates new client per call (no singleton/cache) to ensure fresh API key usage.
  - **User queries:** `get_user_by_id()`, `get_user_by_email()`
  - **Product CRUD:** `create_product()`, `get_user_products()`
  - **Image CRUD:** `create_image()`

- **Auth Service** (`auth/supabase.py`): JWT validation via PyJWT + user lookup in `users` table. Returns `AuthUser` model with `user_id`, `email`, `role`, and `name`. Supports dev mode with fake user. Enforces that authenticated users must exist in the `users` table (HTTP 403 if not found).

- **Permissions Module** (`auth/permissions.py`): RBAC (Role-Based Access Control) via FastAPI Dependency Factories. Provides `require_admin`, `require_user`, `require_any`, and `require_role(*roles)` as dependencies. Use with `Depends()` for route protection.

- **ImageComposer** (`services/image_composer.py`): NEW in v0.5.3. Advanced image composition with:
  - White background (#FFFFFF)
  - Product centered at 85% coverage
  - Soft drop shadow (opacity 40, blur 15)
  - Output 1200x1200px minimum
  - LANCZOS resampling for quality

- **HuskLayer** (`services/husk_layer.py`): NEW in v0.5.3. Quality validation system scoring 0-100:
  - Resolution check (30 pts): ≥1200px minimum dimension
  - Centering check (40 pts): ±15% tolerance, 75-95% coverage
  - Background purity (30 pts): RGB delta <5 from pure white
  - Pass threshold: score ≥80

- **ImagePipelineSync** (`services/image_pipeline.py`): NEW in v0.5.3. Orchestrates the complete pipeline:
  - Stage 1: Upload original → bucket 'raw' → type='original'
  - Stage 2: Segmentation (rembg) → bucket 'segmented' → type='segmented'
  - Stage 3: Composition → bucket 'processed-images' → type='processed'
  - Stage 4: Quality validation → quality_score in response

### Processing Pipeline

**`/process` endpoint (main pipeline) - Updated v0.5.3:**
1. **Validation Layer 1:** Content-Type header check (fast, vulnerable to spoofing)
2. **Validation Layer 2:** Magic numbers check (file signatures)
3. **Validation Layer 3:** Pillow integrity check (detects corruption)
4. **Classification:** Gemini 2.0 Flash Lite with Structured Output (guaranteed JSON)
5. **Database Insert:** Save product to `products` table with classification result
6. **Image Pipeline (NEW v0.5.3):**
   - Upload original to 'raw' bucket
   - Segmentation via rembg U2NET model → save to 'segmented' bucket
   - Composition via ImageComposer (1200x1200, centered, shadow) → save to 'processed-images' bucket
   - Quality validation via HuskLayer (0-100 score)
   - Save all 3 image records to `images` table
7. **Tech Sheet (optional):** Gemini data extraction + Jinja2 HTML rendering
8. **Audit (optional):** Log to `historico_geracoes` table
9. **Response:** Base64/URL + metadata + product_id + quality_score

### Key Design Decisions

**Sync Routes for CPU-bound Tasks**: Processing routes (`/process`, `/classify`, `/remove-background`) use `def` instead of `async def` intentionally. FastAPI runs sync functions in a thread pool, preventing event loop blocking during heavy image operations (rembg uses ~2-3s per image).

**Fail-Fast Startup**: The server won't start if `GEMINI_API_KEY` is missing or if critical services fail to initialize. This catches configuration errors at deploy time instead of runtime.

**Gemini Structured Output**: The classifier uses `response_mime_type="application/json"` with `response_schema` to guarantee valid JSON responses without regex parsing. Temperature is set to 0.1 for consistency.

**Multi-layer Image Validation**: Three layers of validation protect against malicious files:
1. Content-Type (fast filter)
2. Magic numbers (file signatures)
3. Pillow integrity (structural validation)

**CORS Middleware**: Configured for Next.js frontend integration:
- Allowed origins: `http://localhost:3000`, `http://127.0.0.1:3000`, `https://*.vercel.app`
- Credentials: Enabled for JWT cookie support
- Methods: All HTTP methods allowed
- Headers: All headers allowed

## Configuration

Environment variables are managed in `config.py` via `python-dotenv`:

### Required (Fail-Fast)
- `GEMINI_API_KEY`: Google Gemini API key (server won't start without this)

### Optional - Supabase
- `SUPABASE_URL`: Supabase project URL (required for database + storage)
- `SUPABASE_KEY`: Supabase anon/service key (required for database + storage)
- `SUPABASE_BUCKET`: Storage bucket name (default: `processed-images`)
- `SUPABASE_JWT_SECRET`: JWT secret for authentication (required if AUTH_ENABLED=true)

**Note:** If `AUTH_ENABLED=true`, then `SUPABASE_URL` and `SUPABASE_KEY` are also required for querying the `users` table.

### Optional - Authentication
- `AUTH_ENABLED`: Enable JWT authentication (default: `false`)

### Optional - Server
- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)
- `DEBUG`: Enable debug/reload mode (default: `true`)

### Hardcoded Values

**Gemini Models (configured in code):**
- `GEMINI_MODEL_CLASSIFIER`: `gemini-2.0-flash-lite` (classification)
- `GEMINI_MODEL_TECH_SHEET`: `gemini-2.0-flash-lite` (tech sheet generation)
- `GEMINI_MODEL_IMAGE_GEN`: `gemini-2.0-flash-exp` (image generation - experimental, not used)

**Image Processing:**
- Output size: 1080x1080px
- Background color: #FFFFFF (pure white)

**Product Enums (NEW in v0.5.1):**
Centralized in `config.py` for type safety and consistency:
- `ProductCategory`: bolsa, lancheira, garrafa_termica, desconhecido
- `ProductStyle`: sketch, foto, desconhecido
- `ProductStatus`: draft, pending, approved, rejected, published
- `ImageType`: original, segmented, processed

**Storage & Database:**
- Bucket name: `processed-images`
- Audit table: `historico_geracoes` (image processing history - legacy)
- Users table: `users` (authentication + RBAC)
- Products table: `products` (product catalog with workflow)
- Images table: `images` (image tracking linked to products)

## Endpoints

### Public Endpoints (no authentication required)

**`GET /`**
- HTML homepage with links to documentation
- Returns: HTML page with project info

**`GET /public/ping`**
- Simple connectivity test
- Returns: `{status: "pong", service: "Frida Orchestrator", version: "0.5.0", auth_required: bool}`

**`GET /health`**
- Detailed health check for all services
- Returns: `{status, version, ready, services, configuration, warnings}`
- Always returns 200 OK (even in degraded mode)

**`GET /docs`**
- Swagger UI interactive documentation

### Protected Endpoints (authentication if AUTH_ENABLED=true)

**`POST /classify`**
- Classifies product image without processing
- **Form Data:**
  - `file` (required): Image file (JPEG/PNG/WebP)
- **Response:**
  ```json
  {
    "status": "sucesso",
    "classificacao": {
      "item": "bolsa|lancheira|garrafa_termica|desconhecido",
      "estilo": "sketch|foto|desconhecido",
      "confianca": 0.95
    },
    "user_id": "uuid"
  }
  ```
- **Validations:** Magic numbers + Pillow integrity
- **Status Codes:** 200 OK, 400 Bad Request, 422 Validation Error, 503 Service Unavailable

**`POST /remove-background`**
- Removes background and applies white (#FFFFFF)
- **Form Data:**
  - `file` (required): Image file
- **Response:**
  ```json
  {
    "status": "sucesso",
    "imagem_base64": "iVBORw0KGgo...",
    "user_id": "uuid"
  }
  ```
- **Processing:** rembg → white background → resize 1080x1080px → base64
- **Status Codes:** 200 OK, 400 Bad Request, 503 Service Unavailable

**`POST /process`** ⭐ Main endpoint
- Complete pipeline: classification + background removal + database storage + optional tech sheet
- **Form Data:**
  - `file` (required): Product image
  - `gerar_ficha` (optional): boolean, default=false
  - `product_id` (optional): string for storage organization (legacy parameter, unused)
- **Response (Updated v0.5.3):**
  ```json
  {
    "status": "sucesso",
    "product_id": "uuid-of-created-product",
    "categoria": "bolsa",
    "estilo": "foto",
    "confianca": 0.95,
    "imagem_base64": "iVBORw0KGgo..." or "storage:https://...",
    "ficha_tecnica": {
      "dados": {...},
      "html": "<html>...</html>"
    },
    "images": {
      "original": {"id": "uuid", "bucket": "raw", "path": "...", "url": "..."},
      "segmented": {"id": "uuid", "bucket": "segmented", "path": "...", "url": "..."},
      "processed": {"id": "uuid", "bucket": "processed-images", "path": "...", "url": "...", "quality_score": 95}
    },
    "quality_score": 95,
    "quality_passed": true,
    "mensagem": "Imagem processada com sucesso! user_id=xxx"
  }
  ```
- **Database Actions:**
  - Creates product record in `products` table with classification result
  - Creates 3 image records in `images` table (original, segmented, processed)
  - Returns `product_id` and `quality_score` for frontend reference
- **Storage:** If Supabase configured, saves to `{user_id}/{product_id}/{timestamp}.png`
- **Audit:** Logs to `historico_geracoes` with metadata (legacy)
- **Status Codes:** 200 OK, 400 Bad Request, 422 Validation Error, 500 Server Error

**`GET /auth/test`**
- Tests authentication
- **Dev Mode Response:**
  ```json
  {
    "status": "authenticated",
    "user_id": "00000000-0000-0000-0000-000000000000",
    "email": "dev@frida.com",
    "role": "admin",
    "name": "Dev User",
    "message": "Token JWT válido! Usuário cadastrado no sistema."
  }
  ```
- **Prod Mode Response:** Same structure but with real data from JWT + users table
- **Status Codes:** 200 OK, 401 Unauthorized (prod mode only), 403 Forbidden (user not in database)

### Product Management Endpoints (NEW in v0.5.0)

**`GET /products`**
- Lists all products for authenticated user
- **Response:**
  ```json
  {
    "status": "sucesso",
    "total": 10,
    "products": [
      {
        "id": "uuid",
        "name": "Bolsa - image.jpg",
        "sku": null,
        "category": "bolsa",
        "classification_result": {"item": "bolsa", "estilo": "foto", "confianca": 0.95},
        "status": "draft",
        "created_by": "user_uuid",
        "created_at": "2026-01-12T10:00:00Z",
        "updated_at": "2026-01-12T10:00:00Z"
      }
    ],
    "user_id": "user_uuid"
  }
  ```
- **Ordering:** Sorted by `created_at DESC` (newest first)
- **Status Codes:** 200 OK, 401 Unauthorized, 500 Server Error

**`GET /products/{product_id}`**
- Gets detailed information for a specific product
- **Path Parameter:**
  - `product_id` (required): UUID of the product
- **Response:**
  ```json
  {
    "status": "sucesso",
    "product": {
      "id": "uuid",
      "name": "Bolsa Premium",
      "sku": "BAG-001",
      "category": "bolsa",
      "classification_result": {...},
      "status": "approved",
      "created_by": "user_uuid",
      "created_at": "2026-01-12T10:00:00Z",
      "updated_at": "2026-01-12T10:00:00Z"
    }
  }
  ```
- **Access Control:**
  - Users can only access their own products
  - Admins can access all products
- **Status Codes:** 200 OK, 401 Unauthorized, 403 Forbidden, 404 Not Found, 500 Server Error

## Type Contracts

Services use TypedDict and Pydantic models for data contracts:

```python
# Authentication (Pydantic)
AuthUser = BaseModel:
    user_id: str                    # UUID from JWT
    email: str                       # From users table
    role: Literal["admin", "user"]  # From users table
    name: Optional[str]             # From users table

# Classification (TypedDict)
ClassificationResult = {
    "item": str,         # bolsa|lancheira|garrafa_termica|desconhecido
    "estilo": str,       # sketch|foto|desconhecido
    "confianca": float   # 0.0-1.0
}

# Tech Sheet (TypedDict)
TechSheetData = {
    "nome": str,
    "categoria": str,
    "descricao": str,
    "materiais": list[str],
    "cores": list[str],
    "dimensoes": {
        "altura": str,
        "largura": str,
        "profundidade": str
    },
    "detalhes": list[str]
}

# Storage (TypedDict)
StorageResult = {
    "success": bool,
    "image_url": str | None,
    "record_id": str | None,
    "error": str | None
}
```

## Testing Status (FASE_DE_TESTES.md)

**Overall Progress:** 16/25 tests (64% complete)

### ✅ Completed Test Categories

- **Category 1:** Health & Connectivity (3/3 tests) ✓
- **Category 2:** Authentication Dev Mode (2/2 tests) ✓
- **Category 3:** Image Classification (3/3 tests) ✓
- **Category 4:** Complete Processing (4/4 tests) ✓
- **Category 5:** Image Validation & Security (4/4 tests) ✓

### ⏳ Pending Test Categories

- **Category 6:** Storage (Supabase) (0/3 tests) - Requires Supabase configuration
- **Category 7:** Errors & Edge Cases (0/5 tests) - File size limits, concurrent requests
- **Category 8:** Configuration & Startup (0/2 tests) - Missing API key scenarios

## Micro-PRD 03 Test Suite (NEW v0.5.3)

**Test Date:** 2026-01-13
**Test Script:** `scripts/test_prd03_complete.py`
**Result:** ✅ 61/61 tests passing (100%)

### Test Categories & Results

| Category | Tests | Result |
|----------|-------|--------|
| ImageComposer - Composição de Fundo Branco | 12/12 | ✅ 100% |
| HuskLayer - Validação de Qualidade | 13/13 | ✅ 100% |
| ImagePipeline - Estruturas e Configurações | 12/12 | ✅ 100% |
| Config - Proteção DoS | 6/6 | ✅ 100% |
| Edge Cases - Casos Extremos | 8/8 | ✅ 100% |
| Integração - Fluxo Compositor → Validador | 7/7 | ✅ 100% |
| Integração - rembg (Segmentação) | 3/3 | ✅ 100% |
| **TOTAL** | **61/61** | **✅ 100%** |

### ImageComposer Tests (12 tests)
```
✅ Configuração: TARGET_SIZE = 1200
✅ Configuração: PRODUCT_COVERAGE = 0.85
✅ Configuração: BACKGROUND_COLOR = (255, 255, 255)
✅ Composição básica: retorna imagem
✅ Composição básica: modo RGB
✅ Composição básica: dimensão 1200x1200
✅ Composição: cantos são branco puro
✅ compose_from_bytes: retorna bytes
✅ compose_from_bytes: PNG válido
✅ Tamanho customizado: 800x800
✅ Imagem RGB: lança ValueError
✅ Imagem transparente: retorna canvas branco
```

### HuskLayer Tests (13 tests)
```
✅ Pontuação total = 100
✅ Threshold de aprovação = 80
✅ Imagem perfeita: score >= 80
✅ Imagem perfeita: passed = True
✅ Resolução baixa: score resolução < 30
✅ Produto descentralizado: score centralização < 40
✅ Fundo impuro: score background < 30
✅ QualityReport.to_dict: contém 'score'
✅ QualityReport.to_dict: contém 'passed'
✅ QualityReport.to_dict: contém 'details'
✅ validate_from_bytes: retorna QualityReport
✅ Imagem toda branca: centralização = 0
✅ Produto muito pequeno: cobertura TOO_SMALL
```

### ImagePipeline Tests (12 tests)
```
✅ BUCKETS: contém 'original'
✅ BUCKETS: contém 'segmented'
✅ BUCKETS: contém 'processed'
✅ Bucket original = 'raw'
✅ Bucket processed = 'processed-images'
✅ PipelineResult: atributo success
✅ PipelineResult: atributo product_id
✅ PipelineResult: atributo images
✅ PipelineResult.to_dict: serializável
✅ PipelineResult.to_dict: contém success
✅ ImagePipelineSync: instanciação
✅ ImagePipelineSync: tem _client_lock
```

### DoS Protection Tests (6 tests)
```
✅ MAX_FILE_SIZE_MB configurado
✅ MAX_FILE_SIZE_MB = 10
✅ MAX_FILE_SIZE_BYTES configurado
✅ MAX_FILE_SIZE_BYTES = 10MB em bytes
✅ MAX_IMAGE_DIMENSION configurado
✅ MAX_IMAGE_DIMENSION = 8000
```

### Edge Cases Tests (8 tests)
```
✅ Bytes corrompidos: lança exceção
✅ Bytes vazios: lança exceção
✅ Imagem 1x1: não crasha
✅ Imagem 1x1: score baixo
✅ Limite de dimensão: configurado
✅ Transparência parcial: processa OK
✅ Imagem grayscale: processa OK
✅ Imagem palette: processa OK
```

### Integration Tests (10 tests)
```
✅ Fluxo: composição retorna imagem
✅ Fluxo: validação retorna report
✅ Fluxo: imagem composta passa (score >= 80)
✅ Fluxo: resolução OK (30 pts)
✅ Fluxo: fundo puro (30 pts)
✅ Fluxo bytes: funciona end-to-end
✅ Fluxo múltiplo: todas passam
✅ rembg: importação OK
✅ rembg: retorna bytes
✅ rembg: retorna PNG válido
```

### Error Cases Tests (Original Script)
```
✅ Arquivo corrompido: Exceção capturada (UnidentifiedImageError)
✅ Imagem muito pequena (1x1): Score baixo como esperado (0/100)
✅ Imagem totalmente transparente: Retornou canvas branco (1200x1200)
✅ Bytes vazios: Exceção capturada (UnidentifiedImageError)
```

### Full Pipeline Test (Real Image)
```
Imagem: test_images/bolsa_teste.png (800x600, 4KB)

Pipeline Stages:
✅ Stage 1: Segmentação (rembg) → 20,690 bytes
✅ Stage 2: Composição (ImageComposer) → 1200x1200px
✅ Stage 3: Validação (HuskLayer) → Score 100/100

Quality Report:
📐 Resolução: 30/30 pontos (OK: 1200x1200px)
🎯 Centralização: 40/40 pontos (Cobertura: 84.7%, Desvio: 0.7%)
⬜ Pureza do Fundo: 30/30 pontos (Delta: 0.0 - PURE_WHITE)

RESULTADO: ✅ PIPELINE APROVADO - Imagem pronta para produção!
```

### Test Commands
```bash
# Run all PRD 03 tests
python scripts/test_prd03_complete.py

# Run only unit tests
python scripts/test_prd03_complete.py --unit

# Run only edge cases
python scripts/test_prd03_complete.py --edge

# Run only integration tests
python scripts/test_prd03_complete.py --integration

# Run error cases (original script)
python scripts/test_pipeline.py --errors

# Run full pipeline with image
python scripts/test_pipeline.py test_images/bolsa_teste.png
```

### Test Files Created
- `scripts/test_prd03_complete.py` - Complete test suite (61 tests)
- `test_images/bolsa_teste.png` - Test image (800x600px)
- `test_images/bolsa_teste_segmented.png` - Segmented result
- `test_images/bolsa_teste_processed.png` - Processed result (1200x1200px)

## Known Limitations & TODOs

### 🔴 High Priority

**1. Rate Limiting Not Implemented** ⚠️
- **Source:** CODE_REVIEW.md - Only remaining security blocker
- **Issue:** No rate limiting on API endpoints, vulnerable to abuse and excessive API costs
- **Impact:** Gemini API calls can be spammed, causing high costs
- **Status:** ❌ NOT IMPLEMENTED
- **Recommended Solution:** Implement with `slowapi` library:
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)

  @app.post("/classify")
  @limiter.limit("10/minute")
  def classify_image(...): ...

  @app.post("/process")
  @limiter.limit("5/minute")
  def process_image(...): ...
  ```

**2. Tech Sheet Fields Require Rework**
- **Source:** FASE_DE_TESTES.md, test 4.2
- **Issue:** Current fields (`nome`, `materiais`, `cores`, `dimensoes`, `detalhes`) are generic and need customization for Carol's specific requirements.
- **Status:** Functional for validation, **will be updated**
- **Files to modify:** `app/services/tech_sheet.py`, `app/templates/tech_sheet_premium.html`

**3. Image Quality Issues with Models in Background**
- **Source:** FASE_DE_TESTES.md, test 4.4
- **Issue:** When input image contains a person/model next to the product, rembg includes both in segmentation, causing distortion in 1080x1080 composition.
- **Impact:** Works perfectly for isolated products, but fails with lifestyle photos
- **Status:** Functional, **quality needs improvement**
- **Possible solutions:**
  - Improve segmentation pipeline
  - Add automatic product cropping
  - Validate aspect ratio before resizing
  - Consider using Gemini Vision for product detection before rembg

### 🟡 Medium Priority

**4. Complete Storage Testing**
- Category 6 tests pending (Supabase integration)
- Requires: SUPABASE_URL, SUPABASE_KEY configuration
- Validates: Upload to bucket, audit trail in `historico_geracoes`

**5. Edge Cases & Load Testing**
- File size limits (>10MB)
- Concurrent request handling
- Invalid Content-Type scenarios

**6. Production Deployment Documentation**
- Deployment guide (Docker, cloud services)
- Monitoring and logging setup
- Performance optimization recommendations

### 🟢 Low Priority

**7. Model Caching Optimization**
- rembg downloads U2NET model (~170MB) on first run
- Consider pre-loading in Docker image

**8. Image Generation Feature**
- GEMINI_MODEL_IMAGE_GEN configured but not implemented
- Experimental feature for future consideration

## Gemini Schema Compatibility

⚠️ **Important:** When modifying `CLASSIFICATION_SCHEMA` in `classifier.py`, note that Gemini's schema validation differs from JSON Schema.

**Unsupported Keywords:**
- `minimum` / `maximum` (for numbers)
- `minLength` / `maxLength` (for strings)
- `pattern` (regex patterns)

**Workaround:** Use `description` to document constraints instead.

```python
# ❌ Does NOT work
"confianca": {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0
}

# ✅ Works correctly
"confianca": {
    "type": "number",
    "description": "Confidence level between 0.0 and 1.0"
}
```

**Reference:** Issue fixed in commit `fde4658` - "fix: remove unsupported validation keywords from Gemini schema"

## Authentication (AUTH_ENABLED)

**Current Status:** `AUTH_ENABLED=false` (development mode)

**Reason:** Authentication is disabled by default to simplify local development and testing. The auth module (`app/auth/`) is fully implemented but not enforced on routes by default.

### Dev Mode Behavior (AUTH_ENABLED=false)
- `get_current_user()` returns fake `AuthUser`:
  - `user_id`: `00000000-0000-0000-0000-000000000000`
  - `email`: `dev@frida.com`
  - `role`: `admin` (full access for testing)
  - `name`: `Dev User`
- No token validation is performed
- No database queries (bypasses `users` table lookup)
- All routes are accessible without Authorization header
- Useful for local development and testing

### To Enable Authentication (Production)

**Prerequisites:**
1. Run database migration scripts (see "Database Schema & RBAC" section)
2. Create at least one admin user in Supabase Auth + users table

**Configuration:**
1. Set environment variables in `.env`:
   ```bash
   AUTH_ENABLED=true
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_supabase_anon_key
   SUPABASE_JWT_SECRET=your_jwt_secret_here
   ```

2. Get credentials from Supabase Dashboard:
   - `SUPABASE_URL`: Project Settings > API > Project URL
   - `SUPABASE_KEY`: Project Settings > API > anon/public key
   - `SUPABASE_JWT_SECRET`: Project Settings > API > JWT Secret

3. Routes are protected with `Depends(get_current_user)`:
   ```python
   from app.auth.supabase import get_current_user, AuthUser

   @app.post("/process")
   def processar_produto(..., user: AuthUser = Depends(get_current_user)):
       # user is validated: JWT + users table lookup
       # Access: user.user_id, user.email, user.role, user.name
   ```

### JWT Validation Details
- **Algorithm:** HS256
- **Audience:** "authenticated"
- **Claim:** Extracts user_id from "sub"
- **Verifies:** Signature, expiration, audience
- **Errors:** Returns HTTP 401 with `WWW-Authenticate: Bearer` header

### AuthUser Model (NEW in v0.5.0)
Authentication now returns a full user object instead of just user_id:

```python
class AuthUser(BaseModel):
    user_id: str                    # UUID from JWT
    email: str                       # From users table
    role: Literal["admin", "user"]  # From users table
    name: Optional[str]             # From users table
```

**Usage in routes:**
```python
from app.auth.supabase import get_current_user, AuthUser
from app.auth.permissions import require_admin

@app.post("/process")
def processar_produto(user: AuthUser = Depends(get_current_user)):
    # Access user.user_id, user.email, user.role, user.name
    ...

@app.post("/admin-only")
@require_admin
def admin_endpoint(user: AuthUser = Depends(get_current_user)):
    # Guaranteed user.role == "admin"
    ...
```

## Database Schema & RBAC (NEW in v0.5.0)

### Database Tables

#### Users Table
The `users` table stores user information and roles for RBAC:

**Schema:**
```sql
CREATE TABLE public.users (
  id UUID PRIMARY KEY,              -- Must match Supabase Auth user ID
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT CHECK (role IN ('admin', 'user')) DEFAULT 'user' NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Indexes:**
- `idx_users_email` - Fast email lookups
- `idx_users_role` - Fast role filtering

**Row Level Security (RLS):**
- Users can view their own record
- Admins can view all records
- Policies enforced at database level

#### Products Table (NEW in v0.5.0)
The `products` table stores product information with workflow status:

**Schema:**
```sql
CREATE TABLE public.products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sku TEXT UNIQUE,                  -- Optional SKU for inventory
  category TEXT,                     -- bolsa, lancheira, garrafa_termica
  classification_result JSONB,       -- Gemini classification result
  status TEXT DEFAULT 'draft',       -- Workflow: draft→pending→approved→rejected→published
  created_by UUID REFERENCES users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL  -- Auto-updated via trigger
);
```

**Indexes:**
- `idx_products_created_by` - Filter by creator
- `idx_products_status` - Filter by workflow status
- `idx_products_category` - Filter by category
- `idx_products_sku` - Fast SKU lookups

**Workflow States:**
- `draft` - Initial state after classification
- `pending` - Submitted for review
- `approved` - Approved for production
- `rejected` - Rejected, needs rework
- `published` - Published to catalog

**Row Level Security (RLS):**
- Members (role='user'): CRUD only on own products
- Admins (role='admin'): Full access to all products

#### Images Table (NEW in v0.5.0)
The `images` table tracks all images associated with products:

**Schema:**
```sql
CREATE TABLE public.images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id) ON DELETE CASCADE NOT NULL,
  type TEXT CHECK (type IN ('original', 'segmented', 'processed')) NOT NULL,
  storage_bucket TEXT NOT NULL,      -- Supabase storage bucket name
  storage_path TEXT NOT NULL,        -- Full path in storage
  quality_score INTEGER CHECK (quality_score >= 0 AND quality_score <= 100),
  created_by UUID REFERENCES users(id) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Image Types:**
- `original` - Original uploaded image
- `segmented` - After background removal (no background)
- `processed` - Final processed image (white background, 1080x1080)

**Indexes:**
- `idx_images_product_id` - Group by product
- `idx_images_created_by` - Filter by creator
- `idx_images_type` - Filter by image type

**Row Level Security (RLS):**
- Members (role='user'): CRUD only on own images
- Admins (role='admin'): Full access to all images
- Cascade delete: When product is deleted, all images are deleted

### Migration Scripts
Located in `SQL para o SUPABASE/`, execute in order:

1. **`01_create_users_table.sql`**: Creates `users` table + indexes + RLS policies
2. **`02_seed_admin_zero.sql`**: Inserts initial admin user (requires manual UUID from Supabase Auth)
3. **`03_seed_team_members.sql`**: Seeds team members (optional)
4. **`04_create_products.sql`**: Creates `products` table + workflow + RLS policies
5. **`05_create_images.sql`**: Creates `images` table + RLS policies
6. **`06_rls_dual_mode.sql`**: RLS policies for dual mode (dev + prod) (NEW v0.5.3)

**Setup Process:**
1. Run `01_create_users_table.sql` in Supabase SQL Editor
2. Create admin user in Supabase Auth Dashboard
3. Copy the generated UUID
4. Edit `02_seed_admin_zero.sql` with the UUID and execute
5. Optionally run `03_seed_team_members.sql` for team
6. Run `04_create_products.sql` to create products table
7. Run `05_create_images.sql` to create images table

### RBAC Implementation
Role-based access control is implemented via decorators:

```python
from app.auth.permissions import require_admin, require_user, require_any

# Admin only
@app.delete("/users/{user_id}")
@require_admin
def delete_user(user_id: str, user: AuthUser = Depends(get_current_user)):
    # Only admins can access this
    ...

# Any authenticated user
@app.get("/profile")
@require_any
def get_profile(user: AuthUser = Depends(get_current_user)):
    # Any role ("admin" or "user") can access
    ...
```

**Protection Flow:**
1. Request arrives with JWT token
2. `get_current_user()` validates JWT → extracts user_id
3. Queries `users` table for user data
4. Returns `AuthUser` with role
5. `@require_admin` decorator checks if `user.role == "admin"`
6. Returns HTTP 403 if role mismatch

## Dependencies

**Core Stack:**
- `fastapi==0.115.0` - Web framework
- `uvicorn[standard]==0.30.6` - ASGI server
- `python-multipart==0.0.9` - Multipart form parsing

**AI & Image Processing:**
- `google-generativeai==0.8.0` - Gemini API
- `rembg==2.0.59` - Background removal (U2NET model, ~170MB download on first run)
- `pillow==10.4.0` - Image manipulation

**Templates & Storage:**
- `jinja2==3.1.4` - Template rendering
- `supabase==2.7.0` - Supabase client

**Authentication:**
- `PyJWT==2.8.0` - JWT token validation
- `cryptography==41.0.7` - Cryptography for JWT

**Configuration:**
- `python-dotenv==1.0.1` - Environment variables

## Git Status

**Current Branch:** `feature/database-and-permissions`

**Recent Commits:**
- `abb269f` - feat: add database scripts and permission logic
- `41e35c9` - docs: update project context and testing protocols
- `9ab6fad` - feat: implement Supabase JWT authentication module
- `fde4658` - fix: remove unsupported validation keywords from Gemini schema
- `de0d7fb` - feat: complete backend synchronization and audit storage

**Modified Files:**
- `GEMINI.md` (updated with database and RBAC context)

## Quick Reference

**Start Server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Run Tests:**
```bash
# API health check
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify -F "file=@test.jpg"

# PRD 03 Test Suite (61 tests)
python scripts/test_prd03_complete.py

# Full pipeline with image
python scripts/test_pipeline.py test_images/bolsa_teste.png

# See FASE_DE_TESTES.md for full test suite
```

**Common Issues:**

1. **Server won't start:** Check `GEMINI_API_KEY` in `.env`
2. **rembg slow on first run:** Downloading U2NET model (~170MB), normal
3. **WebP files rejected:** Use `-F "file=@image.webp;type=image/webp"` with curl
4. **Image distortion:** Input has model/person, see "Known Limitations" section
5. **Authentication errors:** Check `AUTH_ENABLED` setting in `.env`
6. **HTTP 403 "User not registered":** When `AUTH_ENABLED=true`, user must exist in `users` table. Run migration scripts and create user in Supabase Auth + users table.
7. **Database errors:** Ensure `SUPABASE_URL` and `SUPABASE_KEY` are configured when using `AUTH_ENABLED=true`

## Critical Issue Resolution: Micro-PRD 02 Blocker (RESOLVED ✅)

### Issue Summary
**Status:** ✅ RESOLVED (2026-01-13)
**Duration:** ~4 hours investigation
**Symptom:** `POST /process` returned `product_id: null` despite successful image processing

### Root Cause
**Discovered Issue:** service_role lacked GRANT permissions on tables

**Key Discovery:**
```sql
-- Verification that revealed the problem:
SELECT grantee, privilege_type
FROM information_schema.table_privileges
WHERE table_name = 'products' AND grantee = 'service_role';
-- Result: EMPTY (no grants!)

-- However:
SELECT rolname, rolbypassrls
FROM pg_roles WHERE rolname = 'service_role';
-- rolbypassrls = true

-- Critical Insight: bypassrls ≠ bypass GRANT
-- service_role can ignore RLS, but still needs GRANT on tables
```

### Investigation Timeline
Hypotheses tested (chronological order):

1. ❌ Tables don't exist → Discarded (tables existed)
2. ❌ Invalid FK → Discarded (dev user inserted)
3. ❌ RLS blocking → Discarded (disabled, error persisted)
4. ❌ Missing GRANT for anon → Discarded (applied, error persisted)
5. ⚠️ Singleton caching → Fixed but error persisted (red herring)
6. ⚠️ Anon key vs service_role → Correct approach, error persisted
7. ✅ **service_role missing GRANT → ROOT CAUSE**

### Solution Applied

```sql
-- Critical fix:
GRANT ALL ON public.products TO service_role;
GRANT ALL ON public.images TO service_role;
GRANT ALL ON public.users TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

### Code Modifications

**app/database.py:**
- ✅ Singleton removed (best practice, though not the root cause)
- ✅ Debug prints added
- ✅ New client created per call

**.env:**
- ✅ service_role key verified and configured

**Supabase Database:**
- ✅ GRANTs applied to service_role

### Validation Results

```bash
# Test command:
curl -X POST http://localhost:8000/process -F "file=@bolsa_teste.jpg"

# Response:
{
  "product_id": "291c7351-136b-477f-9505-92b7c31dfef6",  ✅ SUCCESS!
  "categoria": "bolsa",
  "estilo": "foto",
  "confianca": 0.95
}
```

```sql
-- Database verification:
SELECT * FROM products WHERE id = '291c7351-136b-477f-9505-92b7c31dfef6';
-- 1 row returned ✅

SELECT * FROM images WHERE product_id = '291c7351-136b-477f-9505-92b7c31dfef6';
-- 1 row returned ✅
```

### Lessons Learned

1. **rolbypassrls ≠ superuser**: Role with RLS bypass still requires explicit GRANTs
2. **Supabase doesn't auto-grant**: Manually created tables need explicit grants
3. **JWT verification is essential**: Decoding payload confirms actual role
4. **Singletons complicate debugging**: Persistent state between reloads masks issues

### Prevention Template

```sql
-- Template for new tables:
CREATE TABLE public.new_table (...);

-- ALWAYS add after CREATE:
GRANT ALL ON public.new_table TO service_role;
GRANT ALL ON public.new_table TO anon;
GRANT ALL ON public.new_table TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

### Impact
- ✅ Micro-PRD 02: Product Persistence → **100% COMPLETE**
- ✅ Products saving correctly to database
- ✅ Images tracked with FK integrity
- ✅ `product_id` returning valid UUID
- 🎯 Ready for Micro-PRD 03: Image Pipeline

---

## Bug Fixes Applied (v0.5.1)

### ✅ JSON Parsing Bug (FIXED)

**File:** `utils.py:49-114`
**Severity:** 🔴 High
**Status:** ✅ RESOLVED

**Problem:** The regex `r'\{[^{}]*\}'` didn't capture nested JSON objects.

```python
# Before (BROKEN):
match = re.search(r'\{[^{}]*\}', texto)
# Failed on: {"nome": "Bolsa", "dimensoes": {"altura": "30cm"}}
# Returned only: {"altura": "30cm"}  ← WRONG!
```

**Solution:** Replaced regex with bracket-counting algorithm that properly handles:
- Nested objects
- Escaped characters in strings
- Multiple JSON objects in text

```python
# After (FIXED):
def safe_json_parse(text: str) -> Optional[dict]:
    # Uses depth counting: tracks { and } while respecting strings
    depth = 0
    in_string = False
    for char in text:
        if char == '"': in_string = not in_string
        if not in_string:
            if char == '{': depth += 1
            elif char == '}': depth -= 1
        if depth == 0: # Found complete object
            return json.loads(extracted)
```

**Impact:** Tech sheet data with `dimensoes` field now parsed correctly.

### ✅ Product Enums Added (IMPROVEMENT)

**File:** `config.py:16-74`
**Status:** ✅ IMPLEMENTED

Added centralized Enums to eliminate magic strings:

```python
from app.config import ProductCategory, ProductStyle, ProductStatus, ImageType

# Usage examples:
ProductCategory.BOLSA.value  # "bolsa"
ProductCategory.is_valid("lancheira")  # True
ProductStatus.values()  # ["draft", "pending", "approved", "rejected", "published"]
```

**Benefits:**
- Type safety with IDE autocomplete
- Single source of truth for valid values
- Helper methods: `values()`, `is_valid()`

### ✅ RBAC Implementation (FIXED in v0.5.2)

**File:** `permissions.py`
**Status:** ✅ FIXED - Refactored from decorators to Dependency Factory

The RBAC system now uses FastAPI's dependency injection pattern correctly:

```python
from app.auth.permissions import require_admin, require_user, require_any, require_role

# Apenas admin
@app.delete("/users/{id}")
def delete_user(user: AuthUser = Depends(require_admin)):
    ...

# Qualquer autenticado
@app.get("/products")
def list_products(user: AuthUser = Depends(require_any)):
    ...

# Roles customizados
@app.post("/moderate")
def moderate(user: AuthUser = Depends(require_role("admin", "moderator"))):
    ...
```

## Bug Fixes Applied (v0.5.3) - Micro-PRD 03

### ✅ Transaction Rollback (Commit: `b274cb0`)

**File:** `app/services/image_pipeline.py`
**Severity:** 🔴 High
**Status:** ✅ FIXED

**Problem:** Pipeline uploaded files to multiple buckets (raw, segmented, processed-images) without rollback mechanism. If a stage failed, already uploaded files became orphans in storage.

**Solution:**
```python
# Track uploaded files for rollback
uploaded_files: list[tuple[str, str]] = []  # [(bucket, path), ...]

# After each successful upload:
uploaded_files.append((BUCKETS["original"], original_path))

# On error:
except Exception as e:
    if uploaded_files:
        self._rollback_uploads(uploaded_files)

def _rollback_uploads(self, uploaded_files):
    for bucket, path in uploaded_files:
        self.client.storage.from_(bucket).remove([path])
```

**Impact:** Consistency between database and storage; no orphan files on partial failures.

### ✅ Resource Leak Fix (Commit: `1642bb0`)

**File:** `app/services/image_composer.py`
**Severity:** 🔴 High
**Status:** ✅ FIXED

**Problem:** `BytesIO` and `PIL.Image` objects were never closed, causing memory leak in long-running processes.

**Before (BROKEN):**
```python
input_image = Image.open(BytesIO(image_bytes))
result = self.compose_white_background(input_image, target_size)
output = BytesIO()
result.save(output, format='PNG', optimize=True)
return output.getvalue()  # Leak!
```

**After (FIXED):**
```python
with BytesIO(image_bytes) as input_buffer:
    input_image = Image.open(input_buffer)
    try:
        result = self.compose_white_background(input_image, target_size)
        with BytesIO() as output:
            result.save(output, format='PNG', optimize=True)
            return output.getvalue()
    finally:
        input_image.close()
        result.close()
```

**Impact:** Prevents memory leak in prolonged use; resources released immediately.

### ✅ DoS Protection (Commit: `08a6de1`)

**Files:** `app/config.py`, `app/services/image_pipeline.py`
**Severity:** 🔴 Critical
**Status:** ✅ FIXED

**Problem:** No size/dimension validation before rembg, allowing memory exhaustion attacks.

**Solution in config.py:**
```python
# DoS Protection - File limits
MAX_FILE_SIZE_MB: int = 10
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_IMAGE_DIMENSION: int = 8000  # pixels
```

**Solution in image_pipeline.py (Stage 0):**
```python
# Validate file size
file_size = len(image_bytes)
if file_size > settings.MAX_FILE_SIZE_BYTES:
    raise ValueError(f"File too large: {size_mb:.1f}MB")

# Validate dimensions (prevents memory exhaustion)
with BytesIO(image_bytes) as img_buffer:
    with Image.open(img_buffer) as img:
        if max(img.size) > settings.MAX_IMAGE_DIMENSION:
            raise ValueError(f"Image too large: {width}x{height}px")
```

**Impact:** Protection against DoS attacks via upload; fail-fast before expensive operations.

### ✅ API Response Fields (Commit: `01b1d66`)

**File:** `app/main.py`
**Severity:** 🟡 Medium
**Status:** ✅ FIXED

**Problem:** `imagem_base64` field was overloaded with both base64 data and storage URLs, causing frontend parsing issues.

**Solution:** Separated into two distinct fields:
- `imagem_base64`: Base64-encoded image data (fallback mode)
- `imagem_url`: Storage URL when pipeline succeeds

### ✅ Thread-Safe Client Loading (v0.5.2)

**File:** `app/services/image_pipeline.py`
**Severity:** 🟡 Medium
**Status:** ✅ FIXED

**Problem:** Supabase client loading had race condition in concurrent requests.

**Solution:** Implemented double-check locking pattern for thread-safe lazy initialization.

### ✅ rembg Error Handling (v0.5.2)

**File:** `app/services/image_pipeline.py`
**Severity:** 🟡 Medium
**Status:** ✅ FIXED

**Problem:** rembg errors were not properly caught and logged.

**Solution:** Specific exception handling for rembg with detailed error messages and proper cleanup.

---

## Development Roadmap & Progress

### Completed Micro-PRDs

#### ✅ Micro-PRD 01: Authentication & Users (100%)
**Completed:** 2026-01-12
- JWT authentication with Supabase Auth
- RBAC with admin/user roles
- User management with RLS policies
- Dev mode for local development

#### ✅ Micro-PRD 02: Product Persistence (100%)
**Completed:** 2026-01-13
- Products table with workflow (draft→pending→approved→rejected→published)
- Images table with cascade delete
- Database CRUD operations
- service_role GRANT resolution

#### ✅ Micro-PRD 03: Image Pipeline (100%)
**Completed:** 2026-01-13
**Implemented by:** Antigravity (Google DeepMind)
- **ImageComposer Service:** White background composition with shadow (1200x1200px, 85% coverage)
- **HuskLayer Service:** Quality validation (resolution + centering + background purity = 0-100 score)
- **ImagePipelineSync Service:** Triple storage orchestration (original → segmented → processed)
- **RLS Policies:** Dual mode support (dev + prod) with 8 policies
- **Test Script:** Local pipeline testing (`scripts/test_pipeline.py`)
- **Integration:** `/process` endpoint updated with `quality_score` and `images` in response

### Current Progress
```
████████████████████████░░░░░░ 65%

Micro-PRD 00: ⏭️ Skipped
Micro-PRD 01: ✅ 100% (Auth & Users)
Micro-PRD 02: ✅ 100% (Product Persistence)
Micro-PRD 03: ✅ 100% (Image Pipeline)       ← COMPLETE!
Micro-PRD 04: ⏸️   0% (Async Jobs)           ← NEXT
Micro-PRD 05: ⏸️   0% (Tech Sheet)
Micro-PRD 06: ⏸️   0% (Workflow Approval)
```

### Next Steps: Micro-PRD 04 (Async Jobs)

**Scope:**
1. Move heavy processing (rembg) to background workers
2. Implement job queue with status tracking
3. Add webhook notifications for job completion
4. Implement retry logic for failed jobs

**Benefits:**
- Non-blocking API responses
- Better scalability for concurrent uploads
- Timeout and retry handling

### Timeline (Revised)
```
✅ Micro-PRD 01: 12/01 (COMPLETE)
✅ Micro-PRD 02: 13/01 (COMPLETE)
✅ Micro-PRD 03: 13/01 (COMPLETE)
⏳ Micro-PRD 04: 14-17/01 (4 days)
⏳ Micro-PRD 05: 20-24/01 (5 days)
⏳ Micro-PRD 06: 27-31/01 (5 days)

MVP COMPLETE: ~31/01/2026 (18 days remaining)
```

---

## Related Documentation

- `CODE_REVIEW.md` - Comprehensive code review (score: 9.2/10)
- `FASE_DE_TESTES.md` - Complete testing protocols and progress
- `GEMINI.md` - AI model context and prompts
- `ANTIGRAVITY.md` - Implementation history for Micro-PRD 03
- `README.md` - Project overview and setup
- `.env.example` - Environment variable template

---

**Last Updated:** 2026-01-13
**Current Phase:** Micro-PRD 04 (Async Jobs) - Next
**For Questions:** Refer to test results in FASE_DE_TESTES.md or check git history for context
