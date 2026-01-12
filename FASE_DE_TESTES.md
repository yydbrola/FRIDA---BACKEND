# Fase de Testes - Frida Orchestrator v0.5.0

Este documento contém todos os testes necessários para validar a funcionalidade completa do Frida Orchestrator Backend.

## Pré-requisitos

### 1. Iniciar o Servidor

```bash
cd "/home/yvensyandebarrosrola/Área de Trabalho/Projeto Frida - main/componentes"
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 2. Verificar Configuração

```bash
cat .env
# Confirme que GEMINI_API_KEY está configurada
# AUTH_ENABLED=false (para testes iniciais)
```

### 3. Preparar Imagens de Teste

Tenha pelo menos uma imagem válida de cada categoria:
- `bolsa.jpg` - Foto ou sketch de bolsa
- `lancheira.jpg` - Foto ou sketch de lancheira
- `garrafa.jpg` - Foto ou sketch de garrafa térmica

---

## Categoria 1: Health & Connectivity ✓

### 1.1 Health Check Básico

**Comando:**
```bash
curl http://localhost:8000/health
```

**Resultado Esperado:**
```json
{
  "status": "healthy",
  "version": "0.5.0",
  "ready": true,
  "services": {
    "classifier": "ok",
    "background_remover": "ok",
    "tech_sheet": "ok"
  }
}
```

**Status:** [✓] Teste concluído com sucesso

---

### 1.2 Ping Público

**Comando:**
```bash
curl http://localhost:8000/public/ping
```

**Resultado Esperado:**
```json
{
  "status": "pong",
  "service": "Frida Orchestrator",
  "version": "0.5.0",
  "auth_required": false
}
```

**Status:** [✓] Teste concluído com sucesso

---

### 1.3 Root Endpoint

**Comando:**
```bash
curl http://localhost:8000/
```

**Resultado Esperado:**
- Página HTML com título "FRIDA ORCHESTRATOR"
- Link para `/docs` (Swagger)
- Link para `/health`

**Status:** [✓] Teste concluído com sucesso

---

### 1.4 Swagger Documentation

**Comando:**
```bash
# Abrir no navegador
http://localhost:8000/docs
```

**Resultado Esperado:**
- Interface Swagger UI carregada
- Endpoints visíveis: `/process`, `/classify`, `/remove-background`, `/health`, `/auth/test`

**Status:** [✓] Teste concluído com sucesso

---

## Categoria 2: Autenticação (Dev Mode) 🔓

### 2.1 Auth Test Sem Token

**Comando:**
```bash
curl http://localhost:8000/auth/test
```

**Resultado Esperado:**
```json
{
  "status": "authenticated",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "message": "Token JWT válido!"
}
```

**Nota:** Em dev mode (AUTH_ENABLED=false), retorna user_id fake.

**Status:** [✓] Teste concluído com sucesso

---

### 2.2 Auth Test Com Token Inválido

**Comando:**
```bash
curl -H "Authorization: Bearer fake_token_123" http://localhost:8000/auth/test
```

**Resultado Esperado:**
```json
{
  "status": "authenticated",
  "user_id": "00000000-0000-0000-0000-000000000000",
  "message": "Token JWT válido!"
}
```

**Nota:** Dev mode ignora validação, sempre retorna sucesso.

**Status:** [✓] Teste concluído com sucesso

---

## Categoria 3: Classificação de Imagens 🤖

### 3.1 Classificar Imagem Válida (Bolsa)

**Comando:**
```bash
curl -X POST http://localhost:8000/classify -F "file=@bolsa.jpg"
```

**Resultado Esperado:**
```json
{
  "status": "sucesso",
  "classificacao": {
    "item": "bolsa",
    "estilo": "foto" ou "sketch",
    "confianca": 0.7 a 1.0
  },
  "user_id": "00000000-0000-0000-0000-000000000000"
}
```

**Status:** [✓] Teste concluído com sucesso (item: bolsa, confiança: 0.95)

---

### 3.2 Classificar Imagem Válida (Lancheira)

**Comando:**
```bash
curl -X POST http://localhost:8000/classify -F "file=@lancheira.jpg"
```

**Resultado Esperado:**
```json
{
  "classificacao": {
    "item": "lancheira",
    "estilo": "foto" ou "sketch",
    "confianca": > 0.7
  }
}
```

**Status:** [✓] Teste concluído com sucesso (testado com garrafa_termica, confiança: 0.95)

---

### 3.3 Classificar Sem Arquivo

**Comando:**
```bash
curl -X POST http://localhost:8000/classify
```

**Resultado Esperado:**
- HTTP Status: 422 (Unprocessable Entity)
- Mensagem de erro sobre campo obrigatório

**Status:** [✓] Teste concluído com sucesso

---

### 3.4 Classificar Arquivo Não-Imagem

**Comando:**
```bash
echo "fake content" > test.txt
curl -X POST http://localhost:8000/classify -F "file=@test.txt"
```

**Resultado Esperado:**
- HTTP Status: 400 (Bad Request)
- Mensagem: "Arquivo inválido. Envie uma imagem"

**Status:** [✓] Teste concluído com sucesso (testado com README.md)

---

## Categoria 4: Processamento Completo 🖼️

### 4.1 Processar Sem Ficha Técnica

**Comando:**
```bash
curl -X POST http://localhost:8000/process -F "file=@bolsa.jpg"
```

**Resultado Esperado:**
```json
{
  "status": "sucesso",
  "categoria": "bolsa",
  "estilo": "foto" ou "sketch",
  "confianca": 0.7 a 1.0,
  "imagem_base64": "iVBORw0KGgoAAAANSUh..." (string longa),
  "ficha_tecnica": null,
  "mensagem": "Imagem processada com sucesso! user_id=00000000-0000-0000-0000-000000000000"
}
```

**Validação Adicional:**
- `imagem_base64` deve ter centenas/milhares de caracteres
- Decodificar base64 deve resultar em imagem PNG válida

**Status:** [✓] Teste concluído com sucesso (categoria: bolsa, estilo: foto, confiança: 0.95)

---

### 4.2 Processar Com Ficha Técnica

**Comando:**
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@bolsa.jpg" \
  -F "gerar_ficha=true"
```

