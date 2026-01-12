# Frida Orchestrator - Backend Context

## Project Overview
**Frida Orchestrator** is a FastAPI-based backend service designed for the fashion industry (specifically bags, lunchboxes, and thermos). It serves as the intelligence core for the Frida platform, handling image processing, AI classification, and technical documentation generation.

### Key Capabilities
1.  **AI Classification:** Uses Google's Gemini API with **Structured Output** to classify product images by category (e.g., Bag, Lunchbox) and style (Sketch vs. Photo) with 100% JSON reliability.
2.  **Image Processing:** Automated background removal using `rembg` (U2NET) and standardizing images with a pure white background using `Pillow`.
3.  **Tech Sheet Generation:** Generates premium technical data sheets (HTML/JSON) using Jinja2 templates.
4.  **Audit Storage:** Persists processed images and tech sheets to Supabase for enterprise audit trail.
5.  **Secure Authentication:** Validates Supabase JWT tokens to identify users.
6.  **RBAC (Role-Based Access Control):** Enforces permissions based on user roles (`admin`, `user`) stored in Supabase.

## Tech Stack
-   **Runtime:** Python 3.12+
-   **Web Framework:** FastAPI (optimized with Sync Routes for CPU-bound tasks)
-   **Server:** Uvicorn
-   **AI Model:** Google Generative AI (Gemini 1.5 Flash + Structured Output)
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
│   │   └── supabase.py         # JWT validation logic
│   ├── services/
│   │   ├── classifier.py       # Gemini API integration (Structured Output)
│   │   ├── background_remover.py # rembg integration
│   │   ├── tech_sheet.py       # Jinja2 logic
│   │   └── storage.py          # Supabase storage & audit
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                 # FastAPI entry point (Fail-Fast Startup)
│   ├── config.py               # Settings management
│   ├── database.py             # Supabase DB client (Users table lookup)
│   └── utils.py                # Helpers (Deep Validation, image manipulation)
├── SQL para o SUPABASE/        # Database Migration Scripts
│   ├── 01_create_users_table.sql
│   ├── 02_seed_admin_zero.sql
│   └── 03_seed_team_members.sql
├── venv/                       # Virtual environment (ignored by git)
├── .env                        # Environment variables (API Keys)
├── .env.example                # Template for env variables
├── requirements.txt            # Python dependencies
├── GEMINI.md                   # Project context for AI
├── CLAUDE.md                   # Context for Claude Code
├── FASE_DE_TESTES.md           # Testing protocols
└── README.md                   # Project documentation
```

## Database Schema & Migrations
Located in `SQL para o SUPABASE/`:
1.  **`01_create_users_table.sql`**: Creates `users` table for RBAC.
2.  **`02_seed_admin_zero.sql`**: Inserts the initial Admin user.
3.  **`03_seed_team_members.sql`**: Inserts team members.

**Users Table Schema:**
-   `id` (UUID, Primary Key)
-   `email` (VARCHAR, Unique)
-   `name` (VARCHAR)
-   `role` (VARCHAR: 'admin' | 'user')
-   `created_at` (TIMESTAMPTZ)

## Development Workflow

### 1. Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (.env)
**Required:**
-   `GEMINI_API_KEY`: API Key for Google Gemini (Obrigatório para o startup).
-   `AUTH_ENABLED`: `true` or `false` (Dev mode).

**Optional (for Prod/Audit/DB):**
-   `SUPABASE_URL`: Supabase project URL
-   `SUPABASE_KEY`: Supabase anon/service key
-   `SUPABASE_JWT_SECRET`: Secret for validating tokens (Required if AUTH_ENABLED=true)

### 3. Running the Server
```bash
# Development mode with hot-reload
uvicorn app.main:app --reload --port 8000
```
Server accessible at: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

## Key Implementation Details

### Service Pattern
Logic is strictly separated into the `app/services/` directory. `main.py` handles request parsing and response formatting, delegating complex logic to specific services.

### Image Processing Pipeline
1.  **Input:** Multipart Form Data (Image + Options).
2.  **Authentication:** Validates JWT (if enabled) and extracts `user_id`.
3.  **Authorization:** Checks user role via `app/database.py` (if endpoint requires specific role).
4.  **Deep Validation:** Checks **Magic Numbers** (file signatures) and **Pillow Integrity** to prevent spoofing.
5.  **Classification:** Gemini identifies category/style using Structured Output (native JSON).
6.  **Segmentation:** `rembg` removes the background.
7.  **Composition:** `Pillow` applies a #FFFFFF (pure white) background.
8.  **Output:** Base64 encoded string of the processed image.
9.  **Audit (Optional):** `StorageService` persists image and metadata to Supabase.

### Reliability & Performance
-   **Fail-Fast Startup:** The API will NOT start if `GEMINI_API_KEY` is missing or if critical services (`rembg`, `Classifier`, `TechSheet`) fail to initialize.
-   **CPU-Bound Optimization:** Processing routes use `def` instead of `async def` to allow FastAPI to manage them in a separate thread pool, preventing Event Loop blocking during heavy image manipulation.
-   **Structured AI:** Native Gemini `response_schema` ensures the AI always returns valid, typed JSON, eliminating the need for Regex parsing.
-   **Authentication Module:** `app/auth/` handles JWT validation. In Dev Mode (`AUTH_ENABLED=false`), returns a fake `user_id` to simplify testing.
-   **RBAC Module:** `app/auth/permissions.py` provides decorators like `@require_admin` to protect sensitive endpoints.

### Health Check
-   Accessible at `/health`.
-   Returns detailed status of each service (`classifier`, `background_remover`, `tech_sheet`, `storage`, `supabase`).
-   Includes a `ready` flag (true only if all critical services are operational).

## Testing Protocol (v0.5.0)

See `FASE_DE_TESTES.md` for full details. Validated capabilities include:
-   **Health & Connectivity:** Root, Ping, Health checks.
-   **Authentication:** Dev mode (bypass) vs Prod mode (JWT validation).
-   **Classification:** Correctly identifies Bag/Lunchbox/Bottle and Sketch/Photo.
-   **Security:** Rejects fake files (text disguised as jpg) and corrupted images via Deep Validation.
-   **Formats:** Supports PNG, JPEG, and WebP.
-   **Process:** End-to-end pipeline (Upload -> Classify -> Remove BG -> Tech Sheet -> Return).

## Common Tasks & Commands

**Add New Dependency:**
```bash
pip install <package>
pip freeze > requirements.txt
```

**Test Endpoints (cURL):**
```bash
# Health Check
curl http://localhost:8000/health

# Process Image
curl -X POST "http://localhost:8000/process" \
     -F "file=@image.jpg" \
     -F "gerar_ficha=true"
```
