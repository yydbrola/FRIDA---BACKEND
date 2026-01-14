# CHANGELOG

All notable changes to the Frida Orchestrator project are documented in this file.

---

## [0.5.3] - 2026-01-13

### Added
- **ImageComposer Service** (`app/services/image_composer.py`): Advanced image composition with white background, 85% product coverage, soft drop shadow, and 1200x1200px output
- **HuskLayer Service** (`app/services/husk_layer.py`): Quality validation system scoring 0-100 (resolution 30pts, centering 40pts, background purity 30pts)
- **ImagePipelineSync Service** (`app/services/image_pipeline.py`): Triple storage orchestration (original -> segmented -> processed)
- **DoS Protection**: File size limit (10MB) and dimension limit (8000px) validation
- **RLS Policies**: Dual mode support (dev + prod) with 8 policies (`06_rls_dual_mode.sql`)
- **Test Script**: `scripts/test_prd03_complete.py` with 61 comprehensive tests

### Fixed

#### Transaction Rollback (Commit: `b274cb0`)
**File:** `app/services/image_pipeline.py`
**Severity:** High

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

#### Resource Leak Fix (Commit: `1642bb0`)
**File:** `app/services/image_composer.py`
**Severity:** High

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

#### DoS Protection (Commit: `08a6de1`)
**Files:** `app/config.py`, `app/services/image_pipeline.py`
**Severity:** Critical

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

#### API Response Fields (Commit: `01b1d66`)
**File:** `app/main.py`
**Severity:** Medium

**Problem:** `imagem_base64` field was overloaded with both base64 data and storage URLs, causing frontend parsing issues.

**Solution:** Separated into two distinct fields:
- `imagem_base64`: Base64-encoded image data (fallback mode)
- `imagem_url`: Storage URL when pipeline succeeds

---

## [0.5.2] - 2026-01-13

### Fixed

#### Thread-Safe Client Loading
**File:** `app/services/image_pipeline.py`
**Severity:** Medium

**Problem:** Supabase client loading had race condition in concurrent requests.

**Solution:** Implemented double-check locking pattern for thread-safe lazy initialization.

#### rembg Error Handling
**File:** `app/services/image_pipeline.py`
**Severity:** Medium

**Problem:** rembg errors were not properly caught and logged.

**Solution:** Specific exception handling for rembg with detailed error messages and proper cleanup.

#### RBAC Implementation Refactor
**File:** `app/auth/permissions.py`

**Problem:** RBAC was implemented with decorators which didn't integrate well with FastAPI.

**Solution:** Refactored from decorators to Dependency Factory pattern:
```python
from app.auth.permissions import require_admin, require_user, require_any, require_role

# Admin only
@app.delete("/users/{id}")
def delete_user(user: AuthUser = Depends(require_admin)):
    ...

# Any authenticated
@app.get("/products")
def list_products(user: AuthUser = Depends(require_any)):
    ...

# Custom roles
@app.post("/moderate")
def moderate(user: AuthUser = Depends(require_role("admin", "moderator"))):
    ...
```

---

## [0.5.1] - 2026-01-12

### Added
- **Product Enums** (`config.py`): Centralized enums for type safety
  - `ProductCategory`: bolsa, lancheira, garrafa_termica, desconhecido
  - `ProductStyle`: sketch, foto, desconhecido
  - `ProductStatus`: draft, pending, approved, rejected, published
  - `ImageType`: original, segmented, processed

### Fixed

#### JSON Parsing Bug
**File:** `utils.py:49-114`
**Severity:** High

**Problem:** The regex `r'\{[^{}]*\}'` didn't capture nested JSON objects.