**Resultado Esperado:**
```json
{
  "status": "sucesso",
  "ficha_tecnica": {
    "nome": "...",
    "categoria": "...",
    "descricao": "...",
    "materiais": [...],
    "cores": [...],
    "dimensoes": {...}
  }
}
```

**Status:** [✓] Teste concluído com sucesso
- `ficha_tecnica.dados`: nome="Bolsa Premium", categoria="bolsa", materiais=["Couro sintético premium"], cores=["Preto"]
- `ficha_tecnica.html`: Template HTML renderizado com Jinja2 (layout minimalista, fonte Outfit, imagem base64 embutida)
- Pipeline completo: classificação + remoção de fundo + extração de dados + renderização HTML

**⚠️ NOTA IMPORTANTE:**
Esse ponto em específico vai ter que ser retrabalhado por conta da necessidade de alterar os campos da ficha técnica para atender as necessidades da Carol. Contudo, como proposta inicial, foi usado essas referências para averiguar a capacidade da IA em preencher os campos da ficha e apresentar um documento coeso. **Campo será atualizado!!!**
_(Campo importante para contexto de modelos de IA - Gemini e Claude)_

---

### 4.3 Processar Com Product ID

**Comando:**
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@bolsa.jpg" \
  -F "product_id=PROD-001"
