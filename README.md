# 🎨 Frida Orchestrator

Backend de processamento de imagens e IA para produtos de moda (bolsas, lancheiras, garrafas térmicas).

## 🚀 Quick Start

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
# Edite .env e adicione sua GEMINI_API_KEY
```

### 4. Rodar o servidor

```bash
uvicorn app.main:app --reload --port 8000
```

O servidor estará disponível em: **http://localhost:8000**

---

## 📖 Documentação da API

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🔌 Endpoints

### `GET /health`
Health check da API.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.5.0",
  "gemini_configured": true
}
```

---

### `POST /process`
Endpoint principal de processamento.

**Form Data:**
- `file` (required): Imagem do produto (JPEG, PNG, WebP, GIF)
- `gerar_ficha` (optional): `true` para gerar ficha técnica premium

**Response:**
```json
{
  "status": "sucesso",
  "categoria": "bolsa",
  "estilo": "foto",
  "confianca": 0.95,
  "imagem_base64": "iVBORw0KGgo...",
  "ficha_tecnica": {
    "dados": {...},
    "html": "<html>...</html>"
  }
}
```

---

### `POST /classify`
Apenas classifica uma imagem (sem processar).

**Form Data:**
- `file` (required): Imagem para classificar

**Response:**
```json
{
  "status": "sucesso",
  "classificacao": {
    "item": "bolsa",
    "estilo": "sketch",
    "confianca": 0.92
  }
}
```

---

### `POST /remove-background`
Apenas remove o fundo de uma imagem.

**Form Data:**
- `file` (required): Imagem para processar

**Response:**
```json
{
  "status": "sucesso",
  "imagem_base64": "iVBORw0KGgo..."
}
```

---

## 📁 Estrutura do Projeto

```
componentes/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + rotas
│   ├── config.py            # Configurações
│   ├── utils.py             # Funções auxiliares
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classifier.py      # Classificação via Gemini
│   │   ├── background_remover.py  # Remoção de fundo (rembg)
│   │   └── tech_sheet.py      # Ficha técnica (Jinja2)
│   └── templates/
│       └── tech_sheet_premium.html
├── venv/                    # Ambiente virtual
├── requirements.txt
├── .env.example
├── .env                     # Suas variáveis (não commitado)
└── README.md
```

---

## 🧪 Testando com cURL

### Classificar uma imagem
```bash
curl -X POST http://localhost:8000/classify \
  -F "file=@minha_bolsa.jpg"
```

### Processar com ficha técnica
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@minha_bolsa.jpg" \
  -F "gerar_ficha=true" \
  -o response.json
```

### Apenas remover fundo
```bash
curl -X POST http://localhost:8000/remove-background \
  -F "file=@minha_bolsa.jpg"
```

---

## 🔧 Troubleshooting

### Erro: "GEMINI_API_KEY não configurada"
Certifique-se de que o arquivo `.env` existe e contém:
```
GEMINI_API_KEY=sua_chave_aqui
```

### Erro: "Module not found"
Ative o ambiente virtual:
```bash
source venv/bin/activate
```

### rembg muito lento
Na primeira execução, o modelo U2NET é baixado. Isso é normal e leva alguns minutos.

---

## 📄 Licença

Projeto Frida - Desenvolvimento interno.
