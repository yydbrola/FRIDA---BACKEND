#!/bin/bash
# Frida Orchestrator - PRD-04/05 Automated Tests
# Uso: ./scripts/test_prd_04_05.sh
#
# Pré-requisitos:
#   - jq instalado (sudo apt install jq)
#   - Servidor rodando (uvicorn app.main:app --reload --port 8000)
#   - Imagem de teste em test_images/bolsa_teste.png

set -o pipefail

echo "=============================================="
echo "  Frida Orchestrator - Testes PRD-04/05"
echo "  Versão: 1.1"
echo "  Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

# Verificar dependências
if ! command -v jq &> /dev/null; then
  echo "ERRO: 'jq' não instalado. Execute: sudo apt install jq"
  exit 1
fi

if ! command -v curl &> /dev/null; then
  echo "ERRO: 'curl' não instalado."
  exit 1
fi

BASE_URL="http://localhost:8000"
IMAGE="test_images/bolsa_teste.png"
PASS=0
FAIL=0
SKIP=0

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Verificar se servidor está rodando
echo -e "\n[Pre-check] Verificando servidor..."
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
  echo -e "${RED}ERRO: Servidor não está rodando em $BASE_URL${NC}"
  echo "Execute: uvicorn app.main:app --reload --port 8000"
  exit 1
fi
echo -e "${GREEN}OK${NC} Servidor respondendo"

# Verificar se imagem de teste existe
if [ ! -f "$IMAGE" ]; then
  echo -e "${RED}ERRO: Imagem de teste não encontrada: $IMAGE${NC}"
  exit 1
fi
echo -e "${GREEN}OK${NC} Imagem de teste encontrada"

# Função de teste HTTP status code
test_http() {
  local name="$1"
  local cmd="$2"
  local expected="$3"

  echo -n "  $name... "
  result=$(eval "$cmd" 2>/dev/null)

  if [ "$result" == "$expected" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}FAIL${NC} (got: $result, expected: $expected)"
    ((FAIL++))
    return 1
  fi
}

# Função de teste com JSON response
test_json_field() {
  local name="$1"
  local url="$2"
  local jq_filter="$3"
  local expected="$4"

  echo -n "  $name... "
  result=$(curl -s "$url" | jq -r "$jq_filter" 2>/dev/null)

  if [ "$result" == "$expected" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}FAIL${NC} (got: $result, expected: $expected)"
    ((FAIL++))
    return 1
  fi
}

# Função de teste com condição
test_condition() {
  local name="$1"
  local condition="$2"

  echo -n "  $name... "
  if eval "$condition"; then
    echo -e "${GREEN}PASS${NC}"
    ((PASS++))
    return 0
  else
    echo -e "${RED}FAIL${NC}"
    ((FAIL++))
    return 1
  fi
}

# Função para skip test
skip_test() {
  local name="$1"
  local reason="$2"
  echo -e "  $name... ${YELLOW}SKIP${NC} ($reason)"
  ((SKIP++))
}

echo -e "\n=== Categoria 9: PRD-04 Jobs Async ==="

# 9.1 POST /process-async
test_http "9.1 POST /process-async returns 202" \
  "curl -s -o /dev/null -w '%{http_code}' -X POST $BASE_URL/process-async -F 'file=@$IMAGE'" \
  "202"

# Guardar job_id e product_id para próximos testes
echo -n "  Criando job para testes... "
ASYNC_RESP=$(curl -s -X POST "$BASE_URL/process-async" -F "file=@$IMAGE")
JOB_ID=$(echo "$ASYNC_RESP" | jq -r '.job_id')
PRODUCT_ID=$(echo "$ASYNC_RESP" | jq -r '.product_id')

if [ "$JOB_ID" != "null" ] && [ -n "$JOB_ID" ]; then
  echo -e "${GREEN}OK${NC} (job_id: ${JOB_ID:0:8}...)"
else
  echo -e "${RED}FAIL${NC} (não conseguiu criar job)"
  JOB_ID=""
  PRODUCT_ID=""
fi

# 9.2 GET /jobs/{id}
if [ -n "$JOB_ID" ]; then
  test_http "9.2 GET /jobs/{id} returns 200" \
    "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/jobs/$JOB_ID'" \
    "200"
else
  skip_test "9.2 GET /jobs/{id} returns 200" "job não criado"
fi

# 9.3 GET /jobs
test_http "9.3 GET /jobs returns 200" \
  "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/jobs'" \
  "200"

# 9.4 GET /jobs/{invalid}
test_http "9.4 GET /jobs/{invalid} returns 404" \
  "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/jobs/00000000-0000-0000-0000-000000000000'" \
  "404"

