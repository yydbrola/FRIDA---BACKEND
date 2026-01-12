# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Version:** 0.5.0
**Last Updated:** 2026-01-12
**Testing Status:** 64% Complete (16/25 tests passing)
**Production Ready:** Core features ✓ | Edge cases & Load testing pending

## Project Overview

Frida Orchestrator is a FastAPI backend for fashion product image processing (bags, lunchboxes, thermos). It provides:
- AI-powered product classification via Google Gemini 2.0 Flash Lite
- Background removal via rembg (U2NET model) with white background composition
- Technical specification generation with premium HTML templates
- Multi-format image support (JPEG, PNG, WebP)
- Deep security validation (magic numbers + Pillow integrity checks)
- Optional Supabase integration for audit trail and storage
- JWT authentication (Supabase Auth) with dev mode

## Project Structure

```
componentes/
├── app/
│   ├── auth/
│   │   ├── __init__.py
│   │   └── supabase.py              # JWT validation (Supabase Auth)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py            # Gemini Vision + Structured Output
│   │   ├── background_remover.py    # rembg + Pillow composition
│   │   ├── tech_sheet.py            # Jinja2 template rendering
│   │   └── storage.py               # Supabase storage + audit trail
│   ├── templates/
│   │   └── tech_sheet_premium.html  # Premium tech sheet (Outfit font)
│   ├── main.py                      # FastAPI app + routes
│   ├── config.py                    # Settings management
│   ├── utils.py                     # Validation + image utilities
│   └── __init__.py
├── venv/                            # Python 3.12 virtual environment
├── .env                             # Environment variables (secrets)
├── .env.example                     # Template for .env
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
├── CLAUDE.md                        # This file
├── GEMINI.md                        # AI model context
├── FASE_DE_TESTES.md               # Testing protocols v0.5.0
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

- **Auth Service** (`auth/supabase.py`): JWT validation via PyJWT and cryptography for Supabase Auth integration. Supports dev mode with fake user_id.

### Processing Pipeline

**`/process` endpoint (main pipeline):**
1. **Validation Layer 1:** Content-Type header check (fast, vulnerable to spoofing)
2. **Validation Layer 2:** Magic numbers check (file signatures)
3. **Validation Layer 3:** Pillow integrity check (detects corruption)
4. **Classification:** Gemini 2.0 Flash Lite with Structured Output (guaranteed JSON)
5. **Background Removal:** rembg U2NET model
6. **Composition:** White background + resize to 1080x1080px
7. **Tech Sheet (optional):** Gemini data extraction + Jinja2 HTML rendering
8. **Storage (optional):** Upload to Supabase + audit log
9. **Response:** Base64 encoded PNG + metadata

### Key Design Decisions

**Sync Routes for CPU-bound Tasks**: Processing routes (`/process`, `/classify`, `/remove-background`) use `def` instead of `async def` intentionally. FastAPI runs sync functions in a thread pool, preventing event loop blocking during heavy image operations (rembg uses ~2-3s per image).

**Fail-Fast Startup**: The server won't start if `GEMINI_API_KEY` is missing or if critical services fail to initialize. This catches configuration errors at deploy time instead of runtime.

**Gemini Structured Output**: The classifier uses `response_mime_type="application/json"` with `response_schema` to guarantee valid JSON responses without regex parsing. Temperature is set to 0.1 for consistency.

**Multi-layer Image Validation**: Three layers of validation protect against malicious files:
1. Content-Type (fast filter)
2. Magic numbers (file signatures)
3. Pillow integrity (structural validation)

## Configuration

Environment variables are managed in `config.py` via `python-dotenv`:

### Required (Fail-Fast)
- `GEMINI_API_KEY`: Google Gemini API key (server won't start without this)

### Optional - Supabase
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_KEY`: Supabase anon/service key
- `SUPABASE_BUCKET`: Storage bucket name (default: `processed-images`)
- `SUPABASE_JWT_SECRET`: JWT secret for authentication (required if AUTH_ENABLED=true)

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

**Storage:**
- Bucket name: `processed-images`
- Table name: `historico_geracoes`

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
- Complete pipeline: classification + background removal + optional tech sheet
- **Form Data:**
  - `file` (required): Product image
  - `gerar_ficha` (optional): boolean, default=false
  - `product_id` (optional): string for storage organization
- **Response:**
  ```json
  {
    "status": "sucesso",
    "categoria": "bolsa",
    "estilo": "foto",
    "confianca": 0.95,
    "imagem_base64": "iVBORw0KGgo...",
    "ficha_tecnica": {
      "dados": {
        "nome": "Bolsa Premium",
        "categoria": "bolsa",
        "descricao": "Descrição elegante...",
        "materiais": ["Couro sintético premium"],
        "cores": ["Preto"],
        "dimensoes": {"altura": "30 cm", "largura": "40 cm", "profundidade": "15 cm"},
        "detalhes": ["Design moderno"]
      },
      "html": "<html>...</html>"
    },
    "mensagem": "Imagem processada com sucesso! user_id=xxx"
  }
  ```
