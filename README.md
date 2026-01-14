# Frida Orchestrator

Backend de processamento de imagens e IA para produtos de moda (bolsas, lancheiras, garrafas térmicas).

**Versão:** 0.5.4
**Backend:** 100% completo (PRD 00-05)
**Status:** Pronto para frontend

---

## Visão Geral

O Frida Orchestrator é uma API FastAPI que processa imagens de produtos de moda utilizando IA para classificação, remoção de fundo e geração de fichas técnicas.

### Stack Tecnológico

| Categoria | Tecnologia |
|-----------|------------|
| Backend | Python 3.12, FastAPI 0.115 |
| IA | Google Gemini 2.0 Flash Lite |
| Imagem | rembg (U2NET), Pillow |
| Database | Supabase (PostgreSQL) |
| Storage | Supabase Storage (3 buckets) |
| Auth | JWT (HS256) + RBAC |
| PDF | ReportLab |

---

## Quick Start

### 1. Criar ambiente virtual

```bash
cd componentes
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

> **Nota:** O `rembg` pode demorar na primeira execução pois baixa o modelo de IA (~170MB).

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite .env e adicione suas chaves
```

### 4. Rodar o servidor

```bash
uvicorn app.main:app --reload --port 8000
```

O servidor estará disponível em: **http://localhost:8000**

---

## Configuração

### Variáveis Obrigatórias

| Variável | Descrição |
|----------|-----------|
| `GEMINI_API_KEY` | Chave da API Google Gemini (fail-fast) |

### Variáveis Opcionais - Supabase

| Variável | Default | Descrição |
|----------|---------|-----------|
| `SUPABASE_URL` | - | URL do projeto Supabase |
| `SUPABASE_KEY` | - | Service role key |
| `SUPABASE_BUCKET` | `processed-images` | Bucket de imagens |
| `SUPABASE_JWT_SECRET` | - | Secret JWT (se AUTH_ENABLED) |

### Variáveis Opcionais - Servidor

| Variável | Default | Descrição |
|----------|---------|-----------|
| `AUTH_ENABLED` | `false` | Habilita autenticação JWT |
| `HOST` | `0.0.0.0` | Host do servidor |
| `PORT` | `8000` | Porta do servidor |
| `DEBUG` | `true` | Modo debug/reload |

### Limites de Segurança (Hardcoded)

| Limite | Valor |
|--------|-------|
| Tamanho máximo arquivo | 10 MB |
| Dimensão máxima imagem | 8000 px |
| Rate limit /process | 5/minuto |
| Rate limit /process-async | 10/minuto |
| Rate limit /classify | 10/minuto |

---

## Documentação da API

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Endpoints

### Públicos

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/` | Página inicial HTML |
| GET | `/public/ping` | Teste de conectividade |
| GET | `/health` | Health check detalhado |

### Processamento de Imagens

| Método | Path | Descrição | Rate Limit |
|--------|------|-----------|------------|
| POST | `/process` | Pipeline completo (síncrono) | 5/min |
| POST | `/process-async` | Pipeline assíncrono (retorna imediato) | 10/min |
| POST | `/classify` | Apenas classificação | 10/min |
| POST | `/remove-background` | Apenas remoção de fundo | 5/min |

### Jobs Assíncronos (PRD-04)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/jobs` | Lista jobs do usuário |
| GET | `/jobs/{job_id}` | Status detalhado do job |

### Produtos (PRD-02)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/products` | Lista produtos do usuário |
| GET | `/products/{id}` | Detalhes do produto |

### Fichas Técnicas (PRD-05)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/products/{id}/sheet` | Cria ficha técnica |
| GET | `/products/{id}/sheet` | Obtém ficha técnica |
| PUT | `/products/{id}/sheet` | Atualiza dados (versioning) |
| PATCH | `/products/{id}/sheet/status` | Atualiza status |
| GET | `/products/{id}/sheet/versions` | Histórico de versões |
| GET | `/products/{id}/sheet/versions/{v}` | Versão específica |
| DELETE | `/products/{id}/sheet` | Deleta (apenas draft) |
| GET | `/products/{id}/sheet/export/pdf` | Exporta como PDF |

### Autenticação

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/auth/test` | Testa autenticação |

---

## Exemplos de Uso

### Classificar uma imagem

```bash
curl -X POST http://localhost:8000/classify \
  -F "file=@minha_bolsa.jpg"
