# Test Documentation

This file contains comprehensive test documentation for the Frida Orchestrator project.

---

## Quick Summary

| Suite | Tests | Status | Script |
|-------|-------|--------|--------|
| Core API (FASE_DE_TESTES) | 16/25 | 64% | Manual curl commands |
| Micro-PRD 03 | 61/61 | 100% | `scripts/test_prd03_complete.py` |
| Pipeline Validation | 4/4 | 100% | `scripts/test_pipeline.py` |

---

## Test Commands

```bash
# API health check
curl http://localhost:8000/health

# Classification test
curl -X POST http://localhost:8000/classify -F "file=@test.jpg"

# Full processing test
curl -X POST http://localhost:8000/process -F "file=@image.jpg" -F "gerar_ficha=true"

# PRD 03 Test Suite (61 tests)
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

---

## Test Files

| File | Description |
|------|-------------|
| `scripts/test_prd03_complete.py` | Complete PRD 03 test suite (61 tests) |
| `scripts/test_pipeline.py` | Local pipeline testing |
| `test_images/bolsa_teste.png` | Test input image (800x600px) |
| `test_images/bolsa_teste_segmented.png` | Segmented output |
| `test_images/bolsa_teste_processed.png` | Processed output (1200x1200px) |

---

## Core API Tests (FASE_DE_TESTES.md)

**Overall Progress:** 16/25 tests (64% complete)

### Completed Test Categories

| Category | Tests | Status |
|----------|-------|--------|
| Health & Connectivity | 3/3 | PASS |
| Authentication Dev Mode | 2/2 | PASS |
| Image Classification | 3/3 | PASS |
| Complete Processing | 4/4 | PASS |
| Image Validation & Security | 4/4 | PASS |

### Pending Test Categories

| Category | Tests | Blocker |
|----------|-------|---------|
| Storage (Supabase) | 0/3 | Requires Supabase configuration |
| Errors & Edge Cases | 0/5 | File size limits, concurrent requests |
| Configuration & Startup | 0/2 | Missing API key scenarios |

---

## Micro-PRD 03 Test Suite

**Test Date:** 2026-01-13
**Test Script:** `scripts/test_prd03_complete.py`
**Result:** 61/61 tests passing (100%)

### Test Categories Overview

| Category | Tests | Result |
|----------|-------|--------|
| ImageComposer - White Background Composition | 12/12 | 100% |
| HuskLayer - Quality Validation | 13/13 | 100% |
| ImagePipeline - Structures & Configuration | 12/12 | 100% |
| Config - DoS Protection | 6/6 | 100% |
| Edge Cases | 8/8 | 100% |
| Integration - Composer -> Validator Flow | 7/7 | 100% |
| Integration - rembg (Segmentation) | 3/3 | 100% |
| **TOTAL** | **61/61** | **100%** |

---

### ImageComposer Tests (12 tests)

```
Configuration: TARGET_SIZE = 1200
Configuration: PRODUCT_COVERAGE = 0.85
Configuration: BACKGROUND_COLOR = (255, 255, 255)
Basic composition: returns image
Basic composition: RGB mode
Basic composition: dimension 1200x1200
Composition: corners are pure white
compose_from_bytes: returns bytes
compose_from_bytes: valid PNG
Custom size: 800x800
RGB image: raises ValueError
Transparent image: returns white canvas
```

---

### HuskLayer Tests (13 tests)

```
Total score = 100
Approval threshold = 80
Perfect image: score >= 80
Perfect image: passed = True
Low resolution: resolution score < 30
Off-center product: centering score < 40
Impure background: background score < 30
QualityReport.to_dict: contains 'score'
QualityReport.to_dict: contains 'passed'
QualityReport.to_dict: contains 'details'
validate_from_bytes: returns QualityReport
All white image: centering = 0
Very small product: coverage TOO_SMALL
```

---

### ImagePipeline Tests (12 tests)

```
BUCKETS: contains 'original'
BUCKETS: contains 'segmented'
BUCKETS: contains 'processed'
Bucket original = 'raw'
Bucket processed = 'processed-images'
PipelineResult: success attribute
PipelineResult: product_id attribute
PipelineResult: images attribute
PipelineResult.to_dict: serializable
PipelineResult.to_dict: contains success
ImagePipelineSync: instantiation
ImagePipelineSync: has _client_lock
```

---

### DoS Protection Tests (6 tests)

```
MAX_FILE_SIZE_MB configured
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES configured
MAX_FILE_SIZE_BYTES = 10MB in bytes
MAX_IMAGE_DIMENSION configured
MAX_IMAGE_DIMENSION = 8000
```

---

### Edge Cases Tests (8 tests)

```
Corrupted bytes: raises exception
Empty bytes: raises exception
1x1 image: doesn't crash
1x1 image: low score
Dimension limit: configured
Partial transparency: processes OK
Grayscale image: processes OK
Palette image: processes OK
```

---

### Integration Tests (10 tests)

```
Flow: composition returns image
Flow: validation returns report
Flow: composed image passes (score >= 80)
Flow: resolution OK (30 pts)
Flow: pure background (30 pts)
Bytes flow: works end-to-end
Multiple flow: all pass
rembg: import OK
rembg: returns bytes
rembg: returns valid PNG
```

---

### Error Cases Tests (Original Script)

```
Corrupted file: Exception caught (UnidentifiedImageError)
Very small image (1x1): Low score as expected (0/100)
Fully transparent image: Returned white canvas (1200x1200)
Empty bytes: Exception caught (UnidentifiedImageError)
```

---

### Full Pipeline Test (Real Image)

**Test Image:** `test_images/bolsa_teste.png` (800x600, 4KB)

**Pipeline Stages:**
1. Stage 1: Segmentation (rembg) -> 20,690 bytes
2. Stage 2: Composition (ImageComposer) -> 1200x1200px
3. Stage 3: Validation (HuskLayer) -> Score 100/100

**Quality Report:**
- Resolution: 30/30 points (OK: 1200x1200px)
- Centering: 40/40 points (Coverage: 84.7%, Offset: 0.7%)
- Background Purity: 30/30 points (Delta: 0.0 - PURE_WHITE)

**Result:** PIPELINE APPROVED - Image ready for production!

---

## Coverage by Component

### Services Coverage

| Service | Unit Tests | Integration Tests | Status |
|---------|------------|-------------------|--------|
| ImageComposer | 12 | 7 | Full |
| HuskLayer | 13 | 7 | Full |
| ImagePipelineSync | 12 | 3 | Full |
| ClassifierService | 3 | - | Partial |
| BackgroundRemoverService | - | 3 | Integration only |
| TechSheetService | - | - | Not tested |
| StorageService | - | - | Pending Supabase |

### Config Coverage

| Config | Tests | Status |
|--------|-------|--------|
| DoS Protection | 6 | Full |
| Product Enums | - | Not tested |
| Environment Variables | - | Pending |

---

## Known Test Gaps

### High Priority
1. **Storage Tests (Category 6):** Requires Supabase configuration
2. **Rate Limiting Tests:** Not implemented (rate limiting not implemented)
3. **TechSheetService Tests:** No unit or integration tests

### Medium Priority
4. **File Size Limits:** Edge cases for >10MB files
5. **Concurrent Requests:** Load testing not performed
6. **Invalid Content-Type:** Security edge cases

### Low Priority
7. **Model Caching:** rembg U2NET model download behavior
8. **Image Generation:** GEMINI_MODEL_IMAGE_GEN not tested (experimental)

---

## Running Tests in CI/CD

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run PRD 03 tests
        run: python scripts/test_prd03_complete.py
```

---

**Last Updated:** 2026-01-13
**See Also:** FASE_DE_TESTES.md for detailed test protocols