- **Storage:** If Supabase configured, saves to `{user_id}/{product_id}/{timestamp}.png`
- **Audit:** Logs to `historico_geracoes` with metadata
- **Status Codes:** 200 OK, 400 Bad Request, 422 Validation Error, 500 Server Error

**`GET /auth/test`**
- Tests authentication
- **Dev Mode Response:**
  ```json
  {
    "status": "authenticated",
    "user_id": "00000000-0000-0000-0000-000000000000",
    "message": "Token JWT válido!"
  }
  ```
- **Prod Mode Response:** Same but with real user_id from JWT
- **Status Codes:** 200 OK, 401 Unauthorized (prod mode only)

## Type Contracts

Services use TypedDict for data contracts:

```python
ClassificationResult = {
    "item": str,         # bolsa|lancheira|garrafa_termica|desconhecido
    "estilo": str,       # sketch|foto|desconhecido
    "confianca": float   # 0.0-1.0
}

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

## Known Limitations & TODOs

### 🔴 High Priority

**1. Tech Sheet Fields Require Rework**
- **Source:** FASE_DE_TESTES.md, test 4.2
- **Issue:** Current fields (`nome`, `materiais`, `cores`, `dimensoes`, `detalhes`) are generic and need customization for Carol's specific requirements.
- **Status:** Functional for validation, **will be updated**
- **Files to modify:** `app/services/tech_sheet.py`, `app/templates/tech_sheet_premium.html`

**2. Image Quality Issues with Models in Background**
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

**3. Complete Storage Testing**
- Category 6 tests pending (Supabase integration)
- Requires: SUPABASE_URL, SUPABASE_KEY configuration
- Validates: Upload to bucket, audit trail in `historico_geracoes`

**4. Edge Cases & Load Testing**
- File size limits (>10MB)
- Concurrent request handling
- Invalid Content-Type scenarios

**5. Production Deployment Documentation**
- Deployment guide (Docker, cloud services)
- Monitoring and logging setup
- Performance optimization recommendations

### 🟢 Low Priority

**6. Model Caching Optimization**
- rembg downloads U2NET model (~170MB) on first run
- Consider pre-loading in Docker image

**7. Image Generation Feature**
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
- `get_current_user_id()` returns fake UUID: `00000000-0000-0000-0000-000000000000`
- No token validation is performed
- All routes are accessible without Authorization header
- Useful for local development and testing

### To Enable Authentication (Production)

1. Set environment variable:
   ```bash
   AUTH_ENABLED=true
   ```

2. Configure JWT secret from Supabase:
   ```bash
   SUPABASE_JWT_SECRET=your_jwt_secret_here
   ```
   (Get from: Supabase Dashboard > Settings > API > JWT Secret)

3. Routes are already protected with `Depends(get_current_user_id)`:
   ```python
   @app.post("/process")
   def processar_produto(..., user_id: str = Depends(get_current_user_id)):
       # user_id is validated from JWT when AUTH_ENABLED=true
   ```

### JWT Validation Details
- **Algorithm:** HS256
- **Audience:** "authenticated"
- **Claim:** Extracts user_id from "sub"
- **Verifies:** Signature, expiration, audience
- **Errors:** Returns HTTP 401 with `WWW-Authenticate: Bearer` header

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

**Current Branch:** `fix/classifier-schema-compatibility`
**Recent Commits:**
- `fde4658` - fix: remove unsupported validation keywords from Gemini schema
- `de0d7fb` - feat: complete backend synchronization and audit storage
- `e3a809f` - feat: implement robust startup validation and structured AI output
- `b476310` - Initial commit: Frida Orchestrator Backend

**Modified Files:**
- `requirements.txt` (updated dependencies)
- `FASE_DE_TESTES.md` (testing progress updated)

## Quick Reference

**Start Server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Run Tests:**
```bash
# See FASE_DE_TESTES.md for full test suite
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify -F "file=@test.jpg"
```

**Common Issues:**

1. **Server won't start:** Check `GEMINI_API_KEY` in `.env`
2. **rembg slow on first run:** Downloading U2NET model (~170MB), normal
3. **WebP files rejected:** Use `-F "file=@image.webp;type=image/webp"` with curl
4. **Image distortion:** Input has model/person, see "Known Limitations" section
5. **Authentication errors:** Check `AUTH_ENABLED` setting in `.env`

## Related Documentation

- `FASE_DE_TESTES.md` - Complete testing protocols and progress
- `GEMINI.md` - AI model context and prompts
- `README.md` - Project overview and setup
- `.env.example` - Environment variable template

---

**Last Updated:** 2026-01-12
**For Questions:** Refer to test results in FASE_DE_TESTES.md or check git history for context
