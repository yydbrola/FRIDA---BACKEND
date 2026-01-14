# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

| Metric | Value |
|--------|-------|
| Version | 0.5.3 |
| Last Updated | 2026-01-13 |
| Testing Status | 64% (16/25 core) + 100% (61/61 PRD03) |
| Code Review Score | 9.2/10 |
| Development Progress | 65% (Micro-PRD 03 Complete) |
| Next Phase | Micro-PRD 04 (Async Jobs) |

## Project Overview

Frida Orchestrator is a FastAPI backend for fashion product image processing (bags, lunchboxes, thermos). Core features:
- AI-powered product classification via Google Gemini 2.0 Flash Lite
- Background removal via rembg (U2NET) with white background composition
- Technical specification generation with Jinja2 HTML templates
- Triple image storage pipeline (original, segmented, processed)
- Quality validation system (HuskLayer) with 0-100 scoring
- JWT authentication with Supabase Auth + RBAC (admin/user roles)
- Product catalog with workflow (draft->pending->approved->rejected->published)

## Project Structure

```
componentes/
├── app/
│   ├── auth/
│   │   ├── supabase.py              # JWT validation + AuthUser model
│   │   └── permissions.py           # RBAC: require_admin, require_role
│   ├── services/
│   │   ├── classifier.py            # Gemini Vision + Structured Output
│   │   ├── background_remover.py    # rembg + Pillow (legacy)
│   │   ├── tech_sheet.py            # Jinja2 template rendering
│   │   ├── storage.py               # Supabase storage + audit
│   │   ├── image_composer.py        # White background + shadow (1200x1200)
│   │   ├── husk_layer.py            # Quality validation 0-100
│   │   └── image_pipeline.py        # Pipeline orchestration
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                      # FastAPI routes
│   ├── config.py                    # Settings + Enums
│   ├── database.py                  # Supabase queries
│   └── utils.py                     # Validation utilities
├── SQL para o SUPABASE/             # Migration scripts (01-06)
├── scripts/
│   ├── test_pipeline.py
│   └── test_prd03_complete.py       # 61 tests
├── test_images/
├── CHANGELOG.md                     # Version history & bug fixes
├── TESTS.md                         # Test documentation
├── CODE_REVIEW.md                   # Code review (9.2/10)
└── FASE_DE_TESTES.md               # Testing protocols
```

## Development Commands

```bash
# Setup
cd componentes && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env

# Run server
uvicorn app.main:app --reload --port 8000

# Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify -F "file=@image.jpg"
curl -X POST http://localhost:8000/process -F "file=@image.jpg"
python scripts/test_prd03_complete.py
```

## Architecture

### Service Layer

| Service | File | Purpose |
|---------|------|---------|
| ClassifierService | `classifier.py` | Gemini Structured Output for classification |
| BackgroundRemoverService | `background_remover.py` | rembg + white background (legacy) |
| TechSheetService | `tech_sheet.py` | Gemini extraction + Jinja2 HTML |
| StorageService | `storage.py` | Supabase storage + audit trail |
| ImageComposer | `image_composer.py` | 1200x1200 composition with shadow |
| HuskLayer | `husk_layer.py` | Quality scoring (resolution, centering, purity) |
| ImagePipelineSync | `image_pipeline.py` | Triple storage orchestration |

### Processing Pipeline (`/process`)

1. **Validation:** Content-Type -> Magic numbers -> Pillow integrity
2. **Classification:** Gemini 2.0 Flash Lite (Structured Output)
3. **Database:** Save product to `products` table
4. **Image Pipeline:** original->segmented->processed (3 buckets)
5. **Quality:** HuskLayer validation (0-100 score)
6. **Tech Sheet:** Optional Gemini extraction + HTML
7. **Response:** URLs + metadata + product_id + quality_score

### Key Design Decisions

- **Sync Routes:** `def` instead of `async def` for CPU-bound rembg operations
- **Fail-Fast Startup:** Missing GEMINI_API_KEY prevents server start
- **Multi-layer Validation:** Content-Type + magic numbers + Pillow integrity
- **DoS Protection:** 10MB file limit, 8000px dimension limit

## Configuration

### Required
| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (fail-fast) |

### Optional - Supabase
| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | - | Project URL (required for storage/auth) |
| `SUPABASE_KEY` | - | Service role key |
| `SUPABASE_BUCKET` | `processed-images` | Storage bucket |
| `SUPABASE_JWT_SECRET` | - | JWT secret (if AUTH_ENABLED) |

### Optional - Server
| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `false` | Enable JWT authentication |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Debug/reload mode |

### Hardcoded Values
- **Gemini Models:** `gemini-2.0-flash-lite` (classifier, tech sheet)
- **Output Size:** 1200x1200px (composer), 1080x1080px (legacy)
- **Quality Threshold:** 80/100 to pass
- **DoS Limits:** 10MB file, 8000px dimension

## Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | HTML homepage |
| GET | `/public/ping` | Connectivity test |
| GET | `/health` | Service health check |
| GET | `/docs` | Swagger UI |