```

**Resultado Esperado:**
- Mesma resposta de 4.1
- No storage Supabase (se configurado), arquivo salvo em: `{user_id}/PROD-001/{timestamp}.png`

**Status:** [✓] Teste concluído com sucesso
- Parâmetro `product_id=PROD-001` aceito sem erros
- Resposta idêntica ao teste 4.1 (categoria: bolsa, estilo: foto, confiança: 0.95)
- Processamento normal sem ficha técnica

---

### 4.4 Remover Fundo Apenas

**Comando:**
```bash
curl -X POST http://localhost:8000/remove-background -F "file=@bolsa.jpg"
```

**Resultado Esperado:**
```json
{
  "status": "sucesso",
  "imagem_base64": "iVBORw0KGgoAAAANSUh...",
  "user_id": "00000000-0000-0000-0000-000000000000"
}
```

**Validação:**
- Imagem retornada deve ter fundo branco (#FFFFFF)

**Status:** [✓] Teste concluído com sucesso
- Fundo completamente branco (#FFFFFF) validado visualmente
- Remoção de fundo precisa sem artefatos
- Endpoint mais rápido (sem classificação AI)
- Composição profissional da bolsa sobre fundo branco

**⚠️ NOTA IMPORTANTE:**
A proposta da ferramenta funcionou perfeitamente, o fundo branco permite padronização da saída. Contudo, como a imagem do produto foi apresentada com uma modelo, houve distorção da imagem do produto acabado. Eventualmente terei que trabalhar nisso, para que o produto fique perfeito na parte de geração da imagem final. **Qualidade da imagem deve ser retrabalhada!!!**
_(Contexto importante para modelos de IA - a qualidade da imagem deve ser retrabalhada - importante para GEMINI e CLAUDE)_

---

## Categoria 5: Validação de Imagens (Segurança) 🛡️

### 5.1 Magic Numbers Validation

**Comando:**
```bash
echo "fake image content" > fake.jpg
curl -X POST http://localhost:8000/classify -F "file=@fake.jpg"
```

**Resultado Esperado:**
- HTTP Status: 400
- Mensagem: "Assinatura de arquivo não corresponde a nenhum formato de imagem suportado"

**Status:** [✓] Teste concluído com sucesso
- Arquivo fake rejeitado corretamente (HTTP 400)
- Validação de magic numbers funcionando
- Mensagem de erro: "Assinatura de arquivo não corresponde a nenhum formato de imagem suportado"
- Proteção contra arquivos disfarçados ativada

---

### 5.2 Imagem Corrompida

**Comando:**
```bash
head -c 1000 /dev/urandom > corrupted.jpg
curl -X POST http://localhost:8000/classify -F "file=@corrupted.jpg"
```

**Resultado Esperado:**
- HTTP Status: 400
- Mensagem: "Arquivo corrompido ou não é uma imagem válida"

**Status:** [✓] Teste concluído com sucesso
- Arquivo corrompido rejeitado corretamente (HTTP 400)
- Validação em camadas funcionando (detectado na primeira camada - magic numbers)
- Bytes aleatórios não correspondem a formato de imagem válido
- Proteção contra arquivos corrompidos ativada

---

### 5.3 PNG Válido

**Comando:**
```bash
# Use uma imagem PNG legítima
curl -X POST http://localhost:8000/classify -F "file=@image.png"
```

**Resultado Esperado:**
- HTTP Status: 200
- Classificação bem-sucedida

**Status:** [✓] Teste concluído com sucesso
- Imagem PNG legítima processada com sucesso (HTTP 200)
- Classificação: item="bolsa", estilo="foto", confiança=0.95
- Validações de segurança aprovadas (magic numbers + Pillow integrity)
- Confirmado: proteções não bloqueiam imagens legítimas

---

### 5.4 WebP Válido

**Comando:**
```bash
# Use uma imagem WebP legítima
curl -X POST http://localhost:8000/classify -F "file=@image.webp"
```

**Resultado Esperado:**
- HTTP Status: 200
- Classificação bem-sucedida

**Status:** [✓] Teste concluído com sucesso
- Arquivo WebP aceito com Content-Type correto (HTTP 200)
- Classificação: item="desconhecido" (esperado para textura), estilo="foto", confiança=0.9
- Validações de segurança aprovadas (magic numbers RIFF+WEBP + Pillow integrity)
- **Confirmado: API aceita PNG, JPEG e WebP**
- **Nota:** curl precisa forçar Content-Type com `;type=image/webp` para WebP

---

## Categoria 6: Storage (Supabase) ☁️

**Pré-requisito:** Configurar `SUPABASE_URL` e `SUPABASE_KEY` no `.env`

### 6.1 Health Check Com Supabase

**Comando:**
```bash
curl http://localhost:8000/health | jq '.services.storage'
```

**Resultado Esperado:**
- `"ok"` se Supabase configurado
- `"not_configured"` se não configurado

**Status:** [ ]

---

### 6.2 Upload Para Supabase

**Comando:**
```bash
curl -X POST http://localhost:8000/process -F "file=@bolsa.jpg"
```

**Validação:**
1. Verificar logs do servidor
2. Deve aparecer: `[StorageService] ✅ Image uploaded for user...`
3. Deve aparecer: `[PROCESS] ✓ Registrado: {record_id}`

**Status:** [ ]

---

### 6.3 Verificar Bucket

**Ação:**
1. Acessar Supabase Dashboard
2. Storage → `processed-images`
3. Verificar estrutura: `{user_id}/{timestamp}_{id}.png`

**Resultado Esperado:**
- Arquivo PNG salvo corretamente
- Imagem acessível via URL pública

**Status:** [ ]

---

### 6.4 Verificar Auditoria

**Ação:**
1. Acessar Supabase Dashboard
2. Table Editor → `historico_geracoes`
3. Verificar último registro

**Resultado Esperado:**
```sql
SELECT * FROM historico_geracoes ORDER BY created_at DESC LIMIT 1;
```

Campos esperados:
- `user_id`
- `categoria` (bolsa/lancheira/garrafa_termica)
- `estilo` (sketch/foto)
- `confianca` (float)
- `image_url` (URL pública)
- `ficha_tecnica` (JSON, se gerado)
- `product_id` (se fornecido)

**Status:** [ ]

---

## Categoria 7: Errors & Edge Cases ⚠️

### 7.1 Arquivo Muito Grande

**Comando:**
```bash
# Criar arquivo > 10MB (se houver limite configurado)
dd if=/dev/zero of=huge.jpg bs=1M count=15
curl -X POST http://localhost:8000/process -F "file=@huge.jpg"
```

**Resultado Esperado:**
- HTTP Status: 413 (Request Entity Too Large) ou timeout
- Servidor continua operacional

**Status:** [ ]

---

### 7.2 Content-Type Incorreto

**Comando:**
```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: text/plain" \
  -d "fake data"
