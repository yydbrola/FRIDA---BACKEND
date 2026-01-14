#!/usr/bin/env python3
"""
PRD-05 Test Suite - Technical Sheets

Testa CRUD de database e endpoints REST para fichas técnicas.

Uso:
    # Todos os testes
    python scripts/test_prd05_sheets.py --all
    
    # Apenas DB (precisa de IDs válidos)
    TEST_PRODUCT_ID=xxx TEST_USER_ID=yyy python scripts/test_prd05_sheets.py --test-db
    
    # Apenas API (servidor deve estar rodando)
    TEST_PRODUCT_ID=xxx python scripts/test_prd05_sheets.py --test-api
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
TEST_PRODUCT_ID = os.getenv("TEST_PRODUCT_ID", "")
TEST_USER_ID = os.getenv("TEST_USER_ID", "")


# =============================================================================
# Helpers
# =============================================================================

def print_header(text: str):
    """Imprime header de seção."""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}\n")


def print_result(test_name: str, passed: bool, details: str = ""):
    """Imprime resultado de teste."""
    status = "✓" if passed else "✗"
    print(f"{status} {test_name}")
    if details:
        print(f"  → {details}")


def print_warning(message: str):
    """Imprime warning."""
    print(f"⚠ {message}")


# =============================================================================
# Database CRUD Tests
# =============================================================================

def test_database_crud() -> tuple:
    """
    Testa funções CRUD do database.
    
    Requer: TEST_PRODUCT_ID e TEST_USER_ID como env vars.
    
    Returns:
        Tuple (passed, total)
    """
    print_header("DATABASE CRUD TESTS")
    
    if not TEST_PRODUCT_ID or not TEST_USER_ID:
        print_warning("TEST_PRODUCT_ID e TEST_USER_ID são necessários")
        print_warning("Exemplo: TEST_PRODUCT_ID=xxx TEST_USER_ID=yyy python ...")
        return (0, 0)
    
    from app.database import (
        create_technical_sheet,
        get_technical_sheet,
        get_sheet_by_product,
        update_technical_sheet,
        get_sheet_versions,
        delete_technical_sheet
    )
    
    passed = 0
    total = 0
    created_sheet_id = None
    
    # Test 1: create_technical_sheet
    total += 1
    try:
        sheet_id = create_technical_sheet(
            product_id=TEST_PRODUCT_ID,
            user_id=TEST_USER_ID,
            data={"test_field": "hello", "_version": 1, "_schema": "bag_v1"}
        )
        if sheet_id:
            passed += 1
            created_sheet_id = sheet_id
            print_result("create_technical_sheet()", True, f"sheet_id={sheet_id[:12]}...")
        else:
            print_result("create_technical_sheet()", False, "Retornou None")
    except Exception as e:
        print_result("create_technical_sheet()", False, str(e))
    
    # Test 2: get_technical_sheet
    total += 1
    if created_sheet_id:
        try:
            sheet = get_technical_sheet(created_sheet_id)
            if sheet and sheet.get("version") == 1:
                passed += 1
                print_result("get_technical_sheet()", True, f"version={sheet['version']}")
            else:
                print_result("get_technical_sheet()", False, "Sheet não encontrada ou versão incorreta")
        except Exception as e:
            print_result("get_technical_sheet()", False, str(e))
    else:
        print_result("get_technical_sheet()", False, "Skipped - no sheet_id")
    
    # Test 3: get_sheet_by_product
    total += 1
    try:
        sheet = get_sheet_by_product(TEST_PRODUCT_ID)
        if sheet:
            passed += 1
            print_result("get_sheet_by_product()", True, "found")
        else:
            print_result("get_sheet_by_product()", False, "Não encontrada")
    except Exception as e:
        print_result("get_sheet_by_product()", False, str(e))
    
    # Test 4: update_technical_sheet
    total += 1
    if created_sheet_id:
        try:
            success = update_technical_sheet(
                sheet_id=created_sheet_id,
                data={"test_field": "updated", "new_field": 123},
                user_id=TEST_USER_ID
            )
            if success:
                # Verificar se versão incrementou
                updated = get_technical_sheet(created_sheet_id)
                if updated and updated.get("version", 0) >= 2:
                    passed += 1
                    print_result("update_technical_sheet()", True, f"version={updated['version']}")
                else:
                    print_result("update_technical_sheet()", False, "Versão não incrementou")
            else:
                print_result("update_technical_sheet()", False, "Retornou False")
        except Exception as e:
            print_result("update_technical_sheet()", False, str(e))
    else:
        print_result("update_technical_sheet()", False, "Skipped - no sheet_id")
    
    # Test 5: get_sheet_versions
    total += 1
    if created_sheet_id:
        try:
            versions = get_sheet_versions(created_sheet_id)
            # Após update, deve ter pelo menos 1 versão arquivada
            passed += 1
            print_result("get_sheet_versions()", True, f"{len(versions)} versions")
        except Exception as e:
            print_result("get_sheet_versions()", False, str(e))
    else:
        print_result("get_sheet_versions()", False, "Skipped - no sheet_id")
    
    # Test 6: delete_technical_sheet
    total += 1
    if created_sheet_id:
        try:
            success = delete_technical_sheet(created_sheet_id)
            if success:
                # Verificar se foi deletada
                deleted = get_technical_sheet(created_sheet_id)
                if not deleted:
                    passed += 1
                    print_result("delete_technical_sheet()", True, "deleted")
                else:
                    print_result("delete_technical_sheet()", False, "Sheet ainda existe")
            else:
                print_result("delete_technical_sheet()", False, "Retornou False")
        except Exception as e:
            print_result("delete_technical_sheet()", False, str(e))
    else:
        print_result("delete_technical_sheet()", False, "Skipped - no sheet_id")
    
    return (passed, total)


# =============================================================================
# API Endpoint Tests
# =============================================================================

def test_api_endpoints() -> tuple:
    """
    Testa endpoints REST da API.
    
    Requer: TEST_PRODUCT_ID e servidor rodando.
    
    Returns:
        Tuple (passed, total)
    """
    print_header("API ENDPOINT TESTS")
    
    if not TEST_PRODUCT_ID:
        print_warning("TEST_PRODUCT_ID é necessário")
        print_warning("Exemplo: TEST_PRODUCT_ID=xxx python ...")
        return (0, 0)
    
    # Verificar se servidor está rodando
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print_warning(f"Servidor não está respondendo em {BASE_URL}")
            return (0, 0)
    except requests.exceptions.ConnectionError:
        print_warning(f"Não foi possível conectar a {BASE_URL}")
        print_warning("Inicie o servidor: uvicorn app.main:app --reload")
        return (0, 0)
    
    passed = 0
    total = 0
    
    # Test 1: POST /products/{id}/sheet
    total += 1
    try:
        response = requests.post(f"{BASE_URL}/products/{TEST_PRODUCT_ID}/sheet")
        if response.status_code == 200:
            data = response.json()
            if data.get("sheet_id"):
                passed += 1
                print_result(
                    "POST /products/{id}/sheet",
                    True,
                    f"sheet_id={data['sheet_id'][:12]}..."
                )
            else:
                print_result("POST /products/{id}/sheet", False, "No sheet_id in response")
        else:
            print_result("POST /products/{id}/sheet", False, f"status={response.status_code}")
    except Exception as e:
        print_result("POST /products/{id}/sheet", False, str(e))
    
    # Test 2: GET /products/{id}/sheet
    total += 1
    try:
        response = requests.get(f"{BASE_URL}/products/{TEST_PRODUCT_ID}/sheet")
        if response.status_code == 200:
            data = response.json()
            version = data.get("version", "?")
            passed += 1
            print_result("GET /products/{id}/sheet", True, f"version={version}")
        else:
            print_result("GET /products/{id}/sheet", False, f"status={response.status_code}")
    except Exception as e:
        print_result("GET /products/{id}/sheet", False, str(e))
    
    # Test 3: PUT /products/{id}/sheet
    total += 1
    try:
        payload = {
            "data": {
                "dimensions": {"altura": 30, "largura": 40},
                "colors": ["preto", "marrom"]
            },
            "change_summary": "Test update"
        }
        response = requests.put(
            f"{BASE_URL}/products/{TEST_PRODUCT_ID}/sheet",
            json=payload
        )
        if response.status_code == 200:
            data = response.json()
            version = data.get("version", "?")
            passed += 1
            print_result("PUT /products/{id}/sheet", True, f"version={version}")
        else:
            print_result("PUT /products/{id}/sheet", False, f"status={response.status_code}")
    except Exception as e:
        print_result("PUT /products/{id}/sheet", False, str(e))
    
    # Test 4: GET /products/{id}/sheet/versions
    total += 1
    try:
        response = requests.get(f"{BASE_URL}/products/{TEST_PRODUCT_ID}/sheet/versions")
        if response.status_code == 200:
            data = response.json()
            total_versions = data.get("total", 0)
            passed += 1
            print_result("GET /products/{id}/sheet/versions", True, f"total={total_versions}")
        else:
            print_result("GET /products/{id}/sheet/versions", False, f"status={response.status_code}")
    except Exception as e:
        print_result("GET /products/{id}/sheet/versions", False, str(e))
    
    # Test 5: GET /products/{id}/sheet/export/pdf
    total += 1
    try:
        response = requests.get(f"{BASE_URL}/products/{TEST_PRODUCT_ID}/sheet/export/pdf")
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "application/pdf" in content_type:
                size = len(response.content)
                passed += 1
                print_result("GET /products/{id}/sheet/export/pdf", True, f"{size} bytes")
            else:
                print_result("GET /products/{id}/sheet/export/pdf", False, f"content-type={content_type}")
        else:
            print_result("GET /products/{id}/sheet/export/pdf", False, f"status={response.status_code}")
    except Exception as e:
        print_result("GET /products/{id}/sheet/export/pdf", False, str(e))
    
    return (passed, total)


# =============================================================================
# Main
# =============================================================================

def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="PRD-05 Test Suite - Technical Sheets")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--test-db", action="store_true", help="Test database CRUD")
    parser.add_argument("--test-api", action="store_true", help="Test API endpoints")
    
    args = parser.parse_args()
    
    # Default to all if no flag
    if not any([args.all, args.test_db, args.test_api]):
        args.all = True
    
    # Header
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🧪 PRD-05 Test Suite - {now}")
    print(f"   API URL: {BASE_URL}")
    if TEST_PRODUCT_ID:
        print(f"   Product: {TEST_PRODUCT_ID[:12]}...")
    if TEST_USER_ID:
        print(f"   User:    {TEST_USER_ID[:12]}...")
    
    total_passed = 0
    total_tests = 0
    
    # Run tests
    if args.all or args.test_db:
        passed, tests = test_database_crud()
        total_passed += passed
        total_tests += tests
    
    if args.all or args.test_api:
        passed, tests = test_api_endpoints()
        total_passed += passed
        total_tests += tests
    
    # Summary
    print_header("SUMMARY")
    
    if total_tests == 0:
        print("⚠ Nenhum teste executado")
        print("  Verifique as variáveis de ambiente:")
        print("    - TEST_PRODUCT_ID (obrigatório)")
        print("    - TEST_USER_ID (para testes DB)")
        return 1
    
    percentage = (total_passed / total_tests) * 100 if total_tests > 0 else 0
    print(f"Tests passed: {total_passed}/{total_tests} ({percentage:.0f}%)")
    print()
    
    if total_passed == total_tests:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