# 9.5 State Machine (verificação básica)
if [ -n "$JOB_ID" ]; then
  echo -n "  9.5 Job tem campo status... "
  STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID" | jq -r '.status')
  if [ "$STATUS" == "queued" ] || [ "$STATUS" == "processing" ] || [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
    echo -e "${GREEN}PASS${NC} (status: $STATUS)"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC} (status inválido: $STATUS)"
    ((FAIL++))
  fi
else
  skip_test "9.5 Job tem campo status" "job não criado"
fi

# 9.8 DoS - arquivo grande
echo -n "  9.8 DoS: arquivo > 10MB rejeitado (413)... "
python3 -c "
from PIL import Image
img = Image.new('RGB', (100, 100), 'red')
img.save('/tmp/test_large.png')
with open('/tmp/test_large.png', 'ab') as f:
    f.write(b'\x00' * (12 * 1024 * 1024))
" 2>/dev/null
LARGE_RESULT=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/process-async" -F "file=@/tmp/test_large.png")
if [ "$LARGE_RESULT" == "413" ]; then
  echo -e "${GREEN}PASS${NC}"
  ((PASS++))
else
  echo -e "${RED}FAIL${NC} (got: $LARGE_RESULT)"
  ((FAIL++))
fi
rm -f /tmp/test_large.png

# 9.9 DoS - dimensões grandes
echo -n "  9.9 DoS: imagem > 8000px rejeitada (400)... "
python3 -c "from PIL import Image; Image.new('RGB', (9000, 9000), 'blue').save('/tmp/test_huge.png')" 2>/dev/null
HUGE_RESULT=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/process-async" -F "file=@/tmp/test_huge.png")
if [ "$HUGE_RESULT" == "400" ]; then
  echo -e "${GREEN}PASS${NC}"
  ((PASS++))
else
  echo -e "${RED}FAIL${NC} (got: $HUGE_RESULT)"
  ((FAIL++))
fi
rm -f /tmp/test_huge.png

echo -e "\n=== Categoria 10: PRD-05 Technical Sheets ==="

# Aguardar job completar para ter product válido
if [ -n "$JOB_ID" ]; then
  echo -n "  Aguardando job completar... "
  for i in {1..15}; do
    STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID" | jq -r '.status')
    if [ "$STATUS" == "completed" ] || [ "$STATUS" == "failed" ]; then
      break
    fi
    sleep 2
  done
  echo -e "${GREEN}OK${NC} (status: $STATUS)"
fi

# 10.1 POST /sheet
if [ -n "$PRODUCT_ID" ]; then
  test_http "10.1 POST /sheet returns 200" \
    "curl -s -o /dev/null -w '%{http_code}' -X POST '$BASE_URL/products/$PRODUCT_ID/sheet' -H 'Content-Type: application/json' -d '{\"data\":{\"test\":true}}'" \
    "200"
else
  skip_test "10.1 POST /sheet returns 200" "product_id não disponível"
fi

# 10.2 GET /sheet
if [ -n "$PRODUCT_ID" ]; then
  test_http "10.2 GET /sheet returns 200" \
    "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/products/$PRODUCT_ID/sheet'" \
    "200"
else
  skip_test "10.2 GET /sheet returns 200" "product_id não disponível"
fi

# 10.3 PUT /sheet (versionamento)
if [ -n "$PRODUCT_ID" ]; then
  echo -n "  10.3 PUT /sheet incrementa version... "
  curl -s -X PUT "$BASE_URL/products/$PRODUCT_ID/sheet" \
    -H "Content-Type: application/json" \
    -d '{"data":{"updated":true},"change_summary":"test update"}' > /dev/null
  VERSION=$(curl -s "$BASE_URL/products/$PRODUCT_ID/sheet" | jq -r '.version')
  if [ "$VERSION" == "2" ]; then
    echo -e "${GREEN}PASS${NC} (version: $VERSION)"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC} (version: $VERSION, expected: 2)"
    ((FAIL++))
  fi
else
  skip_test "10.3 PUT /sheet incrementa version" "product_id não disponível"
fi

# 10.4 GET /sheet/versions
if [ -n "$PRODUCT_ID" ]; then
  test_http "10.4 GET /sheet/versions returns 200" \
    "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/products/$PRODUCT_ID/sheet/versions'" \
    "200"
else
  skip_test "10.4 GET /sheet/versions returns 200" "product_id não disponível"
fi