```

**Resultado Esperado:**
- HTTP Status: 422 (Unprocessable Entity)

**Status:** [ ]

---

### 7.3 Requisições Simultâneas

**Comando:**
```bash
# Usando GNU parallel (instalar se necessário)
seq 1 10 | parallel -j5 'curl -X POST http://localhost:8000/classify -F "file=@bolsa.jpg"'
```

**Resultado Esperado:**
- Todas as requisições retornam sucesso
- Servidor mantém-se estável
- Sem crashes ou timeouts

**Status:** [ ]

---

## Categoria 8: Configuração & Startup 🚀

### 8.1 Startup Sem GEMINI_API_KEY

**Ação:**
1. Parar servidor
2. Comentar `GEMINI_API_KEY` no `.env`
3. Tentar iniciar servidor

**Resultado Esperado:**
```
[STARTUP] FALHA CRÍTICA: GEMINI_API_KEY não configurada!
  A API do Gemini é obrigatória para o funcionamento do Frida.
  Configure a variável de ambiente no arquivo .env:
    GEMINI_API_KEY=sua_chave_aqui
```

**Status:** [ ]

---

### 8.2 Startup Com Gemini OK

**Ação:**
1. Restaurar `GEMINI_API_KEY` no `.env`
2. Iniciar servidor

**Resultado Esperado:**
```
[STARTUP] ✓ GEMINI_API_KEY configurada
[STARTUP] ✓ BackgroundRemoverService inicializado
[STARTUP] ✓ ClassifierService inicializado
[STARTUP] ✓ TechSheetService inicializado
[STARTUP] ✓ Todos os serviços inicializados com sucesso!
[STARTUP] ✓ Servidor pronto em http://0.0.0.0:8000
[STARTUP] ⚠ Authentication DISABLED (development mode)
```

**Status:** [ ]

---

### 8.3 Verificar Modelos Gemini

**Ação:**
Verificar logs de startup

**Resultado Esperado:**
- Modelos usados: `gemini-2.0-flash-lite` (classifier e tech_sheet)
- Não deve haver erros de modelo não encontrado

**Status:** [ ]

---

## Script de Teste Automatizado

Salve este script como `test_frida.sh`:

```bash
#!/bin/bash
# Frida Orchestrator - Automated Tests