```

**Response:**
```json
{
  "status": "sucesso",
  "classificacao": {
    "item": "bolsa",
    "estilo": "foto",
    "confianca": 0.95
  }
}
```

### Processar com pipeline completo

```bash
curl -X POST http://localhost:8000/process \
  -F "file=@minha_bolsa.jpg" \
  -F "gerar_ficha=true"
```

**Response:**
```json
{
  "status": "sucesso",
  "product_id": "uuid-do-produto",
  "categoria": "bolsa",
  "estilo": "foto",
  "confianca": 0.95,
  "quality_score": 85,
  "quality_passed": true,
  "images": {
    "original": {"url": "...", "path": "..."},
    "segmented": {"url": "...", "path": "..."},
    "processed": {"url": "...", "path": "..."}
  }
}
```

### Processamento assíncrono

```bash
# 1. Enviar para processamento
curl -X POST http://localhost:8000/process-async \
  -F "file=@minha_bolsa.jpg"

# Response: {"job_id": "abc123", "status": "processing"}

# 2. Verificar status (poll a cada 2s)
curl http://localhost:8000/jobs/abc123

# Response quando completo:
# {"status": "completed", "images": {...}, "quality_score": 85}
```

### Apenas remover fundo

```bash
curl -X POST http://localhost:8000/remove-background \
  -F "file=@minha_bolsa.jpg"
```

### Exportar ficha técnica como PDF

```bash
curl -O http://localhost:8000/products/{product_id}/sheet/export/pdf
```

---

## Arquitetura

### Estrutura do Projeto

```
componentes/
├── app/
│   ├── auth/
│   │   ├── supabase.py          # JWT validation + AuthUser
│   │   └── permissions.py       # RBAC: require_admin, require_role
│   ├── services/
│   │   ├── classifier.py        # Gemini Vision + Structured Output
│   │   ├── background_remover.py # rembg + Pillow
│   │   ├── tech_sheet.py        # Jinja2 template rendering
│   │   ├── storage.py           # Supabase storage + audit
│   │   ├── image_composer.py    # White background + shadow (1200x1200)
│   │   ├── image_pipeline.py    # Pipeline orchestration + rollback
│   │   ├── husk_layer.py        # Quality validation 0-100
│   │   ├── job_worker.py        # Background job processing daemon
│   │   └── pdf_generator.py     # ReportLab PDF generation
│   ├── templates/
│   │   └── tech_sheet_premium.html
│   ├── main.py                  # FastAPI routes + rate limiting
│   ├── config.py                # Settings + Enums + DoS limits
│   ├── database.py              # Supabase CRUD queries
│   └── utils.py                 # Validation utilities
├── SQL para o SUPABASE/         # Migration scripts (01-07)
├── scripts/
│   ├── test_pipeline.py
│   └── test_prd03_complete.py
├── test_images/
├── requirements.txt
├── .env.example
└── README.md
```

### Camada de Serviços

| Serviço | Arquivo | Função |
|---------|---------|--------|
| ClassifierService | `classifier.py` | Classificação via Gemini Structured Output |
| BackgroundRemoverService | `background_remover.py` | Remoção de fundo com rembg |
| TechSheetService | `tech_sheet.py` | Extração Gemini + HTML Jinja2 |
| StorageService | `storage.py` | Upload Supabase + audit trail |
| ImageComposer | `image_composer.py` | Composição 1200x1200 + sombra |
| HuskLayer | `husk_layer.py` | Validação de qualidade 0-100 |
| ImagePipelineSync | `image_pipeline.py` | Orquestração + rollback |
| JobWorkerDaemon | `job_worker.py` | Processamento assíncrono |
| PDFGenerator | `pdf_generator.py` | Exportação PDF |

### Pipeline de Processamento (`/process`)

1. **Validação:** Content-Type → Magic numbers → Pillow integrity → DoS limits
2. **Classificação:** Gemini 2.0 Flash Lite (Structured Output)
3. **Database:** Salva produto na tabela `products`
4. **Image Pipeline:** original → segmented → processed (3 buckets)
5. **Qualidade:** HuskLayer validation (0-100 score)
6. **Tech Sheet:** Opcional - extração Gemini + HTML
7. **Response:** URLs + metadata + product_id + quality_score

---

## Database

### Tabelas (6 tabelas com RLS)

| Tabela | Descrição |
|--------|-----------|
| `users` | Usuários + RBAC (admin/user) |
| `products` | Catálogo de produtos + workflow |
| `images` | Tracking de imagens (3 tipos) |
| `jobs` | Fila de processamento assíncrono |
| `technical_sheets` | Fichas técnicas versionadas |
| `sheet_versions` | Histórico de versões |

### Storage Buckets (3 buckets)

| Bucket | Conteúdo |
|--------|----------|
| `raw` | Imagens originais |
| `segmented` | Imagens sem fundo |
| `processed-images` | Imagens finais (1200x1200) |

### Workflow de Produto

```
draft → pending → approved/rejected → published
```

### Scripts de Migração

Execute na ordem:
1. `01_create_users_table.sql`
2. `02_seed_admin_zero.sql`
3. `03_seed_team_members.sql` (opcional)
4. `04_create_products.sql`
5. `05_create_images.sql`
6. `06_rls_dual_mode.sql`
7. `07_create_jobs.sql`

---

## Autenticação

### Modo Desenvolvimento (AUTH_ENABLED=false)

Retorna usuário fake: `user_id=00000000-...`, `email=dev@frida.com`, `role=admin`

### Modo Produção (AUTH_ENABLED=true)

- JWT Algorithm: HS256
- Audience: "authenticated"
- Requer usuário cadastrado em `users` (HTTP 403 se não existir)

### RBAC (Role-Based Access Control)

```python
from app.auth.permissions import require_admin, require_any, require_role

