# Frida Orchestrator - Backend Context

## Project Status
**Version:** 0.5.3
**Last Updated:** 2026-01-13
**Testing Status:** 64% Complete (16/25 tests passing)
**Development Progress:** 65% (Micro-PRD 03 Complete)
**Code Review Score:** 8.6/10 (see CODE_REVIEW.md)
**Production Ready:** Core features ✓ | Edge cases & Load testing pending

## Project Overview
**Frida Orchestrator** is a FastAPI-based backend service designed for the fashion industry (specifically bags, lunchboxes, and thermos). It serves as the intelligence core for the Frida platform, handling image processing, AI classification, and technical documentation generation.

### Key Capabilities
1.  **AI Classification:** Uses Google's Gemini 2.0 Flash Lite with **Structured Output** to classify product images by category and style with 100% JSON reliability.
2.  **Image Processing:** Automated background removal using `rembg` (U2NET) and standardizing images with a pure white background (#FFFFFF) and resizing to 1080x1080px via `Pillow`.
3.  **Tech Sheet Generation:** Generates premium technical data sheets (HTML/JSON) using Jinja2 templates and Gemini-powered data extraction.
4.  **Product Catalog & Workflow:** Manages product lifecycle (draft → pending → approved → rejected → published) with database persistence.
5.  **Secure Authentication & RBAC:** Validates Supabase JWT tokens and enforces Role-Based Access Control (`admin` vs `user`) with database-backed user validation.
6.  **Audit & Storage:** Persists processed images to Supabase Storage and tracks metadata in PostgreSQL.
7.  **Image Pipeline (NEW v0.5.3):** Triple storage (original, segmented, processed) with quality validation scoring 0-100.
8.  **Quality Validation (NEW v0.5.3):** HuskLayer service validates resolution, centering, and background purity with pass threshold ≥80.

## Tech Stack
-   **Runtime:** Python 3.12+
-   **Web Framework:** FastAPI (optimized with Sync Routes for CPU-bound tasks)
-   **Server:** Uvicorn
-   **AI Model:** Google Generative AI (Gemini 2.0 Flash Lite + Structured Output)
-   **Image Logic:** `rembg` (Background Removal), `Pillow` (Manipulation + Deep Validation)
-   **Templating:** Jinja2
-   **Database:** Supabase PostgreSQL (via `supabase-py` client)
-   **Authentication:** Supabase Auth (JWT validation via `PyJWT` + `cryptography`)
-   **Environment:** `python-dotenv`

## Directory Structure
```
componentes/
├── app/
│   ├── auth/
│   │   ├── __init__.py         # Auth module exports
│   │   ├── permissions.py      # RBAC dependency factories (require_admin, require_role)
│   │   └── supabase.py         # JWT validation + AuthUser model
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py       # Gemini Vision + Structured Output
│   │   ├── background_remover.py # rembg + Pillow composition (legacy)
│   │   ├── tech_sheet.py       # Jinja2 logic
│   │   ├── storage.py          # Supabase storage & audit
│   │   ├── image_composer.py   # Advanced composition with shadow (NEW v0.5.3)
│   │   ├── husk_layer.py       # Quality validation 0-100 (NEW v0.5.3)
│   │   └── image_pipeline.py   # Pipeline orchestration (NEW v0.5.3)
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                 # FastAPI entry point (Fail-Fast Startup)
│   ├── config.py               # Settings + Product Enums
│   ├── database.py             # Supabase DB client (Users, Products, Images)
│   └── utils.py                # Helpers (Deep Validation, safe_json_parse)
├── SQL para o SUPABASE/        # Database Migration Scripts
│   ├── 01_create_users_table.sql
│   ├── 02_seed_admin_zero.sql
│   ├── 03_seed_team_members.sql
│   ├── 04_create_products.sql  # Workflow + RLS
│   ├── 05_create_images.sql    # Image tracking + FK
│   └── 06_rls_dual_mode.sql    # RLS dual mode (NEW v0.5.3)
├── scripts/                    # Utility scripts (NEW v0.5.3)
│   └── test_pipeline.py        # Local pipeline testing
├── venv/                       # Virtual environment (ignored by git)
├── .env                        # Environment variables (API Keys)
├── .env.example                # Template for env variables
├── requirements.txt            # Python dependencies
├── GEMINI.md                   # Project context for AI
├── CLAUDE.md                   # Context for Claude Code
├── ANTIGRAVITY.md              # Implementation history for PRD 03 (NEW)
├── CODE_REVIEW.md              # Comprehensive code review (score: 8.6/10)
├── FASE_DE_TESTES.md           # Testing protocols v0.5.0
└── README.md                   # Project documentation
```

## Database Schema & Migrations

### Users Table
-   `id` (UUID, PK): Matches Supabase Auth user ID.
-   `email` (TEXT, Unique)
-   `role` (TEXT): 'admin' | 'user'.
-   `name` (TEXT)

### Products Table
-   `id` (UUID, PK)
-   `name` (TEXT)
-   `sku` (TEXT, Unique)
-   `category` (TEXT): bolsa | lancheira | garrafa_termica | desconhecido
-   `classification_result` (JSONB): Gemini AI classification response
-   `status` (TEXT): draft | pending | approved | rejected | published
-   `created_by` (UUID, FK -> users)

### Images Table
-   `id` (UUID, PK)
-   `product_id` (UUID, FK -> products, CASCADE DELETE)
-   `type` (TEXT): original | segmented | processed
-   `storage_bucket` (TEXT)
-   `storage_path` (TEXT)
-   `quality_score` (INTEGER): 0-100

## Product Enums (NEW in v0.5.1)

Centralized in `config.py` for type safety:

```python
from app.config import ProductCategory, ProductStyle, ProductStatus, ImageType

# Categories
ProductCategory.BOLSA.value           # "bolsa"
ProductCategory.LANCHEIRA.value       # "lancheira"
ProductCategory.GARRAFA_TERMICA.value # "garrafa_termica"
ProductCategory.DESCONHECIDO.value    # "desconhecido"

# Styles
ProductStyle.SKETCH.value             # "sketch"
ProductStyle.FOTO.value               # "foto"

# Workflow Status
ProductStatus.DRAFT.value             # "draft"
ProductStatus.PENDING.value           # "pending"
ProductStatus.APPROVED.value          # "approved"
ProductStatus.REJECTED.value          # "rejected"
ProductStatus.PUBLISHED.value         # "published"

# Image Types
ImageType.ORIGINAL.value              # "original"
ImageType.SEGMENTED.value             # "segmented"
ImageType.PROCESSED.value             # "processed"

# Helper methods
ProductCategory.is_valid("bolsa")     # True
ProductStatus.values()                # ["draft", "pending", "approved", "rejected", "published"]
```

## Implementation Details

### Image Processing Pipeline (Updated v0.5.3)
1.  **Deep Validation:** Checks Magic Numbers and Pillow Integrity.
2.  **Classification:** Gemini 2.0 identifies category/style.
3.  **Product Creation:** Saves draft to `products` table.
4.  **Image Pipeline (NEW):**
    - Upload original → 'raw' bucket → type='original'
    - Segmentation via `rembg` → 'segmented' bucket → type='segmented'
    - Composition via `ImageComposer` (1200x1200, shadow) → 'processed-images' bucket → type='processed'
    - Quality validation via `HuskLayer` → quality_score (0-100)
5.  **Output:** Base64/URL + metadata + product_id + quality_score.

### Service Pattern
- **ClassifierService**: temperature 0.1, response_schema for reliability.
- **BackgroundRemoverService**: U2NET model, async-friendly thread execution (legacy).
- **ImageComposer (NEW v0.5.3)**: White background composition with shadow, 1200x1200px output.
- **HuskLayer (NEW v0.5.3)**: Quality validation (resolution 30pts + centering 40pts + background 30pts).
- **ImagePipelineSync (NEW v0.5.3)**: Orchestrates triple storage with quality validation.
- **Auth Service**: Enforces database registration (HTTP 403 if user not in `users` table).
- **Database Module**: Creates new client per call (no singleton/cache).

### Bug Fixes Applied (v0.5.1)

**JSON Parsing Fix:**
- Old: Regex `r'\{[^{}]*\}'` failed on nested objects
- New: Bracket-counting algorithm handles nested JSON correctly
- Impact: Tech sheet `dimensoes` field now parses properly

**Product Enums Added:**
- Eliminates magic strings throughout codebase
- Type safety with IDE autocomplete
- Helper methods: `values()`, `is_valid()`

### Critical Issue Resolution (RESOLVED)
**Issue:** `POST /process` returned `product_id: null` due to missing GRANTs for `service_role`.

**Fix:** Explicit `GRANT ALL` on `products`, `images`, and `users` tables to `service_role` in Supabase.

**Key Lesson:** PostgreSQL `rolbypassrls=true` does NOT bypass GRANT permissions. Tables need explicit GRANTs even for service_role.

## API Endpoints

### Public
- `GET /` - Homepage
- `GET /health` - Service health check
- `GET /public/ping` - Connectivity test
- `GET /docs` - Swagger UI

### Protected (requires JWT if AUTH_ENABLED=true)
- `POST /classify` - Classify image only
- `POST /remove-background` - Remove background only
- `POST /process` - Full pipeline (classification + processing + database storage + quality validation)
  - **NEW v0.5.3:** Returns `images`, `quality_score`, `quality_passed` in response
- `GET /products` - List user's products
- `GET /products/{id}` - Get specific product
- `GET /auth/test` - Test authentication

## Testing Protocol (v0.5.0)
- **16/25 Tests Passing (64%)**
- **Verified:** Health, Auth Dev Mode, Classification, Full Pipeline, Deep Security.
- **Pending:** Supabase Storage, Load Testing, Edge Cases.

## Development Roadmap

### Current Progress: 65%
```
████████████████████████░░░░░░ 65%

✅ Micro-PRD 01: Auth & Users (100%)
✅ Micro-PRD 02: Product Persistence (100%)
✅ Micro-PRD 03: Image Pipeline (100%) ← COMPLETE!
⏸️ Micro-PRD 04: Async Jobs (0%) ← NEXT
⏸️ Micro-PRD 05: Tech Sheet (0%)
⏸️ Micro-PRD 06: Workflow Approval (0%)
```

### Completed: Micro-PRD 03 (Image Pipeline)
**Implemented by:** Antigravity (Google DeepMind)
- **ImageComposer:** White background composition with shadow (1200x1200px, 85% coverage)
- **HuskLayer:** Quality validation (resolution 30pts + centering 40pts + background 30pts = 0-100)
- **ImagePipelineSync:** Triple storage (original → segmented → processed)
- **Test Script:** `scripts/test_pipeline.py` for local testing
- **Test Result:** 100/100 score on first test

### Next: Micro-PRD 04 (Async Jobs)
1. Move heavy processing (rembg) to background workers
2. Implement job queue with status tracking
3. Add webhook notifications for job completion
4. Implement retry logic for failed jobs

## Common Tasks & Commands
- **Run Server:** `uvicorn app.main:app --reload --port 8000`
- **Health Check:** `curl http://localhost:8000/health`
- **Process Image:** `curl -X POST http://localhost:8000/process -F "file=@image.jpg"`
- **List Products:** `curl http://localhost:8000/products`

## Configuration

### Required
- `GEMINI_API_KEY`: Google Gemini API key (fail-fast on startup)

### Optional - Supabase
- `SUPABASE_URL`: Project URL
- `SUPABASE_KEY`: Service role key (recommended for server)
- `SUPABASE_JWT_SECRET`: JWT secret for auth validation

### Optional - Server
- `AUTH_ENABLED`: Enable JWT validation (default: false)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `DEBUG`: Enable reload mode (default: true)

## Known Issues

1. ~~**RBAC Decorators**~~ ✅ FIXED in v0.5.2: Refactored to Dependency Factory pattern. Use `Depends(require_admin)` or `Depends(require_role("admin"))`.
2. **Rate Limiting Not Implemented** ⚠️: Only remaining security blocker. Vulnerable to API abuse. Recommended: `slowapi` library.
3. **Image Segmentation with Models**: rembg includes people in lifestyle photos. Consider Gemini Vision for product detection.
4. **Performance (noted in v0.5.3)**: rembg takes 2-5s per image. Micro-PRD 04 (Async Jobs) will address this.

## Related Documentation
- `CLAUDE.md` - Detailed project context (1000+ lines)
- `CODE_REVIEW.md` - Comprehensive code analysis (score: 8.6/10)
- `FASE_DE_TESTES.md` - Testing protocols and progress
- `ANTIGRAVITY.md` - Implementation history for Micro-PRD 03 (NEW)
