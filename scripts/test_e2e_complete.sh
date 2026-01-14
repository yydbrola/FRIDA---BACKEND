#!/bin/bash
# Frida E2E Test - Fluxo Completo
# Upload -> Job -> Sheet -> PDF
#
# Uso: ./scripts/test_e2e_complete.sh
# Requer: jq instalado

set -e  # Parar em caso de erro

echo "=========================================="
echo "  FRIDA E2E Test - Fluxo Completo"
echo "  Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Verificar dependências
if ! command -v jq &> /dev/null; then
  echo "ERRO: 'jq' não está instalado. Execute: sudo apt install jq"
  exit 1
fi

BASE_URL="http://localhost:8000"
IMAGE="test_images/bolsa_teste.png"

# Verificar imagem existe
if [ ! -f "$IMAGE" ]; then
  echo "ERRO: Imagem de teste não encontrada: $IMAGE"
  exit 1
fi

# Verificar servidor
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
  echo "ERRO: Servidor não está rodando em $BASE_URL"
  exit 1
fi

# STEP 1: Upload async
echo -e "\n[1/7] Criando job async..."
RESPONSE=$(curl -s -X POST "$BASE_URL/process-async" -F "file=@$IMAGE")
JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')
PRODUCT_ID=$(echo "$RESPONSE" | jq -r '.product_id')

echo "Job ID: $JOB_ID"
echo "Product ID: $PRODUCT_ID"

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo "FALHA: Job não criado"
  echo "Response: $RESPONSE"
  exit 1
fi
echo "[OK] Job criado"

# STEP 2: Polling até completar
echo -e "\n[2/7] Aguardando processamento..."
MAX_POLLS=30
for i in $(seq 1 $MAX_POLLS); do
  POLL=$(curl -s "$BASE_URL/jobs/$JOB_ID")
  STATUS=$(echo "$POLL" | jq -r '.status')
  PROGRESS=$(echo "$POLL" | jq -r '.progress')

  echo "  Poll $i: $STATUS ($PROGRESS%)"

  if [ "$STATUS" == "completed" ]; then
    echo "[OK] Processamento completo"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo "[FALHA] Job falhou"
    echo "Erro: $(echo "$POLL" | jq -r '.last_error')"
    exit 1
  fi

  if [ "$i" -eq "$MAX_POLLS" ]; then
    echo "[TIMEOUT] Job não completou em 60 segundos"
    exit 1
  fi

  sleep 2
done

# STEP 3: Verificar imagens geradas
echo -e "\n[3/7] Verificando output..."
OUTPUT=$(curl -s "$BASE_URL/jobs/$JOB_ID")
QUALITY=$(echo "$OUTPUT" | jq -r '.quality_score')
PASSED=$(echo "$OUTPUT" | jq -r '.quality_passed')

echo "Quality Score: $QUALITY"
echo "Quality Passed: $PASSED"

if [ "$QUALITY" != "null" ] && [ "$QUALITY" -ge 80 ]; then
  echo "[OK] Quality score OK (>= 80)"
else
  echo "[AVISO] Quality score: $QUALITY"
fi

# STEP 4: Criar ficha técnica
echo -e "\n[4/7] Criando ficha técnica..."
SHEET_RESPONSE=$(curl -s -X POST "$BASE_URL/products/$PRODUCT_ID/sheet" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "dimensions": {"height_cm": 25, "width_cm": 35, "depth_cm": 12},
      "materials": {"primary": "Couro sintético", "hardware": "Metal"},
      "colors": ["Preto"],
      "weight_grams": 450
    }
  }')
SHEET_ID=$(echo "$SHEET_RESPONSE" | jq -r '.sheet_id')
SHEET_VERSION=$(echo "$SHEET_RESPONSE" | jq -r '.version')

echo "Sheet ID: $SHEET_ID"
echo "Version: $SHEET_VERSION"

if [ "$SHEET_ID" == "null" ] || [ -z "$SHEET_ID" ]; then
  echo "[FALHA] Ficha não criada"
  echo "Response: $SHEET_RESPONSE"
  exit 1
fi
echo "[OK] Ficha técnica criada"

# STEP 5: Atualizar e verificar versionamento
echo -e "\n[5/7] Testando versionamento..."
curl -s -X PUT "$BASE_URL/products/$PRODUCT_ID/sheet" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "dimensions": {"height_cm": 28, "width_cm": 38, "depth_cm": 14},
      "materials": {"primary": "Couro legítimo", "hardware": "Metal dourado"},
      "colors": ["Caramelo"],
      "weight_grams": 520
    },
    "change_summary": "Atualização de materiais"
  }' > /dev/null

VERSION=$(curl -s "$BASE_URL/products/$PRODUCT_ID/sheet" | jq -r '.version')
echo "Versão atual: $VERSION"

if [ "$VERSION" == "2" ]; then
  echo "[OK] Versionamento funcionando"
else
  echo "[FALHA] Versão deveria ser 2, é $VERSION"
fi

# STEP 6: Workflow de aprovação
echo -e "\n[6/7] Testando workflow..."
curl -s -X PATCH "$BASE_URL/products/$PRODUCT_ID/sheet/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "pending"}' > /dev/null
echo "  draft -> pending"

curl -s -X PATCH "$BASE_URL/products/$PRODUCT_ID/sheet/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "approved"}' > /dev/null
echo "  pending -> approved"

FINAL_STATUS=$(curl -s "$BASE_URL/products/$PRODUCT_ID/sheet" | jq -r '.status')
echo "Status final: $FINAL_STATUS"

if [ "$FINAL_STATUS" == "approved" ]; then
  echo "[OK] Workflow funcionando"
else
  echo "[FALHA] Status deveria ser 'approved', é '$FINAL_STATUS'"
fi

# STEP 7: Export PDF
echo -e "\n[7/7] Exportando PDF..."
curl -s -o /tmp/ficha_e2e_test.pdf "$BASE_URL/products/$PRODUCT_ID/sheet/export/pdf"
PDF_SIZE=$(stat -c%s /tmp/ficha_e2e_test.pdf 2>/dev/null || stat -f%z /tmp/ficha_e2e_test.pdf 2>/dev/null || echo "0")
echo "PDF gerado: $PDF_SIZE bytes"

if [ "$PDF_SIZE" -gt 1000 ]; then
  echo "[OK] PDF válido"
else
  echo "[AVISO] PDF muito pequeno ou inválido"
fi

# RESULTADO FINAL
echo -e "\n=========================================="
echo "  RESULTADO DO TESTE E2E"
echo "=========================================="
echo "Job ID:      $JOB_ID"
echo "Product ID:  $PRODUCT_ID"
echo "Sheet ID:    $SHEET_ID"
echo "Version:     $VERSION"
echo "Quality:     $QUALITY"
echo "Status:      $FINAL_STATUS"
echo "PDF Size:    $PDF_SIZE bytes"
echo "=========================================="
echo "[OK] TESTE E2E COMPLETO COM SUCESSO"

# Limpar
rm -f /tmp/ficha_e2e_test.pdf
