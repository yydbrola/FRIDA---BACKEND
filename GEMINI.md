# Frida Orchestrator - Backend Context

## Project Overview
**Frida Orchestrator** is a FastAPI-based backend service designed for the fashion industry (specifically bags, lunchboxes, and thermos). It serves as the intelligence core for the Frida platform, handling image processing, AI classification, and technical documentation generation.

### Key Capabilities
1.  **AI Classification:** Uses Google's Gemini API to classify product images by category (e.g., Bag, Lunchbox) and style (Sketch vs. Photo).
2.  **Image Processing:** Automated background removal using `rembg` (U2NET) and standardizing images with a pure white background using `Pillow`.
3.  **Tech Sheet Generation:** Generates premium technical data sheets (HTML/PDF) using Jinja2 templates and WeasyPrint.

## Tech Stack
-   **Runtime:** Python 3.12+
-   **Web Framework:** FastAPI
-   **Server:** Uvicorn
-   **AI Model:** Google Generative AI (Gemini)
-   **Image Logic:** `rembg` (Background Removal), `Pillow` (Manipulation)
-   **Templating:** Jinja2
-   **PDF Engine:** WeasyPrint
-   **Database/Storage:** Supabase (Client library included)

## Directory Structure
```
componentes/
├── app/
│   ├── services/
│   │   ├── classifier.py       # Gemini API integration
│   │   ├── background_remover.py # rembg integration
│   │   └── tech_sheet.py       # Jinja2 + WeasyPrint logic
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                 # FastAPI entry point & routes
│   ├── config.py               # Settings management
│   └── utils.py                # Helpers (validation, filenames)
├── venv/                       # Virtual environment
├── .env                        # Environment variables (API Keys)
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

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
Required environment variables:
-   `GEMINI_API_KEY`: API Key for Google Gemini.
-   `SUPABASE_URL` / `SUPABASE_KEY`: If database features are enabled.

### 3. Running the Server
```bash
# Development mode with hot-reload
uvicorn app.main:app --reload --port 8000
```
Server accessible at: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

## Key Implementation Details

### Service Pattern
Logic is strictly separated into the `app/services/` directory. `main.py` should only handle request parsing and response formatting, delegating complex logic to services.

### Initialization
Services (`ClassifierService`, `BackgroundRemoverService`) are initialized during the FastAPI `startup` event to preload models and validate configurations.

### Error Handling
-   Use `HTTPException` for expected API errors.
-   Global exception handlers catch unhandled errors to prevent server crashes.
-   `rembg` model download happens on the first run; timeouts should be handled gracefully.

## Common Tasks & Commands

**Run Linter/Formatter (if applicable):**
*Currently relying on standard Python tooling. Ensure PEP8 compliance.*

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
curl -X POST "http://localhost:8000/process" -F "file=@image.jpg"
```