echo "======================================"
echo "  Frida Orchestrator Tests v0.5.0"
echo "======================================"
echo ""

BASE_URL="http://localhost:8000"
PASS=0
FAIL=0

# Função auxiliar
test_endpoint() {
  local name="$1"
  local url="$2"
  local expected_status="$3"
  
  echo -n "Testing: $name... "
  
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  
  if [ "$status" = "$expected_status" ]; then
    echo "✓ PASS"
    ((PASS++))
  else
    echo "✗ FAIL (got $status, expected $expected_status)"
    ((FAIL++))
  fi
}

# 1. Health Check
test_endpoint "Health Check" "$BASE_URL/health" "200"

# 2. Public Ping
test_endpoint "Public Ping" "$BASE_URL/public/ping" "200"

# 3. Auth Test
test_endpoint "Auth Test (Dev Mode)" "$BASE_URL/auth/test" "200"

# 4. Root Endpoint
test_endpoint "Root HTML" "$BASE_URL/" "200"

# 5. Swagger Docs
test_endpoint "Swagger Docs" "$BASE_URL/docs" "200"

echo ""
echo "======================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "======================================"
```

**Executar:**
```bash
chmod +x test_frida.sh
./test_frida.sh
```

---

## Checklist de Validação Final ✅

Após executar todos os testes, confirme:

- [ ] Health endpoint retorna `ready: true`
- [ ] Todos os serviços críticos mostram status `"ok"`
- [ ] Classificação retorna categoria válida (bolsa/lancheira/garrafa_termica)
- [ ] Imagem processada tem fundo branco (#FFFFFF)
- [ ] Ficha técnica é gerada quando `gerar_ficha=true`
- [ ] Logs mostram `user_id` em todas as requisições
- [ ] Supabase storage funciona (se configurado)
- [ ] Validation rejeita arquivos não-imagem
- [ ] Servidor não crashe com requisições malformadas
- [ ] Startup fail-fast funciona (sem GEMINI_API_KEY → não inicia)
- [ ] Auth em dev mode retorna user_id fake `00000000-0000-0000-0000-000000000000`

---

## Testes de Autenticação em Produção (Futuro)

Quando `AUTH_ENABLED=true` for configurado:

### Teste 1: Requisição Sem Token
```bash
curl http://localhost:8000/process -F "file=@bolsa.jpg"
```
**Esperado:** HTTP 401 "Token de autorização não fornecido"

### Teste 2: Token Inválido
```bash
curl -H "Authorization: Bearer fake_token" \
  http://localhost:8000/process -F "file=@bolsa.jpg"
```
**Esperado:** HTTP 401 "Token inválido"

### Teste 3: Token Expirado
```bash
curl -H "Authorization: Bearer {expired_token}" \
  http://localhost:8000/process -F "file=@bolsa.jpg"
```
**Esperado:** HTTP 401 "Token expirado"

### Teste 4: Token Válido
```bash
curl -H "Authorization: Bearer {valid_supabase_jwt}" \
  http://localhost:8000/process -F "file=@bolsa.jpg"
```
**Esperado:** HTTP 200, processamento normal com `user_id` extraído do JWT

---

## Observações Finais

1. **Ordem de Execução:** Execute os testes na ordem apresentada para evitar dependências.

2. **Logs do Servidor:** Monitore os logs em tempo real para validação:
   ```bash
   tail -f nohup.out  # Se rodando com nohup
   # Ou observe o terminal onde o uvicorn está rodando
   ```

3. **Limpeza:** Após os testes, limpe arquivos temporários:
   ```bash
   rm -f test.txt fake.jpg corrupted.jpg huge.jpg
   ```

4. **Documentação:** Atualize este documento conforme novos testes forem adicionados.

---

**Última atualização:** 2026-01-12
**Versão do Frida:** 0.5.0