### Protected (if AUTH_ENABLED=true)

| Method | Path | Description | Key Response Fields |
|--------|------|-------------|---------------------|
| POST | `/classify` | Classify image only | `classificacao.item`, `.estilo`, `.confianca` |
| POST | `/remove-background` | Remove background | `imagem_base64` |
| POST | `/process` | Full pipeline | `product_id`, `quality_score`, `images`, `categoria` |
| GET | `/auth/test` | Test authentication | `user_id`, `email`, `role` |
| GET | `/products` | List user products | `products[]`, `total` |
| GET | `/products/{id}` | Get product details | `product` object |

### `/process` Response Fields
- `product_id`: UUID of created product
- `categoria`, `estilo`, `confianca`: Classification result
- `quality_score`, `quality_passed`: HuskLayer validation
- `images.original`, `.segmented`, `.processed`: Storage URLs
- `ficha_tecnica` (if gerar_ficha=true): HTML tech sheet

## Database Schema

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | Authentication + RBAC | `id`, `email`, `role` (admin/user) |
| `products` | Product catalog | `id`, `category`, `status`, `classification_result` |
| `images` | Image tracking | `product_id`, `type`, `storage_path`, `quality_score` |

### Product Workflow States
`draft` -> `pending` -> `approved` / `rejected` -> `published`

### Image Types
`original` (raw bucket) -> `segmented` -> `processed` (processed-images bucket)

### Migration Scripts (execute in order)
1. `01_create_users_table.sql` - Users + RLS
2. `02_seed_admin_zero.sql` - Initial admin
3. `03_seed_team_members.sql` - Team (optional)
4. `04_create_products.sql` - Products + workflow
5. `05_create_images.sql` - Images + cascade
6. `06_rls_dual_mode.sql` - Dual mode RLS

## Authentication

### Dev Mode (AUTH_ENABLED=false)
Returns fake `AuthUser`: `user_id=00000000-...`, `email=dev@frida.com`, `role=admin`

### Production Mode (AUTH_ENABLED=true)
- JWT Algorithm: HS256
- Audience: "authenticated"
- Requires user exists in `users` table (HTTP 403 if not)

### RBAC Dependencies
```python
from app.auth.permissions import require_admin, require_any, require_role
user: AuthUser = Depends(require_admin)       # Admin only
user: AuthUser = Depends(require_any)         # Any authenticated
user: AuthUser = Depends(require_role("mod")) # Custom roles
```

## Known Limitations & TODOs

### High Priority

1. **Rate Limiting Not Implemented**
   - Impact: API abuse, excessive Gemini costs
   - Solution: Implement with `slowapi` library

2. **Tech Sheet Fields Need Customization**
   - Files: `tech_sheet.py`, `tech_sheet_premium.html`

3. **Image Quality with Models in Background**
   - rembg includes people, causing distortion
   - Works for isolated products only

### Medium Priority
4. Complete Supabase storage tests (Category 6)
5. Edge cases & load testing
6. Production deployment documentation

### Low Priority
7. rembg model pre-loading in Docker
8. Image generation feature (experimental)

## Type Contracts

```python
# AuthUser (Pydantic)
user_id: str, email: str, role: "admin"|"user", name: Optional[str]

# ClassificationResult (TypedDict)
item: str, estilo: str, confianca: float

# QualityReport
score: int (0-100), passed: bool, details: dict
```

## Dependencies

| Category | Packages |
|----------|----------|
| Core | `fastapi==0.115.0`, `uvicorn==0.30.6`, `python-multipart` |
| AI/Image | `google-generativeai==0.8.0`, `rembg==2.0.59`, `pillow==10.4.0` |
| Templates | `jinja2==3.1.4` |
| Storage | `supabase==2.7.0` |
| Auth | `PyJWT==2.8.0`, `cryptography==41.0.7` |

## Quick Reference

**Common Issues:**
1. Server won't start: Check `GEMINI_API_KEY`
2. rembg slow first run: Downloading U2NET (~170MB)
3. WebP rejected: Use `file=@image.webp;type=image/webp`
4. Image distortion: Input has model/person
5. HTTP 403: User not in `users` table

**See Also:**
- `CHANGELOG.md` - Version history, bug fixes, investigations
- `TESTS.md` - Test documentation and commands
- `CODE_REVIEW.md` - Code review analysis
- `FASE_DE_TESTES.md` - Testing protocols

## Development Progress

```
Micro-PRD 01: Auth & Users       [COMPLETE]
Micro-PRD 02: Product Persistence [COMPLETE]
Micro-PRD 03: Image Pipeline      [COMPLETE]
Micro-PRD 04: Async Jobs          [NEXT]
Micro-PRD 05: Tech Sheet          [PENDING]
Micro-PRD 06: Workflow Approval   [PENDING]
```

**Timeline:** MVP target ~31/01/2026

---
**Last Updated:** 2026-01-14
**Current Phase:** Micro-PRD 04 (Async Jobs)
