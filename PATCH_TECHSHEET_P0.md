# PATCH P0-BACKEND: Schema v2 para Fichas Técnicas

**Data:** 2026-01-15  
**Versão:** FRIDA v0.5.1 → v0.5.2  
**Status:** ✅ IMPLEMENTADO E TESTADO

---

## 📋 Resumo da Implementação

Implementação do **Schema v2** para fichas técnicas no backend FRIDA, expandindo de 10 para 30 campos organizados em 7 categorias, com migração automática de dados v1 existentes.

---

## 🔧 Arquivos Alterados

### Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `app/schemas/__init__.py` | Módulo de exports para schemas |
| `app/schemas/sheet_schema.py` | Schema v2 completo com migração e validação |

### Arquivos Modificados

| Arquivo | Alterações |
|---------|------------|
| `app/utils.py` | +5 funções auxiliares para sheet data |
| `app/main.py` | PUT endpoint atualizado com lógica v2 |

---

## 📐 Estrutura Schema v2

### 7 Categorias, 30 Campos

```
identification (4 campos)
├── style_number, style_name, season, collection

dimensions (7 campos)
├── width_top_cm, width_bottom_cm, height_cm
├── depth_cm, strap_drop_cm, strap_length_cm, strap_width_cm

materials (8 campos)
├── primary: type, color, pantone, supplier
├── lining: type, color
├── hardware: type, finish, items[]

construction (4 campos)
├── stitch_type, stitch_per_inch, edge_finish, reinforcement_areas[]

compartments (4 campos)
├── external_pockets, internal_pockets, closure_type, special_pockets[]

additional (3 campos)
├── weight_grams, country_of_origin, care_instructions
```

### Enums Suportados

```python
Season = ['SS25', 'FW25', 'SS26', 'FW26', 'Resort', 'Pre-Fall', 'Continuado']
HardwareFinish = ['Dourado', 'Prateado', 'Rose Gold', 'Níquel', 'Fosco', 'Outro']
ClosureType = ['Zíper', 'Magnético', 'Botão', 'Fivela', 'Aberto', 'Outro']
```

---

## 🔄 Funcionalidades Implementadas

### 1. Migração Automática v1 → v2

Fichas existentes são migradas automaticamente na primeira edição:

```python
# Antes (v1)
{"_schema": "bag_v1", "name": "Bolsa", "dimensions": {"width_cm": 30}}

# Depois (v2)
{"_schema": "bag_v2", "identification": {"style_name": "Bolsa"}, "dimensions": {"width_top_cm": 30}}
```

**Log do servidor:**
```
[SHEET] Migrated product fcac62be-... from v1 to v2
```

### 2. Deep Merge para Updates Parciais

Campos não enviados são preservados:

```bash
# Update apenas dimensions
curl -X PUT /products/{id}/sheet -d '{"data": {"dimensions": {"height_cm": 25}}}'

# Resultado: identification, materials, etc. são preservados
```

### 3. Validação de Ranges Numéricos

Retorna HTTP 422 se valores estiverem fora dos limites:

| Campo | Min | Max |
|-------|-----|-----|
| width_top_cm | 1 | 100 |
| width_bottom_cm | 1 | 100 |
| height_cm | 1 | 80 |
| depth_cm | 1 | 50 |
| strap_drop_cm | 5 | 150 |
| strap_length_cm | 10 | 200 |
| strap_width_cm | 0.5 | 15 |
| weight_grams | 50 | 5000 |
| stitch_per_inch | 4 | 20 |
| external_pockets | 0 | 10 |
| internal_pockets | 0 | 10 |

**Exemplo de erro 422:**
```json
{
  "detail": {
    "message": "Validation failed",
    "errors": ["dimensions.width_top_cm: 500 fora do range [1, 100]"]
  }
}
```

---

## ✅ Resultados dos Testes

### Testes Unitários (7/7)

```
✓ Imports OK
✓ v1 detection OK
✓ v2 detection OK
✓ Migration v1→v2 OK
✓ Valid range OK
✓ Invalid range detection OK
✓ Deep merge OK
```

### Testes de API (3/3)

```
✓ POST /products/{id}/sheet → Sheet criada
✓ PUT com dados v2 → Salvo com _schema: "bag_v2"
✓ PUT com range inválido → HTTP 422 retornado
```

### Dados Finais da Sheet de Teste

```json
{
  "version": 2,
  "status": "draft",
  "_schema": "bag_v2",
  "identification": {
    "style_name": "Bolsa Teste v2",
    "season": "SS25",
    "collection": "Premium"
  },
  "dimensions": {
    "width_top_cm": 28,
    "height_cm": 20,
    "depth_cm": 12
  },
  "materials": {
    "primary": {
      "type": "Couro",
      "color": "Preto"
    }
  }
}
```

---

## 🚀 Uso da API

### Criar Sheet (POST)

```bash
curl -X POST http://localhost:8000/products/{PRODUCT_ID}/sheet
```

### Atualizar com Dados v2 (PUT)

```bash
curl -X PUT http://localhost:8000/products/{PRODUCT_ID}/sheet \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "identification": {"style_name": "Bolsa Premium", "season": "SS25"},
      "dimensions": {"width_top_cm": 28, "height_cm": 20},
      "materials": {"primary": {"type": "Couro", "color": "Preto"}}
    },
    "change_summary": "Atualização para Schema v2"
  }'
```

### Obter Sheet (GET)

```bash
curl http://localhost:8000/products/{PRODUCT_ID}/sheet
```

---

## 📦 Funções Adicionadas

### app/schemas/sheet_schema.py

| Função | Descrição |
|--------|-----------|
| `is_v1_schema(data)` | Detecta se dados são v1 |
| `migrate_v1_to_v2(data)` | Converte v1 → v2 |
| `validate_ranges(data)` | Valida limites numéricos |

### app/utils.py

| Função | Descrição |
|--------|-----------|
| `deep_merge(base, updates)` | Merge recursivo de dicts |
| `apply_na_to_empty(data)` | Substitui None por "N/A" |
| `remove_na_values(data)` | Remove "N/A" antes de salvar |
| `get_nested_value(data, path)` | Obtém valor por caminho ("a.b.c") |
| `set_nested_value(data, path, value)` | Define valor por caminho |

---

## 🔗 Retrocompatibilidade

- ✅ Fichas v1 continuam funcionando
- ✅ Migração automática apenas na edição
- ✅ Campos extras são preservados (`Config.extra = "allow"`)
- ✅ Sem alterações no banco de dados (apenas JSONB content)

---

## 📝 Próximos Passos (P1-Frontend)

1. Atualizar componentes React para usar estrutura v2
2. Implementar formulários por categoria
3. Adicionar validação client-side
4. Exibir erros de range de forma amigável

---

**Implementado por:** Antigravity (Google DeepMind)  
**Data de Conclusão:** 2026-01-15  
**Testado com:** Python 3.12, FastAPI, Supabase PostgreSQL