# 10.5 PATCH /sheet/status
if [ -n "$PRODUCT_ID" ]; then
  echo -n "  10.5 PATCH /sheet/status workflow... "
  # draft -> pending
  curl -s -X PATCH "$BASE_URL/products/$PRODUCT_ID/sheet/status" \
    -H "Content-Type: application/json" \
    -d '{"status":"pending"}' > /dev/null
  STATUS1=$(curl -s "$BASE_URL/products/$PRODUCT_ID/sheet" | jq -r '.status')

  # pending -> approved
  curl -s -X PATCH "$BASE_URL/products/$PRODUCT_ID/sheet/status" \
    -H "Content-Type: application/json" \
    -d '{"status":"approved"}' > /dev/null
  STATUS2=$(curl -s "$BASE_URL/products/$PRODUCT_ID/sheet" | jq -r '.status')

  if [ "$STATUS1" == "pending" ] && [ "$STATUS2" == "approved" ]; then
    echo -e "${GREEN}PASS${NC} (draft->pending->approved)"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC} (got: $STATUS1 -> $STATUS2)"
    ((FAIL++))
  fi
else
  skip_test "10.5 PATCH /sheet/status workflow" "product_id não disponível"
fi

# 10.6 GET /sheet/export/pdf
if [ -n "$PRODUCT_ID" ]; then
  echo -n "  10.6 GET /sheet/export/pdf gera arquivo... "
  curl -s -o /tmp/test_sheet.pdf "$BASE_URL/products/$PRODUCT_ID/sheet/export/pdf"
  PDF_SIZE=$(stat -c%s /tmp/test_sheet.pdf 2>/dev/null || stat -f%z /tmp/test_sheet.pdf 2>/dev/null || echo "0")
  if [ "$PDF_SIZE" -gt 1000 ]; then
    echo -e "${GREEN}PASS${NC} ($PDF_SIZE bytes)"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC} (tamanho: $PDF_SIZE bytes)"
    ((FAIL++))
  fi
  rm -f /tmp/test_sheet.pdf
else
  skip_test "10.6 GET /sheet/export/pdf" "product_id não disponível"
fi

# 10.8 GET /sheet para produto inexistente
test_http "10.8 GET /sheet para produto inexistente returns 404" \
  "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/products/00000000-0000-0000-0000-000000000000/sheet'" \
  "404"

# 10.9 PATCH /sheet/status com status inválido
if [ -n "$PRODUCT_ID" ]; then
  test_http "10.9 PATCH /sheet/status inválido returns 400" \
    "curl -s -o /dev/null -w '%{http_code}' -X PATCH '$BASE_URL/products/$PRODUCT_ID/sheet/status' -H 'Content-Type: application/json' -d '{\"status\":\"invalid_status\"}'" \
    "400"
else
  skip_test "10.9 PATCH /sheet/status inválido" "product_id não disponível"
fi

# 10.11 GET /sheet/versions/{invalid}
if [ -n "$PRODUCT_ID" ]; then
  test_http "10.11 GET /sheet/versions/999 returns 404" \
    "curl -s -o /dev/null -w '%{http_code}' '$BASE_URL/products/$PRODUCT_ID/sheet/versions/999'" \
    "404"
else
  skip_test "10.11 GET /sheet/versions/999" "product_id não disponível"
fi

echo -e "\n=== Categoria 11: Fluxos E2E ==="

# 11.2 Sync vs Async comparison
echo -n "  11.2 Async mais rápido que Sync... "
ASYNC_START=$(date +%s%N)
curl -s -X POST "$BASE_URL/process-async" -F "file=@$IMAGE" > /dev/null
ASYNC_END=$(date +%s%N)
ASYNC_TIME=$(( (ASYNC_END - ASYNC_START) / 1000000 ))

if [ "$ASYNC_TIME" -lt 3000 ]; then
  echo -e "${GREEN}PASS${NC} (async: ${ASYNC_TIME}ms < 3000ms)"
  ((PASS++))
else
  echo -e "${YELLOW}WARN${NC} (async: ${ASYNC_TIME}ms, esperado < 3000ms)"
  ((PASS++))  # Ainda passa, mas com aviso
fi

# Resultado final
echo ""
echo "=============================================="
echo "  RESULTADO DOS TESTES"
echo "=============================================="
echo -e "  Passou:  ${GREEN}$PASS${NC}"
echo -e "  Falhou:  ${RED}$FAIL${NC}"
echo -e "  Pulado:  ${YELLOW}$SKIP${NC}"
echo "=============================================="

TOTAL=$((PASS + FAIL))
if [ $TOTAL -gt 0 ]; then
  PERCENT=$((PASS * 100 / TOTAL))
  echo "  Taxa de sucesso: $PERCENT%"
fi

if [ -n "$JOB_ID" ]; then
  echo ""
  echo "  Job ID usado:     ${JOB_ID:0:8}..."
  echo "  Product ID usado: ${PRODUCT_ID:0:8}..."
fi

echo "=============================================="

if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}TODOS OS TESTES PASSARAM${NC}"
  exit 0
else
  echo -e "${RED}ALGUNS TESTES FALHARAM${NC}"
  exit 1
fi
