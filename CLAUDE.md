# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Frida Orchestrator is a FastAPI backend for fashion product image processing (bags, lunchboxes, thermos). It provides AI-powered classification via Google Gemini, background removal via rembg, and technical specification generation.

## Development Commands

```bash
# Setup (one-time)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify -F "file=@image.jpg"
curl -X POST http://localhost:8000/process -F "file=@image.jpg" -F "gerar_ficha=true"
```

## Architecture

### Service Layer Pattern
All business logic lives in `app/services/`. The `main.py` handles HTTP routing and delegates to services:

- **ClassifierService** (`classifier.py`): Uses Gemini Structured Output for product classification. Returns `ClassificationResult` TypedDict with `item`, `estilo`, `confianca` fields.
- **BackgroundRemoverService** (`background_remover.py`): rembg for background removal + Pillow for white background composition.
- **TechSheetService** (`tech_sheet.py`): Gemini for data extraction + Jinja2 for HTML rendering.
- **StorageService** (`storage.py`): Optional Supabase integration for audit trail.
- **Auth Service** (Planned): JWT validation via `PyJWT` and `cryptography` for Supabase Auth integration.

### Processing Pipeline
1. Deep image validation (magic numbers + Pillow integrity check in `utils.py`)
2. AI classification via Gemini Structured Output
3. Background removal (rembg) → white background (#FFFFFF) composition
4. Optional tech sheet generation
5. Optional Supabase audit storage

### Key Design Decisions

**Sync Routes for CPU-bound Tasks**: Processing routes (`/process`, `/classify`, `/remove-background`) use `def` instead of `async def` intentionally. FastAPI runs sync functions in a thread pool, preventing event loop blocking during heavy image operations.

**Fail-Fast Startup**: The server won't start if `GEMINI_API_KEY` is missing or if critical services fail to initialize. This catches configuration errors at deploy time.

**Gemini Structured Output**: The classifier uses `response_mime_type="application/json"` with `response_schema` to guarantee valid JSON responses without regex parsing.

### Configuration
Environment variables are managed in `config.py` via `python-dotenv`:
- `GEMINI_API_KEY` (required): Google Gemini API key
- `SUPABASE_URL`, `SUPABASE_KEY` (optional): For audit storage
- Default output size: 1080x1080px with #FFFFFF background

### Type Contracts
Services use TypedDict for data contracts:
- `ClassificationResult`: `item`, `estilo`, `confianca`
- `TechSheetData`: `nome`, `categoria`, `descricao`, `materiais`, `cores`, `dimensoes`, `detalhes`
- `StorageResult`: `success`, `image_url`, `record_id`, `error`

## Gemini Schema Compatibility

When modifying `CLASSIFICATION_SCHEMA` in `classifier.py`, note that Gemini's schema validation differs from JSON Schema. Unsupported keywords like `minimum`/`maximum` will cause errors. Use `description` to document constraints instead.

## Authentication (AUTH_ENABLED)

**Current Status:** `AUTH_ENABLED=false` (development mode)

**Reason:** Authentication is disabled by default to simplify local development and testing. The auth module (`app/auth/`) is fully implemented but not enforced on routes yet.

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

3. Protect routes by adding the dependency:
   ```python
   from fastapi import Depends
   from app.auth import get_current_user_id

   @app.post("/process")
   def process(user_id: str = Depends(get_current_user_id)):
       # user_id is validated from JWT
   ```

### Dev Mode Behavior (AUTH_ENABLED=false)
- `get_current_user_id()` returns fake UUID: `00000000-0000-0000-0000-000000000000`
- No token validation is performed
- All routes are accessible without Authorization header

### TODO
- [x] Add `Depends(get_current_user_id)` to `/process`, `/classify`, `/remove-background`
- [ ] Set `AUTH_ENABLED=true` in production environment
- [x] Update `StorageService` to accept `user_id` and `product_id` parameters