```python
# Before (BROKEN):
match = re.search(r'\{[^{}]*\}', texto)
# Failed on: {"nome": "Bolsa", "dimensoes": {"altura": "30cm"}}
# Returned only: {"altura": "30cm"}  <- WRONG!
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

---

## [0.5.0] - 2026-01-12

### Added
- **AuthUser Model**: Full user object with `user_id`, `email`, `role`, `name`
- **Product Management Endpoints**: `GET /products`, `GET /products/{id}`
- **Products Table**: Product catalog with workflow (draft->pending->approved->rejected->published)
- **Images Table**: Image tracking linked to products with cascade delete
- **RBAC System**: Role-based access control with `require_admin`, `require_user`, `require_any`

---

## Critical Issue Resolution: Micro-PRD 02 Blocker

### Issue Summary
**Status:** RESOLVED (2026-01-13)
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

-- Critical Insight: bypassrls != bypass GRANT
-- service_role can ignore RLS, but still needs GRANT on tables
```

### Investigation Timeline
Hypotheses tested (chronological order):

1. Tables don't exist -> Discarded (tables existed)
2. Invalid FK -> Discarded (dev user inserted)
3. RLS blocking -> Discarded (disabled, error persisted)
4. Missing GRANT for anon -> Discarded (applied, error persisted)
5. Singleton caching -> Fixed but error persisted (red herring)
6. Anon key vs service_role -> Correct approach, error persisted
7. **service_role missing GRANT -> ROOT CAUSE**

### Solution Applied
```sql
-- Critical fix:
GRANT ALL ON public.products TO service_role;
GRANT ALL ON public.images TO service_role;
GRANT ALL ON public.users TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

### Code Modifications
- **app/database.py:** Singleton removed, debug prints added, new client created per call
- **.env:** service_role key verified and configured
- **Supabase Database:** GRANTs applied to service_role

### Validation Results
```bash
# Test command:
curl -X POST http://localhost:8000/process -F "file=@bolsa_teste.jpg"

# Response:
{
  "product_id": "291c7351-136b-477f-9505-92b7c31dfef6",  # SUCCESS!
  "categoria": "bolsa",
  "estilo": "foto",
  "confianca": 0.95
}
```

```sql
-- Database verification:
SELECT * FROM products WHERE id = '291c7351-136b-477f-9505-92b7c31dfef6';
-- 1 row returned

SELECT * FROM images WHERE product_id = '291c7351-136b-477f-9505-92b7c31dfef6';
-- 1 row returned
```

### Lessons Learned

1. **rolbypassrls != superuser**: Role with RLS bypass still requires explicit GRANTs
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

---

## Development Roadmap History

### Completed Micro-PRDs

#### Micro-PRD 01: Authentication & Users (100%)
**Completed:** 2026-01-12
- JWT authentication with Supabase Auth
- RBAC with admin/user roles
- User management with RLS policies
- Dev mode for local development

#### Micro-PRD 02: Product Persistence (100%)
**Completed:** 2026-01-13
- Products table with workflow (draft->pending->approved->rejected->published)
- Images table with cascade delete
- Database CRUD operations
- service_role GRANT resolution

#### Micro-PRD 03: Image Pipeline (100%)
**Completed:** 2026-01-13
**Implemented by:** Antigravity (Google DeepMind)
- **ImageComposer Service:** White background composition with shadow (1200x1200px, 85% coverage)
- **HuskLayer Service:** Quality validation (resolution + centering + background purity = 0-100 score)
- **ImagePipelineSync Service:** Triple storage orchestration (original -> segmented -> processed)
- **RLS Policies:** Dual mode support (dev + prod) with 8 policies
- **Test Script:** Local pipeline testing (`scripts/test_pipeline.py`)
- **Integration:** `/process` endpoint updated with `quality_score` and `images` in response

---

## Gemini Schema Compatibility Note

**Reference:** Issue fixed in commit `fde4658` - "fix: remove unsupported validation keywords from Gemini schema"

When modifying `CLASSIFICATION_SCHEMA` in `classifier.py`, note that Gemini's schema validation differs from JSON Schema.

**Unsupported Keywords:**
- `minimum` / `maximum` (for numbers)
- `minLength` / `maxLength` (for strings)
- `pattern` (regex patterns)

**Workaround:** Use `description` to document constraints instead.

```python
# Does NOT work
"confianca": {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0
}

# Works correctly
"confianca": {
    "type": "number",
    "description": "Confidence level between 0.0 and 1.0"
}
```
