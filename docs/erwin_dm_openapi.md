# erwin Data Modeler — OpenAPI: Engenharia Reversa e Limitações 2.0 vs 3.0

---

## 1. Estrutura de alto nível do padrão OpenAPI 3.0

A especificação OpenAPI 3.0 define as seguintes chaves de **nível raiz** (top-level):

```yaml
openapi: "3.0.3"          # obrigatório — versão da spec
info: {}                   # obrigatório — metadados da API (título, versão, licença...)
servers: []                # opcional  — lista de servidores (URL base)
security: []               # opcional  — segurança global aplicada a todos os paths
tags: []                   # opcional  — agrupadores de operações
paths: {}                  # obrigatório* — endpoints e operações HTTP
components: {}             # opcional  — biblioteca de objetos reutilizáveis
externalDocs: {}           # opcional  — link para documentação externa
```

> `*` O campo `paths` é tecnicamente opcional no 3.0.3 (pode ser um objeto vazio `{}`), mas é obrigatório na prática.

### Subestrutura de `components` (biblioteca de reutilização)

```yaml
components:
  schemas: {}          # Modelos de dados (era 'definitions' no 2.0)
  responses: {}        # Respostas HTTP reutilizáveis
  parameters: {}       # Parâmetros reutilizáveis (path, query, header, cookie)
  requestBodies: {}    # Corpos de requisição reutilizáveis  ← NOVO no 3.0
  headers: {}          # Cabeçalhos de resposta reutilizáveis ← NOVO no 3.0
  securitySchemes: {}  # Esquemas de segurança (era 'securityDefinitions' no 2.0)
  links: {}            # Links hipermídia entre operações    ← NOVO no 3.0
  examples: {}         # Exemplos reutilizáveis              ← NOVO no 3.0
  callbacks: {}        # Callbacks/webhooks                  ← NOVO no 3.0
```

### Comparação de raiz: 2.0 vs 3.0

| Chave raiz 2.0 (Swagger)   | Equivalente em 3.0                       |
|----------------------------|------------------------------------------|
| `swagger: "2.0"`           | `openapi: "3.0.x"`                       |
| `host` + `basePath` + `schemes` | `servers[]`                        |
| `consumes` / `produces`    | *(removido — vai para cada `content:`)* |
| `definitions`              | `components/schemas`                     |
| `parameters` (raiz)        | `components/parameters`                  |
| `responses` (raiz)         | `components/responses`                   |
| `securityDefinitions`      | `components/securitySchemes`             |
| `paths`                    | `paths` *(estrutura interna idêntica)*   |
| *(não existe)*             | `components/requestBodies`               |
| *(não existe)*             | `components/headers`                     |
| *(não existe)*             | `components/links`                       |
| *(não existe)*             | `components/examples`                    |
| *(não existe)*             | `components/callbacks`                   |

---

## 2. Suporte nativo do erwin DM

O erwin Data Modeler suporta **OpenAPI 3.0 como único DBMS alvo**. Não existe um "modo OpenAPI 2.0". Quando você importa um arquivo 2.0, o erwin tenta encaixar a estrutura no modelo interno 3.0 — com perdas.

---

## 3. Comportamento observado na engenharia reversa

### 3.1 Importando OpenAPI 3.0 — estrutura correta

```
openapi_3.0_example (+)
├── components
│   ├── schemas          ← POPULADO: Pedido, PedidoCriacao, PedidoPatch,
│   │   ├── Pedido           ItemPedido, Endereco, Erro
│   │   ├── PedidoCriacao
│   │   ├── PedidoPatch
│   │   ├── ItemPedido
│   │   ├── Endereco
│   │   └── Erro
│   ├── parameters
│   ├── responses
│   ├── securitySchemes
│   ├── links
│   ├── examples
│   ├── headers
│   ├── requestBodies
│   └── callbacks
└── paths
    ├── /pedidos            get / post
    ├── /pedidos/{pedidoId} get / put / patch / delete
    ├── /pedidos/{pedidoId}/itens   get
    ├── /clientes/{clienteId}/pedidos  get
    └── /produtos/upload    post
```

### 3.2 Importando OpenAPI 2.0 — estrutura quebrada

```
openapi_2.0_example (+)
├── components          ← VAZIO ao expandir (todos os subnós sem conteúdo)
│   ├── schemas         ← vazio
│   ├── responses       ← vazio
│   ├── examples        ← vazio
│   ├── parameters      ← vazio
│   ├── headers         ← vazio
│   ├── requestBodies   ← vazio
│   ├── securitySchemes ← vazio
│   ├── links           ← vazio
│   └── callbacks       ← vazio
├── paths               ← IGUAL ao 3.0 (paths são preservados corretamente)
│   ├── /pedidos            get / post
│   ├── /pedidos/{pedidoId} get / put / patch / delete
│   ├── /pedidos/{pedidoId}/itens   get
│   ├── /clientes/{clienteId}/pedidos  get
│   └── /produtos/upload    post
└── definitions         ← EXCLUSIVO DO 2.0: nó raiz extra, com os schemas
    ├── Erro
    ├── Endereco
    ├── ItemPedido
    ├── PedidoPatch
    ├── PedidoCriacao
    └── Pedido
```

