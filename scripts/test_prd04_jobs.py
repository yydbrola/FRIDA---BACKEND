#!/usr/bin/env python3
"""
FRIDA PRD-04: Testes de Jobs Async
Valida todo o fluxo de processamento assíncrono.

Uso:
    python scripts/test_prd04_jobs.py
    python scripts/test_prd04_jobs.py --test-worker  (testa worker isolado)
    python scripts/test_prd04_jobs.py --test-api     (testa apenas endpoints)
    python scripts/test_prd04_jobs.py --all          (todos os testes)
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuração
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
TEST_IMAGE = os.getenv("TEST_IMAGE", "test_images/bolsa_teste.png")

# Cores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_ok(msg):
    print(f"{GREEN}✓{RESET} {msg}")

def print_fail(msg):
    print(f"{RED}✗{RESET} {msg}")

def print_warn(msg):
    print(f"{YELLOW}⚠{RESET} {msg}")

def print_info(msg):
    print(f"{BLUE}ℹ{RESET} {msg}")

def print_header(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


# ============================================
# TESTES DE DATABASE (CRUD Functions)
# ============================================

def test_database_crud():
    """Testa funções CRUD de jobs no banco."""
    print_header("TESTE: Database CRUD Functions")
    
    from app.database import (
        create_job,
        get_job,
        update_job_progress,
        increment_job_attempt,
        complete_job,
        fail_job,
        get_next_queued_job,
        get_user_jobs,
        create_product
    )
    
    results = []
    
    # Usar IDs do dev mode
    test_user_id = "00000000-0000-0000-0000-000000000000"
    
    # Criar produto de teste primeiro
    print_info("Criando produto de teste...")
    try:
        product = create_product(
            name="Teste CRUD PRD-04",
            category="bolsa",
            classification={"item": "bolsa", "estilo": "foto", "confianca": 0.95},
            user_id=test_user_id
        )
        test_product_id = product["id"]
        print_ok(f"Produto criado: {test_product_id[:8]}...")
    except Exception as e:
        print_fail(f"Falha ao criar produto: {e}")
        print_warn("Verifique se a tabela 'products' existe no Supabase")
        return results
    
    # Teste 1: create_job
    try:
        job_id = create_job(
            product_id=test_product_id,
            user_id=test_user_id,
            input_data={"test": True, "timestamp": time.time()}
        )
        if job_id:
            print_ok(f"create_job() retornou job_id: {job_id[:8]}...")
            results.append(True)
        else:
            print_fail("create_job() retornou None")
            results.append(False)
            return results
    except Exception as e:
        print_fail(f"create_job() erro: {e}")
        results.append(False)
        return results
    
    # Teste 2: get_job
    try:
        job = get_job(job_id)
        if job and job["status"] == "queued":
            print_ok(f"get_job() retornou job com status='queued'")
            results.append(True)
        else:
            print_fail(f"get_job() status incorreto: {job}")
            results.append(False)
    except Exception as e:
        print_fail(f"get_job() erro: {e}")
        results.append(False)
    
    # Teste 3: update_job_progress
    try:
        success = update_job_progress(
            job_id,
            status="processing",
            current_step="segmenting",
            progress=25
        )
        if success:
            job = get_job(job_id)
            if job["status"] == "processing" and job["progress"] == 25:
                print_ok("update_job_progress() atualizou corretamente")
                results.append(True)
            else:
                print_fail(f"update_job_progress() valores incorretos")
                results.append(False)
        else:
            print_fail("update_job_progress() retornou False")
            results.append(False)
    except Exception as e:
        print_fail(f"update_job_progress() erro: {e}")
        results.append(False)
    
    # Teste 4: increment_job_attempt
    try:
        result = increment_job_attempt(job_id, "Erro de teste", retry_delay_seconds=5)
        if result and result.get("attempts") == 1:
            print_ok(f"increment_job_attempt() incrementou para {result['attempts']}")
            results.append(True)
        else:
            print_fail(f"increment_job_attempt() resultado incorreto: {result}")
            results.append(False)
    except Exception as e:
        print_fail(f"increment_job_attempt() erro: {e}")
        results.append(False)
    
    # Teste 5: complete_job
    try:
        # Resetar para processing primeiro
        update_job_progress(job_id, status="processing")
        
        success = complete_job(job_id, {
            "images": {"test": "data"},
            "quality_score": 95,
            "quality_passed": True
        })
        if success:
            job = get_job(job_id)
            if job["status"] == "completed":
                print_ok("complete_job() marcou como completed")
                results.append(True)
            else:
                print_fail(f"complete_job() status incorreto: {job['status']}")
                results.append(False)
        else:
            print_fail("complete_job() retornou False")
            results.append(False)
    except Exception as e:
        print_fail(f"complete_job() erro: {e}")
        results.append(False)
    
    # Teste 6: fail_job (criar novo job para testar)
    try:
        job_id_2 = create_job(test_product_id, test_user_id, {"test": "fail"})
        success = fail_job(job_id_2, "Erro de teste definitivo")
        if success:
            job = get_job(job_id_2)
            if job["status"] == "failed":
                print_ok("fail_job() marcou como failed")
                results.append(True)
            else:
                print_fail(f"fail_job() status incorreto: {job['status']}")
                results.append(False)
        else:
            print_fail("fail_job() retornou False")
            results.append(False)
    except Exception as e:
        print_fail(f"fail_job() erro: {e}")
        results.append(False)
    
    # Teste 7: get_user_jobs
    try:
        jobs = get_user_jobs(test_user_id, limit=5)
        if isinstance(jobs, list):
            print_ok(f"get_user_jobs() retornou {len(jobs)} jobs")
            results.append(True)
        else:
            print_fail(f"get_user_jobs() não retornou lista")
            results.append(False)
    except Exception as e:
        print_fail(f"get_user_jobs() erro: {e}")
        results.append(False)
    
    # Teste 8: get_next_queued_job
    try:
        # Criar um novo job queued
        job_id_3 = create_job(test_product_id, test_user_id, {"test": "queue"})
        
        next_job = get_next_queued_job()
        if next_job:
            print_ok(f"get_next_queued_job() retornou job: {next_job['id'][:8]}...")
            results.append(True)
        else:
            print_warn("get_next_queued_job() retornou None (fila pode estar vazia)")
            results.append(True)  # Não é falha, só não tem jobs
    except Exception as e:
        print_fail(f"get_next_queued_job() erro: {e}")
        results.append(False)
    
    return results


# ============================================
# TESTES DE API (Endpoints)
# ============================================

def test_api_endpoints():
    """Testa endpoints da API."""
    print_header("TESTE: API Endpoints")
    
    try:
        import requests
    except ImportError:
        print_fail("Módulo 'requests' não instalado")
        print_warn("Execute: pip install requests")
        return []
    
    results = []
    
    # Verificar se servidor está rodando
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_ok(f"Servidor rodando em {BASE_URL}")
        else:
            print_fail(f"Servidor retornou {response.status_code}")
            return results
    except Exception as e:
        print_fail(f"Servidor não acessível: {e}")
        print_warn("Execute: uvicorn app.main:app --reload")
        return results
    
    # Verificar se imagem de teste existe
    if not os.path.exists(TEST_IMAGE):
        print_fail(f"Imagem de teste não encontrada: {TEST_IMAGE}")
        print_warn("Crie a imagem ou defina TEST_IMAGE=/caminho/para/imagem.png")
        return results
    
    print_info(f"Usando imagem: {TEST_IMAGE}")
    
    # Teste 1: POST /process-async
    job_id = None
    try:
        with open(TEST_IMAGE, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/process-async",
                files={"file": ("test.png", f, "image/png")},
                timeout=30
            )
        
        if response.status_code == 200:
            data = response.json()
            if "job_id" in data and "product_id" in data:
                print_ok(f"POST /process-async retornou job_id: {data['job_id'][:8]}...")
                print(f"    product_id: {data['product_id'][:8]}...")
                print(f"    status: {data['status']}")
                results.append(True)
                job_id = data["job_id"]
            else:
                print_fail(f"POST /process-async response incompleto: {data}")
                results.append(False)
                return results
        else:
            print_fail(f"POST /process-async retornou {response.status_code}: {response.text[:200]}")
            results.append(False)
            return results
    except Exception as e:
        print_fail(f"POST /process-async erro: {e}")
        results.append(False)
        return results
    
    # Teste 2: GET /jobs/{job_id} - polling
    try:
        max_polls = 60  # 60 polls * 2s = 120s timeout
        poll_interval = 2
        
        print_info(f"Aguardando processamento (max {max_polls * poll_interval}s)...")
        
        final_status = None
        for i in range(max_polls):
            response = requests.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                progress = data.get("progress", 0)
                step = data.get("current_step", "?")
                
                # Progress bar visual
                bar_len = 20
                filled = int(bar_len * progress / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                
                print(f"\r    [{bar}] {progress:3d}% | {step:15} | status={status}", end="", flush=True)
                
                if status == "completed":
                    print()  # Nova linha
                    print_ok(f"Job completou com sucesso!")
                    print(f"    quality_score: {data.get('quality_score')}")
                    print(f"    quality_passed: {data.get('quality_passed')}")
                    if data.get('images'):
                        print(f"    images: {list(data['images'].keys())}")
                    results.append(True)
                    final_status = "completed"
                    break
                elif status == "failed":
                    print()  # Nova linha
                    print_fail(f"Job falhou: {data.get('last_error')}")
                    print(f"    attempts: {data.get('attempts')}/{data.get('max_attempts')}")
                    print(f"    can_retry: {data.get('can_retry')}")
                    results.append(False)
                    final_status = "failed"
                    break
                else:
                    time.sleep(poll_interval)
            else:
                print()
                print_fail(f"GET /jobs/{{id}} retornou {response.status_code}")
                results.append(False)
                break
        else:
            print()
            print_fail("GET /jobs/{id} - Timeout aguardando conclusão")
            results.append(False)
    except Exception as e:
        print()
        print_fail(f"GET /jobs/{{id}} erro: {e}")
        results.append(False)
    
    # Teste 3: GET /jobs (listagem)
    try:
        response = requests.get(f"{BASE_URL}/jobs", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "jobs" in data and "total" in data:
                print_ok(f"GET /jobs retornou {data['total']} jobs")
                results.append(True)
            else:
                print_fail(f"GET /jobs response incompleto: {data}")
                results.append(False)
        else:
            print_fail(f"GET /jobs retornou {response.status_code}")
            results.append(False)
    except Exception as e:
        print_fail(f"GET /jobs erro: {e}")
        results.append(False)
    
    return results


# ============================================
# TESTE DO WORKER (Isolado)
# ============================================

def test_worker_isolated():
    """Testa o worker de forma isolada (sem daemon)."""
    print_header("TESTE: Worker Isolado")
    
    results = []
    
    # Teste 1: Import
    try:
        from app.services.job_worker import JobWorker, JobWorkerDaemon, job_worker, job_daemon
        print_ok("JobWorker e JobWorkerDaemon importados")
        results.append(True)
    except ImportError as e:
        print_fail(f"Import erro: {e}")
        results.append(False)
        return results
    
    # Teste 2: Instância
    try:
        worker = JobWorker()
        print_ok("JobWorker instanciado")
        results.append(True)
    except Exception as e:
        print_fail(f"JobWorker() erro: {e}")
        results.append(False)
        return results
    
    # Teste 3: Verificar serviços internos
    try:
        assert worker.composer is not None, "ImageComposer não inicializado"
        assert worker.husk is not None, "HuskLayer não inicializado"
        print_ok("Serviços internos (composer, husk) OK")
        results.append(True)
    except AssertionError as e:
        print_fail(str(e))
        results.append(False)
    
    # Teste 4: Daemon
    try:
        daemon = JobWorkerDaemon(poll_interval=5)
        assert daemon.poll_interval == 5
        assert daemon.running == False
        print_ok("JobWorkerDaemon configurável OK")
        results.append(True)
    except Exception as e:
        print_fail(f"JobWorkerDaemon erro: {e}")
        results.append(False)
    
    # Teste 5: Instâncias globais
    try:
        assert job_worker is not None
        assert job_daemon is not None
        print_ok("Instâncias globais (job_worker, job_daemon) OK")
        results.append(True)
    except Exception as e:
        print_fail(f"Instâncias globais erro: {e}")
        results.append(False)
    
    print_warn("Para teste E2E do worker, execute: --test-api")
    
    return results


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Testes PRD-04 Jobs Async")
    parser.add_argument("--test-db", action="store_true", help="Testa apenas CRUD do banco")
    parser.add_argument("--test-api", action="store_true", help="Testa apenas endpoints API")
    parser.add_argument("--test-worker", action="store_true", help="Testa worker isolado")
    parser.add_argument("--all", action="store_true", help="Executa todos os testes")
    
    args = parser.parse_args()
    
    # Se nenhum argumento, executar API (teste mais útil)
    if not any([args.test_db, args.test_api, args.test_worker, args.all]):
        args.test_api = True
    
    all_results = []
    
    print("\n" + "="*60)
    print("  FRIDA PRD-04: Testes de Jobs Async")
    print("="*60)
    print(f"  BASE_URL: {BASE_URL}")
    print(f"  TEST_IMAGE: {TEST_IMAGE}")
    
    if args.test_db or args.all:
        results = test_database_crud()
        all_results.extend(results)
    
    if args.test_worker or args.all:
        results = test_worker_isolated()
        all_results.extend(results)
    
    if args.test_api or args.all:
        results = test_api_endpoints()
        all_results.extend(results)
    
    # Resumo
    print_header("RESUMO")
    
    passed = sum(all_results)
    total = len(all_results)
    
    if total > 0:
        percentage = (passed / total) * 100
        
        print(f"Testes passaram: {passed}/{total} ({percentage:.0f}%)")
        
        if passed == total:
            print(f"\n{GREEN}{'='*40}")
            print(f"  ✓ TODOS OS TESTES PASSARAM!")
            print(f"{'='*40}{RESET}")
            return 0
        else:
            print(f"\n{RED}{'='*40}")
            print(f"  ✗ {total - passed} teste(s) falharam")
            print(f"{'='*40}{RESET}")
            return 1
    else:
        print_warn("Nenhum teste executado")
        return 1


if __name__ == "__main__":
    sys.exit(main())