user: AuthUser = Depends(require_admin)       # Apenas admin
user: AuthUser = Depends(require_any)         # Qualquer autenticado
user: AuthUser = Depends(require_role("mod")) # Role customizado
```

---

## Troubleshooting

### Servidor não inicia

**Erro:** "GEMINI_API_KEY não configurada"

```bash
# Verifique o arquivo .env
cat .env | grep GEMINI_API_KEY
```

### rembg muito lento na primeira execução

Normal - o modelo U2NET (~170MB) é baixado automaticamente.

### WebP rejeitado

Use o header correto de Content-Type:
```bash
curl -F "file=@image.webp;type=image/webp" ...
```

### Imagem com distorção

O rembg pode incluir pessoas/modelos no resultado. Funciona melhor com produtos isolados.

### HTTP 403 em produção

Usuário não cadastrado na tabela `users` do Supabase.

### Rate limit exceeded (429)

Aguarde 1 minuto ou use o endpoint `/process-async` para maior throughput.

---

## Progresso de Desenvolvimento

| PRD | Nome | Status |
|-----|------|--------|
| 00 | Setup & Config | Completo |
| 01 | Auth & Users | Completo |
| 02 | Product Persistence | Completo |
| 03 | Image Pipeline | Completo |
| 04 | Async Jobs | Completo |
| 05 | Tech Sheet & PDF | Completo |
| 06 | Workflow Approval | Pendente (Frontend) |

**Backend:** 100% completo
**Frontend:** Em desenvolvimento

---

## Testes

```bash
# Health check
curl http://localhost:8000/health

# Classificação
curl -X POST http://localhost:8000/classify -F "file=@image.jpg"

# Pipeline completo
python scripts/test_prd03_complete.py

# Testes unitários
python -m pytest tests/
```

---

## Dependências Principais

| Categoria | Pacotes |
|-----------|---------|
| Core | `fastapi==0.115.0`, `uvicorn==0.30.6`, `python-multipart` |
| IA/Imagem | `google-generativeai==0.8.0`, `rembg==2.0.59`, `pillow==10.4.0` |
| Templates | `jinja2==3.1.4` |
| Storage | `supabase==2.7.0` |
| Auth | `PyJWT==2.8.0`, `cryptography==41.0.7` |
| PDF | `reportlab==4.2.5` |
| Rate Limit | `slowapi==0.1.9` |

---

## Documentação Adicional

- `CLAUDE.md` - Instruções para IA assistente
- `CHANGELOG.md` - Histórico de versões
- `CODE_REVIEW.md` - Análise de qualidade (9.2/10)
- `FASE_DE_TESTES.md` - Protocolos de teste
- `TESTS.md` - Documentação de testes

---

## Licença

Projeto Frida - Desenvolvimento interno.