### 3.3 Diferenças concretas observadas

| Aspecto                    | OpenAPI 3.0              | OpenAPI 2.0 no erwin              |
|----------------------------|--------------------------|-----------------------------------|
| `components/schemas`       | Populado com entidades   | **Vazio**                         |
| Schemas de dados           | Dentro de `components`   | **Em `definitions` (nó separado)**|
| `paths`                    | Completo, com operações  | Igual — paths são preservados     |
| `components` restantes     | Com conteúdo reutilizável| Todos vazios                      |
| Nó `definitions`           | Não existe               | **Criado fora de `components`**   |

> **Conclusão:** O erwin reconhece a chave `definitions` do 2.0 mas **não a promove** para `components/schemas`. Cria um nó `definitions` extra na raiz do modelo, enquanto `components` fica estruturalmente presente porém sem conteúdo.

---

## 4. Erros EMU-1003 na importação do 2.0

```
EMU-1003: Property type 'JSON_Col_Array_Options' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'

EMU-1003: Property type 'JSON_Col_Format' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'

EMU-1003: Property type 'JSON_Object_Ref_Property' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'
```

**Causa:** No 2.0, parâmetros têm `type`, `format`, `enum` diretamente na raiz do objeto:

```yaml
# 2.0 — type/format no nível do parâmetro (causa EMU-1003)
parameters:
  - name: limit
    in: query
    type: integer       ← direto no parâmetro
    format: int32       ← direto no parâmetro
```

```yaml
# 3.0 — type/format dentro de schema (correto para o erwin)
parameters:
  - name: limit
    in: query
    schema:
      type: integer     ← dentro de schema
      format: int32     ← dentro de schema
```

O modelo interno do erwin espera a estrutura 3.0. Ao receber a 2.0, não consegue aplicar as propriedades e gera um erro EMU-1003 para cada atributo afetado.

---

## 5. O que é perdido ao usar OpenAPI 2.0 diretamente no erwin

### Perdas estruturais

| Elemento 2.0                    | O que ocorre no erwin                                |
|---------------------------------|------------------------------------------------------|
| `definitions`                   | Vira nó raiz separado, não integrado a `components/schemas` |
| `in: body`                      | Não convertido para `requestBody`                    |
| `in: formData`                  | Não convertido para `requestBody` multipart          |
| `consumes` / `produces`         | Ignorados                                            |
| `host` + `basePath` + `schemes` | Não convertidos para `servers`                       |
| `securityDefinitions`           | Não mapeado para `components/securitySchemes`        |
| `parameters` raiz               | Não integrado a `components/parameters`              |
| `responses` raiz                | Não integrado a `components/responses`               |

### Funcionalidades 3.0 inacessíveis via 2.0

| Funcionalidade 3.0      | Motivo                                          |
|-------------------------|-------------------------------------------------|
| `requestBody`           | Conceito não existe no 2.0                      |
| `links`                 | Conceito não existe no 2.0                      |
| `callbacks`             | Conceito não existe no 2.0                      |
| `components/examples`   | Conceito não existe no 2.0                      |
| `components/headers`    | Conceito não existe no 2.0                      |
| Múltiplos `servers`     | 2.0 só suporta um host                          |
| `oneOf` / `anyOf`       | Suporte parcial no 2.0                          |
| Parâmetros `cookie`     | Não suportados no 2.0                           |

---

## 6. Recomendação

Para usar o erwin DM corretamente, **sempre converta o arquivo 2.0 para 3.0 antes de importar**:

```bash
python migrator_2to3.py examples/openapi_2.0_example.yaml
# → output_migrator/openapi_2.0_example_3.0.yaml
```

```
Arquivo 2.0 (Swagger)
        │
        ▼
migrator_2to3.py
        │
        ▼
Arquivo 3.0 convertido
        │
        ▼
erwin DM  →  components/schemas populado
          →  definitions inexistente
          →  sem erros EMU-1003
          →  modelo completo e navegável
```

---

## 7. Mapeamento: tipos de entidade do erwin DM (OpenAPI 3.0)

| Entidade no erwin  | Origem na spec OpenAPI 3.0      |
|--------------------|---------------------------------|
| `callback`         | `components/callbacks`          |
| `encoding`         | encoding dentro de `requestBody`|
| `example`          | `components/examples`           |
| `header`           | `components/headers`            |
| `link`             | `components/links`              |
| `media`            | media type dentro de `content:` |
| `medias`           | agrupador de media types        |
| `operation`        | verbo HTTP dentro de um path    |
| `parameter`        | `components/parameters`         |
| `requestBody`      | `components/requestBodies`      |
| `response`         | `components/responses`          |
| `securityScheme`   | `components/securitySchemes`    |
