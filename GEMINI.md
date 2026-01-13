# Frida Orchestrator - Backend Context

## Project Status
**Version:** 0.5.1
**Last Updated:** 2026-01-13
**Testing Status:** 64% Complete (16/25 tests passing)
**Development Progress:** 45% (Micro-PRD 02 Complete)
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
│   │   ├── permissions.py      # RBAC decorators (@require_admin)
│   │   └── supabase.py         # JWT validation + AuthUser model
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py       # Gemini Vision + Structured Output
│   │   ├── background_remover.py # rembg + Pillow composition
│   │   ├── tech_sheet.py       # Jinja2 logic
│   │   └── storage.py          # Supabase storage & audit
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                 # FastAPI entry point (Fail-Fast Startup)
│   ├── config.py               # Settings management
│   ├── database.py             # Supabase DB client (Users, Products, Images)
│   └── utils.py                # Helpers (Deep Validation, image manipulation)
├── SQL para o SUPABASE/        # Database Migration Scripts
│   ├── 01_create_users_table.sql
│   ├── 02_seed_admin_zero.sql
│   ├── 03_seed_team_members.sql
│   ├── 04_create_products.sql  # Workflow + RLS
│   └── 05_create_images.sql    # Image tracking + FK
├── venv/                       # Virtual environment (ignored by git)
├── .env                        # Environment variables (API Keys)
├── .env.example                # Template for env variables
├── requirements.txt            # Python dependencies
├── GEMINI.md                   # Project context for AI
├── CLAUDE.md                   # Context for Claude Code
├── FASE_DE_TESTES.md           # Testing protocols v0.5.0
└── README.md                   # Project documentation
```

## Database Schema & Migrations

### Users Table
-   `id` (UUID, PK): Matches Supabase Auth user ID.
-   `email` (TEXT, Unique)
-   `role` (TEXT): 'admin' | 'user'.
-   `name` (TEXT)

### Products Table (NEW)
-   `id` (UUID, PK)
-   `name` (TEXT)
-   `sku` (TEXT, Unique)
-   `category` (TEXT)
-   `status` (TEXT): draft, pending, approved, rejected, published.
-   `created_by` (UUID, FK -> users)

### Images Table (NEW)
-   `id` (UUID, PK)
-   `product_id` (UUID, FK -> products)
-   `type` (TEXT): original, segmented, processed.
-   `storage_path` (TEXT)
-   `quality_score` (INTEGER): 0-100.

## Implementation Details

### Image Processing Pipeline
1.  **Deep Validation:** Checks Magic Numbers and Pillow Integrity.
2.  **Classification:** Gemini 2.0 identifies category/style.
3.  **Product Creation:** Saves draft to `products` table.
4.  **Segmentation:** `rembg` removes background.
5.  **Composition:** `Pillow` applies #FFFFFF background and 1080x1080px resize.
6.  **Image Tracking:** Saves record to `images` table.
7.  **Output:** Base64 PNG + metadata + product_id.

### Service Pattern
- **ClassifierService**: temperature 0.1, response_schema for reliability.
- **BackgroundRemoverService**: U2NET model, async-friendly thread execution.
- **Auth Service**: Enforces database registration (HTTP 403 if user not in `users` table).
- **Permissions Module**: `@require_admin`, `@require_user` decorators.

### Critical Issue Resolution (RESOLVED)
**Issue:** `POST /process` returned `product_id: null` due to missing GRANTs for `service_role`.
**Fix:** Explicit `GRANT ALL` on `products`, `images`, and `users` tables to `service_role` in Supabase.

## Testing Protocol (v0.5.0)
- **16/25 Tests Passing**
- **Verified:** Health, Auth Dev Mode, Classification, Full Pipeline, Deep Security.
- **Pending:** Supabase Storage, Load Testing, Edge Cases.

## Roadmap: Micro-PRD 03 (Image Pipeline)
1. **Sharp.js / Advanced Composition:** Improved centering and soft shadows.
2. **Husk Layer:** Quality scoring (resolution, centering, background purity).
3. **Triple Storage:** Saving original, segmented, and processed versions.

## Common Tasks & Commands
- **Run Server:** `uvicorn app.main:app --reload --port 8000`
- **Health Check:** `curl http://localhost:8000/health`
- **Process Image:** `curl -X POST http://localhost:8000/process -F "file=@image.jpg"`