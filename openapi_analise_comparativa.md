# OpenAPI 2.0 vs 3.x — Análise Comparativa e Engenharia Reversa erwin DM

> Documento técnico de referência — Versão 1.1 | 2026

---

## Índice

1. [Introdução](#1-introdução)
2. [Estrutura de Alto Nível do OpenAPI 3.0](#2-estrutura-de-alto-nível-do-openapi-30)
3. [erwin DM e Engenharia Reversa de OpenAPI](#3-erwin-dm-e-engenharia-reversa-de-openapi)
   - 3.1 [Suporte Nativo do erwin DM](#31-suporte-nativo-do-erwin-dm)
   - 3.2 [O que o erwin DM Efetivamente Importa](#32-o-que-o-erwin-dm-efetivamente-importa)
   - 3.3 [Comportamento Observado na Engenharia Reversa](#33-comportamento-observado-na-engenharia-reversa)
   - 3.4 [Como o erwin Armazena as Informações](#34-como-o-erwin-armazena-as-informações)
   - 3.5 [Análise dos Erros ao Importar OpenAPI 2.0 no erwin](#35-análise-dos-erros-ao-importar-openapi-20-no-erwin)
   - 3.6 [Mapeamento de Tipos de Entidade no erwin DM](#36-mapeamento-de-tipos-de-entidade-no-erwin-dm)
   - 3.7 [Recomendações para Importação no erwin DM](#37-recomendações-para-importação-no-erwin-dm)
4. [Comparativo de Campos: OpenAPI 2.0 vs 3.x](#4-comparativo-de-campos-openapi-20-vs-3x)
5. [Principais Mudanças entre 2.0 e 3.x](#5-principais-mudanças-entre-20-e-3x)
6. [Exemplos YAML](#6-exemplos-yaml)
7. [Scripts Python](#7-scripts-python)
   - 7.1 [`migrador_2to3.py`](#71-migrador_2to3py--openapi-2x--3x)
   - 7.2 [`migrador_3to2.py`](#72-migrador_3to2py--openapi-3x--2x)
   - 7.3 [Análise de Cobertura: o que é possível inferir do 2.0](#73-análise-de-cobertura-o-que-é-possível-inferir-do-20)
   - 7.4 [`validador_openapi.py`](#74-validador_openapipy--validador-de-sintaxe)
8. [Guia de Referência Rápida](#8-guia-de-referência-rápida)
9. [Case: Engenharia Reversa no erwin DM — Do 2.0 ao 3.0](#9-case-engenharia-reversa-no-erwin-dm--do-20-ao-30)
10. [Conclusão](#10-conclusão)

---

## 1. Introdução

O OpenAPI Specification (OAS) é o padrão mais adotado para descrição de APIs REST. A versão 2.0, historicamente conhecida como **Swagger**, foi amplamente adotada e ainda está presente em grande parte das APIs legadas. A versão 3.x representou uma reestruturação significativa do padrão, trazendo maior flexibilidade, suporte a múltiplos servidores, polimorfismo de schemas e melhor separação entre corpo de requisição e parâmetros de URL.

Este documento cobre:

- Estrutura de alto nível do padrão OpenAPI 3.0
- Análise de engenharia reversa do erwin DM ao importar arquivos OpenAPI 2.0 e 3.0
- O que o erwin efetivamente importa e como armazena as informações
- Análise dos erros e comportamentos observados ao importar arquivos 2.0 no importador 3.0 do erwin
- Tabela comparativa completa de campos: o que mudou, o que foi migrado e o que foi descontinuado
- Exemplos YAML comentados — `openapi_2.0_example.yaml` e `openapi_3.0_example.yaml`
- Três scripts Python: migrador 2.x→3.x, migrador 3.x→2.x e validador de sintaxe
- Case prático com o processo completo de engenharia reversa

---

## 2. Estrutura de Alto Nível: OpenAPI 2.0 vs 3.0

### 2.1 Visão comparativa no erwin DM

Antes de entrar nos detalhes, veja como as duas versões aparecem visualmente no erwin DM ao colapsar todos os nós:

| OpenAPI 2.0 — raiz no erwin | OpenAPI 3.0 — raiz no erwin |
|:---:|:---:|
| ![Árvore 2.0 colapsada](erwin_images/erwinDM_OpenAPI%20(7).png) | ![Árvore 3.0 colapsada](erwin_images/erwinDM_OpenAPI%20(4).png) |
| `components` + `paths` + **`definitions`** (extra) | `components` + `paths` (estrutura limpa) |

> O nó `definitions` na raiz é o sinal imediato de que um arquivo 2.0 foi importado sem conversão — ele não existe no padrão 3.0.

---

### 2.2 Estrutura de alto nível: OpenAPI 2.0 (Swagger)

```yaml
swagger: "2.0"            # obrigatório — identifica a versão

info: {}                  # obrigatório — título, versão, contato, licença

host: ""                  # servidor — domínio (ex: api.exemplo.com)
basePath: ""              # servidor — prefixo de URL (ex: /v1)
schemes: []               # servidor — protocolos (https, http)

consumes: []              # media types aceitos globalmente na requisição
produces: []              # media types produzidos globalmente na resposta

security: []              # segurança global
securityDefinitions: {}   # definição dos esquemas de segurança

tags: []                  # agrupadores de operações
externalDocs: {}          # link para documentação externa

parameters: {}            # parâmetros reutilizáveis (nível raiz)
responses: {}             # respostas reutilizáveis (nível raiz)
definitions: {}           # schemas/modelos de dados (equivale a components/schemas)

paths: {}                 # obrigatório — endpoints e operações HTTP
```

**Subestrutura de `definitions`** — todos os schemas de dados ficam aqui:

```yaml
definitions:
  Pedido: {}        # schema de dados
  ItemPedido: {}
  Endereco: {}
  Erro: {}
  # ... demais modelos
```

---

### 2.3 Estrutura de alto nível: OpenAPI 3.0

```yaml
openapi: "3.0.3"   # obrigatório — versão da spec

info: {}           # obrigatório — metadados (título, versão, licença...)

servers: []        # lista de servidores com URL completa (substitui host+basePath+schemes)

security: []       # segurança global aplicada a todos os paths

tags: []           # agrupadores de operações
externalDocs: {}   # link para documentação externa

paths: {}          # obrigatório* — endpoints e operações HTTP

components: {}     # biblioteca central de objetos reutilizáveis (ver abaixo)
```

> `*` `paths` pode ser `{}` tecnicamente, mas é obrigatório na prática.

**Subestrutura de `components`** — substitui todos os objetos de nível raiz do 2.0:

```yaml
components:
  schemas: {}          # Modelos de dados               ← era 'definitions' no 2.0
  responses: {}        # Respostas HTTP reutilizáveis   ← era 'responses' raiz no 2.0
  parameters: {}       # Parâmetros reutilizáveis       ← era 'parameters' raiz no 2.0
  securitySchemes: {}  # Esquemas de segurança          ← era 'securityDefinitions' no 2.0
  requestBodies: {}    # Corpos de requisição           ← NOVO no 3.0
  headers: {}          # Cabeçalhos reutilizáveis       ← NOVO no 3.0
  links: {}            # Links hipermídia               ← NOVO no 3.0
  examples: {}         # Exemplos reutilizáveis         ← NOVO no 3.0
  callbacks: {}        # Callbacks/webhooks             ← NOVO no 3.0
```

---

### 2.4 Comparação de chaves raiz: 2.0 vs 3.0

| Chave raiz 2.0 (Swagger)        | Equivalente em 3.0                        | Diferença |
|----------------------------------|-------------------------------------------|-----------|
| `swagger: "2.0"`                 | `openapi: "3.0.x"`                        | Renomeado |
| `host` + `basePath` + `schemes`  | `servers[]`                               | Consolidado em array |
| `consumes` / `produces`          | *(removido)*                              | Vai para `content:` por operação |
| `definitions`                    | `components/schemas`                      | Movido para `components` |
| `parameters` (raiz)              | `components/parameters`                   | Movido para `components` |
| `responses` (raiz)               | `components/responses`                    | Movido para `components` |
| `securityDefinitions`            | `components/securitySchemes`              | Renomeado + movido |
| `paths`                          | `paths`                                   | Idêntico |
| *(não existe)*                   | `components/requestBodies`                | Novo |
| *(não existe)*                   | `components/headers`                      | Novo |
| *(não existe)*                   | `components/links`                        | Novo |
| *(não existe)*                   | `components/examples`                     | Novo |
| *(não existe)*                   | `components/callbacks`                    | Novo |

### 2.5 OpenAPI 3.1 — Adições

O OpenAPI 3.1 acrescenta mais duas chaves de nível raiz:

```yaml
webhooks: {}           # webhooks de nível raiz (antes só em callbacks)
jsonSchemaDialect: ""  # dialeto JSON Schema usado nos schemas
```

---

## 3. erwin DM e Engenharia Reversa de OpenAPI

### 3.1 Suporte Nativo do erwin DM

O erwin Data Modeler (DM) oferece importação nativa de especificações **OpenAPI 3.0 como único DBMS alvo**. Não existe opção de importação dedicada ao formato 2.0 (Swagger). Ao tentar carregar um arquivo Swagger 2.0 através do importador OpenAPI 3.0, o erwin tenta processar o arquivo, mas encontra incompatibilidades estruturais que resultam em erros e importação parcial.

### 3.2 O que o erwin DM Efetivamente Importa

| Elemento OpenAPI | Mapeado para | Como é Armazenado | Nível de Importação |
|---|---|---|---|
| `info` (title, version, desc) | Metadados do modelo | info.title → Nome do modelo; info.version → versão | ✅ Completo |
| `servers[].url` | Propriedade de conectividade | URL base armazenada como endpoint do modelo físico | ⚠️ Parcial |
| `paths.*` (endpoints) | Entidade/Recurso | Cada path vira um objeto no diagrama; método HTTP vira operação | ✅ Completo |
| `parameters` (query/path/header) | Atributos da operação | Parâmetros viram atributos com tipo, obrigatoriedade e localização | ✅ Completo |
| `requestBody.content.*.schema` | Entidade de request | Schema do body vira entidade separada ou atributos inline | ⚠️ Parcial |
| `responses.*.content.*.schema` | Entidade de response | Schemas de response viram entidades; código HTTP armazenado | ⚠️ Parcial |
| `components/schemas` | Entidades globais | Schemas globais viram entidades reutilizáveis no modelo | ✅ Completo |
| `components/parameters` | Parâmetros globais | Parâmetros reutilizáveis armazenados como atributos globais | ⚠️ Parcial |
| `components/responses` | Respostas globais | Respostas reutilizáveis; schema associado vira entidade | ⚠️ Parcial |
| `components/securitySchemes` | Propriedades de segurança | Armazenados como configuração do modelo; não viram entidades ER | ⚠️ Parcial |
| `tags` | Grupos/Domínios | Tags organizam operações em grupos no modelo visual | ✅ Completo |
| `$ref` (interno) | Relacionamento entre entidades | $ref resolvido; entidade referenciada ligada por relacionamento | ✅ Completo |
| `externalDocs` | — | Campo ignorado pelo importador do erwin DM | ❌ Ignorado |
| `callbacks` / `webhooks` | — | Não existe equivalente no modelo erwin; ignorado | ❌ Ignorado |
| `links` (3.0) | — | Links HATEOAS não têm representação no modelo ER do erwin | ❌ Ignorado |
| `x-extensions` | Propriedades customizadas | Extensões x-* armazenadas como propriedades extras | ✅ Completo |

### 3.3 Comportamento Observado na Engenharia Reversa

#### Importando OpenAPI 3.0 — estrutura correta e completa

![Modelo OpenAPI 3.0 no erwin DM — árvore completa](erwin_images/erwinDM_OpenAPI%20(3).png)

```
openapi_3.0_example (+)
├── components
│   ├── schemas          ← POPULADO com as entidades de dados
│   │   ├── Pedido
│   │   ├── PedidoCriacao
│   │   ├── PedidoPatch
│   │   ├── ItemPedido
│   │   ├── Endereco
│   │   └── Erro
│   ├── parameters       ← com conteúdo
│   ├── responses        ← com conteúdo
│   ├── securitySchemes  ← com conteúdo
│   ├── links
│   ├── examples
│   ├── headers
│   ├── requestBodies
│   └── callbacks
└── paths
    ├── /pedidos                      get / post
    ├── /pedidos/{pedidoId}           get / put / patch / delete
    ├── /pedidos/{pedidoId}/itens     get
    ├── /clientes/{clienteId}/pedidos get
    └── /produtos/upload              post
```

#### Importando OpenAPI 2.0 — estrutura quebrada (comportamento real observado)

| Visão colapsada | Visão expandida |
|:---:|:---:|
| ![Árvore 2.0 — nós raiz](erwin_images/erwinDM_OpenAPI%20(7).png) | ![Árvore 2.0 — definitions expandido](erwin_images/erwinDM_OpenAPI%20(2).png) |
| Revela os 3 nós raiz: `components`, `paths`, `definitions` | `definitions` expandido com os 6 schemas, `components` vazio |

```
openapi_2.0_example (+)
├── components          ← VAZIO ao expandir todos os subnós
│   ├── schemas         ← vazio (schemas NÃO foram promovidos)
│   ├── responses       ← vazio
│   ├── examples        ← vazio
│   ├── parameters      ← vazio
│   ├── headers         ← vazio
│   ├── requestBodies   ← vazio
│   ├── securitySchemes ← vazio
│   ├── links           ← vazio
│   └── callbacks       ← vazio
├── paths               ← IGUAL ao 3.0 (único elemento preservado corretamente)
│   ├── /pedidos                      get / post
│   ├── /pedidos/{pedidoId}           get / put / patch / delete
│   ├── /pedidos/{pedidoId}/itens     get
│   ├── /clientes/{clienteId}/pedidos get
│   └── /produtos/upload              post
└── definitions         ← NÓ EXTRA criado na raiz — não existe no padrão 3.0
    ├── Erro
    ├── Endereco
    ├── ItemPedido
    ├── PedidoPatch
    ├── PedidoCriacao
    └── Pedido
```

#### Diferenças concretas entre os dois modelos no erwin

| Aspecto                    | OpenAPI 3.0 importado    | OpenAPI 2.0 importado                   |
|----------------------------|--------------------------|-----------------------------------------|
| `components/schemas`       | Populado com entidades   | **Vazio**                               |
| Schemas de dados           | Dentro de `components`   | **Em `definitions` (nó raiz separado)** |
| `paths`                    | Completo, com operações  | **Igual** — paths são preservados       |
| `components` restantes     | Com conteúdo reutilizável| **Todos vazios**                        |
| Nó `definitions`           | Não existe               | **Criado fora de `components`**         |
| Erros de importação        | Nenhum                   | **Dezenas de EMU-1003**                 |

> **Conclusão:** o erwin reconhece a chave `definitions` do 2.0 mas **não a promove** para `components/schemas`. Os schemas ficam em um nó `definitions` isolado, enquanto `components` permanece estruturalmente presente porém sem conteúdo. O único elemento que sobrevive íntegro são os `paths`.

### 3.4 Como o erwin Armazena as Informações

Internamente, o erwin DM representa a especificação OpenAPI em um modelo orientado a recursos (não puramente relacional). Os principais aspectos de armazenamento são:

- **Recursos e Operações:** cada path (`/recurso`) se torna uma entidade-recurso. Cada método HTTP (GET, POST, etc.) vira uma operação associada ao recurso.
- **Schemas/Entidades:** schemas definidos em `components/schemas` (3.0) ou `definitions` (2.0) são importados como entidades independentes. Relacionamentos são criados quando `$ref` é usado.
- **Parâmetros:** parâmetros de query, path e header viram atributos da operação com metadados (tipo, obrigatoriedade, localização).
- **Request Body:** o schema do `requestBody` é associado à operação; schemas inline viram entidades ad-hoc; schemas referenciados (`$ref`) apontam para a entidade global.
- **Segurança:** esquemas de segurança são armazenados como configurações globais do modelo, não como entidades ER.
- **Metadados:** `info.title`, `info.version` e `info.description` são armazenados como propriedades do modelo.

### 3.5 Análise dos Erros ao Importar OpenAPI 2.0 no erwin

#### Erros EMU-1003 — causa raiz

```
EMU-1003: Property type 'JSON_Col_Array_Options' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'

EMU-1003: Property type 'JSON_Col_Format' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'

EMU-1003: Property type 'JSON_Object_Ref_Property' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'
```

No 2.0, `type`, `format` e `enum` ficam **diretamente no parâmetro**. No modelo interno do erwin (baseado em 3.0), essas propriedades devem estar dentro de um bloco `schema: {}`. Como o erwin não faz essa conversão automaticamente, gera um EMU-1003 para cada atributo afetado.

```yaml
# 2.0 — causa EMU-1003
parameters:
  - name: limit
    in: query
    type: integer       # ← direto no parâmetro
    format: int32       # ← direto no parâmetro

# 3.0 — estrutura esperada pelo erwin
parameters:
  - name: limit
    in: query
    schema:
      type: integer     # ← dentro de schema
      format: int32     # ← dentro de schema
```

#### Tabela de erros e comportamentos

| Tipo de Erro/Comportamento | Descrição | Solução Recomendada | Severidade |
|---|---|---|---|
| Erro de versão | erwin espera `openapi: 3.x.x`. Não reconhece `swagger: 2.0` como válido. | Migrar o arquivo para 3.0 antes de importar. | 🔴 Crítico |
| Falha em `securityDefinitions` | erwin não processa `securityDefinitions`. Em 3.0 é `components/securitySchemes`. | Converter com migrador. | 🟠 Alto |
| Parâmetros `body`/`formData` | erwin não mapeia `in: body` e `in: formData` para entidades. Ficam sem correspondência. | Em 3.0 tornam-se `requestBody`. | 🟠 Alto |
| `$ref` desatualizado | Referências `#/definitions/X` são inválidas em 3.0. Os $ref quebram. | O migrador atualiza todos os $ref automaticamente. | 🟠 Alto |
| `definitions` como nó raiz extra | erwin não promove `definitions` para `components/schemas`. | Converter para 3.0 antes de importar. | 🟠 Alto |
| EMU-1003 em massa | `type`/`format`/`enum` direto no parâmetro não é válido no modelo 3.0 do erwin. | Converter para 3.0 (propriedades vão para `schema:{}`). | 🟠 Alto |
| `consumes`/`produces` ignorados | Campos globais ignorados pelo importador 3.0. | Em 3.0 o media type fica em `content{}`. | 🟡 Médio |
| `type: file` | `type: file` em formData pode gerar schema inválido. | Em 3.0 usar `format: binary` dentro de `requestBody`. | 🟡 Médio |
| `host`/`basePath`/`schemes` | erwin pode não montar a URL base corretamente a partir dos três campos. | Em 3.0 a URL completa está em `servers[].url`. | 🟢 Baixo |
| Campos `x-` (extensões) | Extensões `x-*` são aceitas em ambas versões. | Sem ação necessária. | ℹ️ Info |

### 3.6 Mapeamento de Tipos de Entidade no erwin DM

O editor de objetos do erwin para OpenAPI 3.0 lista os seguintes tipos de entidade. O modelo 3.0 exibe o objeto `openapi_3.0_example` selecionado; o modelo 2.0 exibe `openapi_2.0_example` — repare que a lista de tipos é idêntica, mas a diferença está no conteúdo gerado.

| Editor — `openapi_3.0_example` / `requestBody` selecionado | Editor — `openapi_2.0_example` selecionado |
|:---:|:---:|
| ![Editor de objeto OpenAPI 3.0](erwin_images/erwinDM_OpenAPI%20(1).png) | ![Editor de objeto OpenAPI 2.0](erwin_images/erwinDM_OpenAPI%20(5).png) |
| Lista de tipos idêntica — `requestBody` destacado em azul | Lista de tipos idêntica — modelo 2.0 selecionado |

> **Detalhe:** a lista de tipos de entidade é **idêntica** nos dois modelos — o erwin usa o mesmo esquema interno. A diferença está no conteúdo gerado: no 3.0, `requestBody` é populado; no 2.0, fica vazio porque o erwin não converte `in: body` automaticamente.

| Entidade no erwin  | Origem na spec OpenAPI 3.0       |
|--------------------|----------------------------------|
| `callback`         | `components/callbacks`           |
| `encoding`         | encoding dentro de `requestBody` |
| `example`          | `components/examples`            |
| `header`           | `components/headers`             |
| `link`             | `components/links`               |
| `media`            | media type dentro de `content:`  |
| `medias`           | agrupador de media types         |
| `operation`        | verbo HTTP dentro de um path     |
| `parameter`        | `components/parameters`          |
| `requestBody`      | `components/requestBodies`       |
| `response`         | `components/responses`           |
| `securityScheme`   | `components/securitySchemes`     |

> O tipo `requestBody` **só existe** no modelo OpenAPI 3.0 do erwin. Ao importar um 2.0, os parâmetros `in: body` e `in: formData` **não são automaticamente transformados** em `requestBody`.

### 3.7 Recomendações para Importação no erwin DM

1. **Converter** o arquivo 2.0 para 3.0 usando o script `migrador_2to3.py` fornecido.
2. **Validar** o arquivo resultante com `validador_openapi.py` para garantir que não há erros de sintaxe.
3. **Certificar-se** de que schemas estão em `components/schemas` (não em `definitions`).
4. **Usar** `requestBody` em vez de `in: body` e `in: formData`.
5. **Após importação**, verificar manualmente se todos os schemas foram gerados e se os relacionamentos por `$ref` estão corretos.

---

## 4. Comparativo de Campos: OpenAPI 2.0 vs 3.x

**Legenda:**
- ✅ `MANTIDO` — campo idêntico em ambas as versões
- 🟡 `ALTERADO` — existe em ambas, mas com nome, localização ou comportamento diferente
- 🟢 `NOVO` — inexistente no 2.0, adicionado no 3.x
- 🔴 `REMOVIDO` — presente no 2.0, descontinuado no 3.x (pode ter equivalente)

| Categoria | Campo 2.0 | Campo 3.0 | Status | Observação |
|---|---|---|---|---|
| Versão | `swagger: "2.0"` | `openapi: "3.0.3"` | 🟡 ALTERADO | Campo raiz renomeado |
| Info | `info.title` | `info.title` | ✅ MANTIDO | Sem alteração |
| Info | `info.version` | `info.version` | ✅ MANTIDO | Sem alteração |
| Info | `info.description` | `info.description` | ✅ MANTIDO | Sem alteração |
| Info | `info.termsOfService` | `info.termsOfService` | ✅ MANTIDO | Sem alteração |
| Info | `info.contact` | `info.contact` | ✅ MANTIDO | Sem alteração |
| Info | `info.license` | `info.license` | ✅ MANTIDO | Sem alteração |
| Servidor | `host` | *(removido)* | 🔴 REMOVIDO | Substituído por `servers[].url` |
| Servidor | `basePath` | *(removido)* | 🔴 REMOVIDO | Substituído por `servers[].url` |
| Servidor | `schemes` | *(removido)* | 🔴 REMOVIDO | Substituído por `servers[].url` |
| Servidor | *(não existe)* | `servers[].url` | 🟢 NOVO | Array de servidores com URL completa + variáveis |
| Servidor | *(não existe)* | `servers[].description` | 🟢 NOVO | Descrição do ambiente (prod, sandbox...) |
| Servidor | *(não existe)* | `servers[].variables` | 🟢 NOVO | Variáveis de URL substituíveis |
| Conteúdo | `consumes` (raiz/op) | *(removido)* | 🔴 REMOVIDO | Substituído por `requestBody.content` |
| Conteúdo | `produces` (raiz/op) | *(removido)* | 🔴 REMOVIDO | Substituído por `responses.content` |
| Conteúdo | *(não existe)* | `requestBody.content` | 🟢 NOVO | Media types declarados por operação com schema específico |
| Schemas | `definitions.*` | `components/schemas/*` | 🟡 ALTERADO | Movido para `components`; $ref atualizado correspondentemente |
| Schemas | `type: file` (formData) | `format: binary` | 🟡 ALTERADO | `type:file` substituído por `type:string + format:binary` |
| Parâmetros | `parameters` (raiz) | `components/parameters/*` | 🟡 ALTERADO | Movido para `components/parameters` |
| Parâmetros | `in: body` | `requestBody` | 🟡 ALTERADO | `in:body` removido; usa `requestBody` separado |
| Parâmetros | `in: formData` | `requestBody multipart` | 🟡 ALTERADO | `in:formData` removido; usa `requestBody` com `multipart/form-data` |
| Parâmetros | `in: query/path/header` | `in: query/path/header` | ✅ MANTIDO | Locais comuns mantidos |
| Parâmetros | *(não existe)* | `in: cookie` | 🟢 NOVO | Suporte nativo a parâmetros de cookie |
| Parâmetros | `type/format` direto | dentro de `schema{}` | 🟡 ALTERADO | Em 3.0, `type/format` ficam dentro do objeto `schema:` |
| Parâmetros | *(não existe)* | `content{}` em parâmetro | 🟢 NOVO | Parâmetro pode usar `content{}` para media types complexos |
| Respostas | `responses` (raiz) | `components/responses/*` | 🟡 ALTERADO | Movido para `components/responses` |
| Respostas | `response.schema` | `response.content.*.schema` | 🟡 ALTERADO | Schema agora está dentro de `content.<mediatype>.schema` |
| Respostas | `response.examples` | `response.content.*.examples` | 🟡 ALTERADO | Exemplos agora por media type |
| Respostas | `headers.*.type` | `headers.*.schema.type` | 🟡 ALTERADO | Headers em respostas também usam `schema{}` |
| Segurança | `securityDefinitions.*` | `components/securitySchemes/*` | 🟡 ALTERADO | Movido para `components/securitySchemes` |
| Segurança | `type: basic` | `type: http, scheme: basic` | 🟡 ALTERADO | `basic` vira subscheme do tipo `http` |
| Segurança | `type: apiKey` (bearer) | `type: http, scheme: bearer` | 🟡 ALTERADO | JWT bearer vira subscheme do tipo `http` |
| Segurança | `type: apiKey` | `type: apiKey` | ✅ MANTIDO | Comportamento idêntico |
| Segurança | `type: oauth2, flow: ...` | `type: oauth2, flows: {…}` | 🟡 ALTERADO | `flow` singular → `flows` plural; múltiplos flows por scheme |
| Segurança | `flow: accessCode` | `flows.authorizationCode` | 🟡 ALTERADO | Nome do flow renomeado |
| Segurança | `flow: application` | `flows.clientCredentials` | 🟡 ALTERADO | Nome do flow renomeado |
| Segurança | *(não existe)* | `type: openIdConnect` | 🟢 NOVO | Suporte nativo a OpenID Connect |
| Segurança | *(não existe)* | `type: mutualTLS` | 🟢 NOVO | Autenticação mTLS (OpenAPI 3.1) |
| Components | *(não existe)* | `components/requestBodies` | 🟢 NOVO | Request bodies reutilizáveis |
| Components | *(não existe)* | `components/headers` | 🟢 NOVO | Headers reutilizáveis |
| Components | *(não existe)* | `components/examples` | 🟢 NOVO | Exemplos nomeados e reutilizáveis |
| Components | *(não existe)* | `components/links` | 🟢 NOVO | Links entre operações (HATEOAS) |
| Components | *(não existe)* | `components/callbacks` | 🟢 NOVO | Webhooks/callbacks definidos por operação |
| Components | *(não existe)* | `components/pathItems` | 🟢 NOVO | Path items reutilizáveis (OpenAPI 3.1) |
| Paths | `paths.*` | `paths.*` | ✅ MANTIDO | Estrutura de paths mantida |
| Paths | *(não existe)* | `webhooks` (raiz) | 🟢 NOVO | Webhooks de nível raiz (OpenAPI 3.1) |
| Operação | `operationId` | `operationId` | ✅ MANTIDO | Sem alteração |
| Operação | `tags` | `tags` | ✅ MANTIDO | Sem alteração |
| Operação | `summary` | `summary` | ✅ MANTIDO | Sem alteração |
| Operação | `description` | `description` | ✅ MANTIDO | Sem alteração |
| Operação | `deprecated` | `deprecated` | ✅ MANTIDO | Sem alteração |
| Operação | `externalDocs` | `externalDocs` | ✅ MANTIDO | Sem alteração |
| Operação | *(não existe)* | `callbacks` | 🟢 NOVO | Callbacks/webhooks definidos por operação |
| Operação | *(não existe)* | `servers` (por operação) | 🟢 NOVO | Override de server por operação |
| Schema | `x-*` | `x-*` | ✅ MANTIDO | Extensões mantidas em ambas versões |
| Schema | `allOf` | `allOf` | ✅ MANTIDO | Sem alteração |
| Schema | *(não existe)* | `oneOf` | 🟢 NOVO | Discriminador polimórfico |
| Schema | *(não existe)* | `anyOf` | 🟢 NOVO | Discriminador polimórfico |
| Schema | *(não existe)* | `not` | 🟢 NOVO | Negação de schema |
| Schema | `readOnly` | `readOnly` | ✅ MANTIDO | Sem alteração |
| Schema | *(não existe)* | `writeOnly` | 🟢 NOVO | Campo somente escrita (não aparece em GET) |
| Schema | *(não existe)* | `nullable` | 🟢 NOVO | Permite valor null além do tipo declarado |
| Schema | *(não existe)* | `discriminator` | 🟢 NOVO | Mapeamento de propriedade para subschemas |
| Schema | `example` (inline) | `example` / `examples` | 🟡 ALTERADO | 3.0 adiciona `examples` plural como objeto nomeado |
| Misc | `tags` (raiz) | `tags` (raiz) | ✅ MANTIDO | Sem alteração |
| Misc | `externalDocs` (raiz) | `externalDocs` (raiz) | ✅ MANTIDO | Sem alteração |
| Misc | `security` (raiz) | `security` (raiz) | ✅ MANTIDO | Sem alteração |

---

## 5. Principais Mudanças entre 2.0 e 3.x

### 5.1 Reestruturação do Servidor

A mudança mais visível é a eliminação dos campos `host`, `basePath` e `schemes`, substituídos pelo array `servers`:

```yaml
# OpenAPI 2.0
host: api.exemplo.com
basePath: /v1
schemes:
  - https

# OpenAPI 3.0
servers:
  - url: https://api.exemplo.com/v1
    description: Produção
  - url: https://sandbox.exemplo.com/v1
    description: Sandbox
```

### 5.2 Corpo da Requisição

Em 2.0, o body era um parâmetro com `in: body`. Em 3.0 existe o objeto `requestBody` separado, permitindo especificar diferentes representações com schemas distintos:

```yaml
# OpenAPI 2.0
parameters:
  - name: body
    in: body
    required: true
    schema:
      $ref: "#/definitions/Pedido"

# OpenAPI 3.0
requestBody:
  required: true
  content:
    application/json:
      schema:
        $ref: "#/components/schemas/Pedido"
    application/xml:
      schema:
        $ref: "#/components/schemas/Pedido"
```

### 5.3 Upload de Arquivo

```yaml
# OpenAPI 2.0
parameters:
  - name: arquivo
    in: formData
    type: file         # ← type: file (exclusivo do 2.0)

# OpenAPI 3.0
requestBody:
  content:
    multipart/form-data:
      schema:
        properties:
          arquivo:
            type: string
            format: binary   # ← substitui type: file
```

### 5.4 Componentes Reutilizáveis

O 2.0 tinha seções de nível raiz separadas. O 3.0 consolida tudo sob `components`:

| OpenAPI 2.0 (raiz) | OpenAPI 3.0 (`components/*`) |
|---|---|
| `definitions/*` | `components/schemas/*` |
| `parameters/*` | `components/parameters/*` |
| `responses/*` | `components/responses/*` |
| `securityDefinitions/*` | `components/securitySchemes/*` |
| *(não existe)* | `components/requestBodies/*` 🟢 |
| *(não existe)* | `components/headers/*` 🟢 |
| *(não existe)* | `components/examples/*` 🟢 |
| *(não existe)* | `components/links/*` 🟢 |
| *(não existe)* | `components/callbacks/*` 🟢 |

### 5.5 Segurança

```yaml
# OpenAPI 2.0
securityDefinitions:
  BearerAuth:
    type: apiKey
    in: header
    name: Authorization
  BasicAuth:
    type: basic
  OAuth2:
    type: oauth2
    flow: accessCode          # ← flow singular, um por scheme
    authorizationUrl: "..."
    tokenUrl: "..."
    scopes: {}

# OpenAPI 3.0
components:
  securitySchemes:
    BearerAuth:
      type: http              # ← tipo http com scheme bearer
      scheme: bearer
      bearerFormat: JWT
    BasicAuth:
      type: http
      scheme: basic
    OAuth2:
      type: oauth2
      flows:                  # ← flows plural, múltiplos suportados
        authorizationCode:    # ← accessCode → authorizationCode
          authorizationUrl: "..."
          tokenUrl: "..."
          scopes: {}
```

### 5.6 Polimorfismo de Schemas

| Construção | 2.0 | 3.0 |
|---|---|---|
| `allOf` | ✅ | ✅ |
| `oneOf` | ❌ | ✅ |
| `anyOf` | ❌ | ✅ |
| `not` | ❌ | ✅ |
| `discriminator` | ❌ | ✅ |
| `nullable` | ❌ | ✅ |
| `writeOnly` | ❌ | ✅ |

---

## 6. Exemplos YAML

Dois arquivos de referência foram criados modelando a mesma API (**Gestão de Pedidos**) para facilitar comparação direta.

### 6.1 Recursos Modelados nos Exemplos

| Endpoint | Métodos | Descrição |
|---|---|---|
| `/pedidos` | GET, POST | Listagem paginada com filtros e criação |
| `/pedidos/{pedidoId}` | GET, PUT, PATCH, DELETE | CRUD completo |
| `/pedidos/{pedidoId}/itens` | GET | Sub-recurso de itens |
| `/clientes/{clienteId}/pedidos` | GET | Multi-tag (clientes + pedidos) |
| `/produtos/upload` | POST | Upload multipart/form-data |

### 6.2 Schemas Modelados

`Pedido`, `PedidoCriacao`, `PedidoPatch`, `ItemPedido`, `Endereco`, `Erro`

### 6.3 Atributos Cobertos por Versão

**`openapi_2.0_example.yaml`:** `swagger`, `info`, `host`, `basePath`, `schemes`, `consumes`, `produces`, `security`, `securityDefinitions` (apiKey/basic/oauth2), `tags`, `parameters` (raiz), `responses` (raiz), paths com GET/POST/PUT/PATCH/DELETE, `in:body`, `in:formData`, `in:path/query/header`, `definitions`, `$ref`, `readOnly`, enums, formats, `additionalProperties`, `example`

**`openapi_3.0_example.yaml`:** `openapi`, `info`, `servers` (múltiplos), `security`, `components/schemas`, `components/parameters`, `components/responses`, `components/securitySchemes` (http-bearer/basic/oauth2-authorizationCode), `components/links`, `components/examples`, `requestBody`, `content` (json/xml/multipart), `format:binary`, responses com `content` e `examples` nomeados, `tags`, `externalDocs`

---

## 7. Scripts Python

### 7.1 `migrador_2to3.py` — OpenAPI 2.x → 3.x

```bash
python migrador_2to3.py entrada.yaml saida.yaml
python migrador_2to3.py entrada.yaml            # salva em output_migrator/
```

**Cobertura de migração — o que é convertido automaticamente:**

| Elemento 2.0 | Resultado em 3.0 | Observação |
|---|---|---|
| `swagger: "2.0"` | `openapi: "3.0.3"` | |
| `host` + `basePath` + `schemes` | `servers[].url` + `description` | https → "Produção", http → "Desenvolvimento" |
| `consumes` (global/operação) | `requestBody.content.<mime>` | Aplicado por operação |
| `produces` (global/operação) | `responses.<code>.content.<mime>` | Aplicado por operação |
| `definitions.*` | `components/schemas.*` | $ref atualizados automaticamente |
| `parameters.*` (raiz) | `components/parameters.*` | $ref atualizados automaticamente |
| `responses.*` (raiz) | `components/responses.*` | $ref atualizados automaticamente |
| `securityDefinitions.*` | `components/securitySchemes.*` | Ver conversões abaixo |
| `type: basic` | `type: http, scheme: basic` | |
| `type: apiKey` (header Authorization) | `type: http, scheme: bearer, bearerFormat: JWT` | Detecta pelo nome do header |
| `type: apiKey` (outros) | `type: apiKey` | Mantido igual |
| `oauth2, flow: accessCode` | `flows.authorizationCode` | |
| `oauth2, flow: implicit` | `flows.implicit` | |
| `oauth2, flow: password` | `flows.password` | |
| `oauth2, flow: application` | `flows.clientCredentials` | |
| `in: body` | `requestBody` com `content.<mime>.schema` | |
| `in: formData, type: file` | `requestBody multipart/form-data, format: binary` | |
| `in: formData` (campo) | `requestBody multipart/form-data, schema.properties` | |
| `type`/`format`/`enum` direto no param | `schema: {type, format, enum}` | Estrutura 3.0 |
| `#/definitions/X` | `#/components/schemas/X` | Recursivo em toda a estrutura |
| `#/parameters/X` | `#/components/parameters/X` | |
| `#/responses/X` | `#/components/responses/X` | |
| `headers` em respostas | `headers.<name>.schema` | type/format movidos para schema |
| `operationId`, `tags`, `summary`, `description`, `externalDocs`, `security`, `deprecated` | Mantidos idênticos | |

**Correção aplicada (v1.1):**

> **Bug YAML Anchors** — versões anteriores geravam `&id001`/`*id001` ao expandir `produces` com múltiplos content types. Corrigido: cada media type recebe uma cópia independente do schema (`deep_copy`), sem anchors YAML no output.

### 7.2 `migrador_3to2.py` — OpenAPI 3.x → 2.x

```bash
python migrador_3to2.py entrada.yaml saida.yaml
python migrador_3to2.py entrada.yaml            # imprime na stdout
```

**Cobertura de migração:**
- `openapi` → `swagger: "2.0"`
- `servers[]` → `host` + `basePath` + `schemes`
- `components/schemas` → `definitions`
- `components/parameters` → `parameters` (raiz)
- `components/responses` → `responses` (raiz)
- `components/securitySchemes` → `securityDefinitions`
- `requestBody` (json/xml) → `in: body`
- `requestBody multipart/form-data` → `in: formData`
- `format: binary` → `type: file`
- `responses content` → `schema` + `produces`
- `parameters schema{}` → tipo direto no parâmetro
- Todos os `$ref` atualizados: `#/components/schemas/` → `#/definitions/`, etc.

**Limitações inerentes ao formato 2.0:**
- `servers[]` múltiplos: usa apenas o primeiro; demais salvos em `x-servers`
- `links`, `callbacks` e `webhooks`: descartados (não existem em 2.0)
- `oneOf` / `anyOf` / `not`: sem equivalente direto em 2.0
- Multiple content types por resposta: usa o primeiro (JSON preferido)
- `in: cookie` → convertido para `in: header` com aviso
- OAuth2 com múltiplos flows: apenas o primeiro flow é exportado

### 7.3 Análise de Cobertura: o que é possível inferir do 2.0

A migração automática tem um teto definido pelo que o formato 2.0 **registra explicitamente**. Abaixo a análise completa de cada funcionalidade 3.0 e se ela pode ser gerada a partir de um arquivo 2.0:

**Legenda:**
- ✅ `MIGRADO` — convertido automaticamente pelo script
- 🟡 `PARCIAL` — convertido com perda ou aproximação
- 🔴 `INFERÍVEL` — não existe no 2.0, mas pode ser deduzido com heurística
- ❌ `IMPOSSÍVEL` — não há como obter essa informação a partir do 2.0

| Funcionalidade 3.0 | Status | Por quê |
|---|---|---|
| `openapi` versão | ✅ MIGRADO | Valor fixo `3.0.3` |
| `info.*` (título, versão, contato, licença) | ✅ MIGRADO | Estrutura idêntica |
| `servers[].url` | ✅ MIGRADO | Montado de `host + basePath + scheme` |
| `servers[].description` | 🔴 INFERÍVEL | Heurística por scheme: https → "Produção", http → "Desenvolvimento" ✅ implementado |
| `servers[].variables` | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| Servidor sandbox / localhost | ❌ IMPOSSÍVEL | O 2.0 só tem um `host`; URLs adicionais não têm fonte |
| `tags.*` | ✅ MIGRADO | Estrutura idêntica |
| `security` (global) | ✅ MIGRADO | Estrutura idêntica |
| `paths.*` (estrutura) | ✅ MIGRADO | Estrutura interna compatível |
| `requestBody` (de `in: body`) | ✅ MIGRADO | Conversão direta |
| `requestBody` (de `in: formData`) | ✅ MIGRADO | Conversão para multipart |
| `requestBody.description` | ✅ MIGRADO | Vem do campo `description` do parâmetro body |
| `requestBody` reutilizável em `components` | ❌ IMPOSSÍVEL | 2.0 não tem `requestBodies` como componente |
| `responses.content.<mime>.schema` | ✅ MIGRADO | Expandido a partir de `produces` |
| `responses.content.<mime>.examples` | 🟡 PARCIAL | `example` inline migrado; named `examples` não existem no 2.0 |
| `components/schemas` | ✅ MIGRADO | De `definitions` |
| `components/parameters` | ✅ MIGRADO | De `parameters` raiz |
| `components/responses` | ✅ MIGRADO | De `responses` raiz |
| `components/securitySchemes` | ✅ MIGRADO | De `securityDefinitions` |
| `components/requestBodies` | ❌ IMPOSSÍVEL | Conceito não existe no 2.0 |
| `components/headers` | ❌ IMPOSSÍVEL | Headers de resposta existem no 2.0, mas não como componente reutilizável |
| `components/links` | ❌ IMPOSSÍVEL | Conceito não existe no 2.0 |
| `components/examples` | ❌ IMPOSSÍVEL | Named examples não existem no 2.0 |
| `components/callbacks` | ❌ IMPOSSÍVEL | Conceito não existe no 2.0 |
| `parameters.schema{}` (envoltório) | ✅ MIGRADO | `type/format/enum` movidos para `schema:` |
| `parameters.style` / `explode` | 🟡 PARCIAL | `collectionFormat` do 2.0 tem equivalente aproximado, não implementado |
| `parameters` `in: cookie` | ❌ IMPOSSÍVEL | Não existe no 2.0 (convertido de header se necessário) |
| `nullable: true` | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| `writeOnly` | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| `oneOf` / `anyOf` / `not` | ❌ IMPOSSÍVEL | Não existem no 2.0 |
| `discriminator` | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| `allOf` | ✅ MIGRADO | Existe no 2.0, preservado |
| `readOnly` | ✅ MIGRADO | Existe no 2.0, preservado |
| `externalDocs` | ✅ MIGRADO | Estrutura idêntica |
| Bearer JWT (de `apiKey` Authorization) | ✅ MIGRADO | Heurística pelo nome do header ✅ implementado |
| OAuth2 múltiplos flows | ❌ IMPOSSÍVEL | 2.0 suporta apenas 1 flow por scheme |
| `openIdConnect` security type | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| Named `examples` em requestBody | ❌ IMPOSSÍVEL | 2.0 só tem `example` inline |
| `callbacks` em operações | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| `servers` por operação (override) | ❌ IMPOSSÍVEL | Não existe no 2.0 |
| YAML sem anchors (`&id`/`*id`) | ✅ CORRIGIDO | Bug resolvido com `deep_copy` por content type |

**Resumo quantitativo:**

| Status | Quantidade |
|---|---|
| ✅ MIGRADO (automático e completo) | 24 |
| 🟡 PARCIAL (com perda aceitável) | 2 |
| 🔴 INFERÍVEL (heurística implementada) | 2 |
| ❌ IMPOSSÍVEL (limitação estrutural do 2.0) | 15 |

> As 15 funcionalidades impossíveis são **exclusivas do OpenAPI 3.0** e não têm representação no formato 2.0. Nenhum migrador automático pode gerá-las a partir de um arquivo 2.0, pois a informação simplesmente não existe na fonte.

### 7.4 `validador_openapi.py` — Validador de Sintaxe

```bash
python validador_openapi.py arquivo.yaml
python validador_openapi.py arquivo.yaml --json      # saída em JSON
python validador_openapi.py arquivo.yaml --resumo    # apenas resumo
python validador_openapi.py arquivo.yaml --sem-cor   # sem cores ANSI
```

**Retorna** exit code `0` se válido, `1` se houver erros (integrável em CI/CD).

**Verificações realizadas:**

| Verificação | 2.0 | 3.0 |
|---|---|---|
| Sintaxe YAML válida | ✅ | ✅ |
| Detecção automática de versão | ✅ | ✅ |
| Campos obrigatórios (`info`, `title`, `version`, `paths`) | ✅ | ✅ |
| Estrutura de servidores | ✅ | ✅ |
| Paths começam com `/` | ✅ | ✅ |
| Parâmetros (`name`, `in`, `required` para path) | ✅ | ✅ |
| Schema dentro de `schema{}` nos parâmetros | — | ✅ |
| `requestBody` com `content` não vazio | — | ✅ |
| Respostas com `description` obrigatória | ✅ | ✅ |
| Pelo menos um 2xx ou `default` por operação | ✅ | ✅ |
| `$ref` internos resolvíveis | ✅ | ✅ |
| `operationId` únicos | ✅ | ✅ |
| Tags declaradas vs usadas | ✅ | ✅ |
| Parâmetros de path declarados vs usados na URL | ✅ | ✅ |
| Tipos válidos (`integer`, `string`, `object`...) | ✅ | ✅ |
| Formatos conhecidos (`int32`, `date-time`, `uuid`...) | ✅ | ✅ |
| Security schemes com tipos válidos | ✅ | ✅ |
| Arrays com `items` definido | ✅ | ✅ |

---

### 7.5 Simulação de `examples` — o que o migrador consegue fazer

> **Contexto:** `components/examples` (named examples reutilizáveis) é exclusivo do OpenAPI 3.0.
> Para verificar o comportamento real do migrador, foi criado o arquivo
> [`examples/openapi_2.0_sim_examples.yaml`](examples/openapi_2.0_sim_examples.yaml)
> cobrindo 5 cenários distintos de uso de `example`/`examples` no 2.0.

#### Arquivo de simulação

```bash
python migrator_2to3.py examples/openapi_2.0_sim_examples.yaml
# → output_migrator/openapi_2.0_sim_examples_3.0.yaml
```

#### Resultados por cenário

| # | Cenário | Sintaxe 2.0 | Resultado 3.0 | Status |
|---|---------|-------------|---------------|--------|
| A | `example` inline em **propriedade** de schema | `properties.id.example: 1001` | Preservado identicamente | ✅ MIGRADO |
| B | `example` no **nível do schema** (object-level) | `Pedido.example: {id: 1001, ...}` | Preservado identicamente | ✅ MIGRADO |
| C | `example` inline em **parâmetro** | `param.example: 1001` (raiz do param) | Movido para `schema.example` | ✅ MIGRADO |
| D | `examples` na **resposta** (por mime type, 2.0) | `response.examples.application/json: {...}` | Convertido para `content.application/json.examples.default.value` | ✅ MIGRADO |
| E | `x-examples` em parâmetro body (extensão) | `param.x-examples: {PedidoCompleto: {value:...}}` | **Descartado silenciosamente** | ❌ PERDIDO |

#### Saída gerada — Cenário D (mais interessante)

O migrador já converte automaticamente o `examples` de resposta do 2.0 (chaveado por mime type)
para o formato 3.0 dentro de `content`:

```yaml
# 2.0 — examples no nível da resposta, chaveado por mime type
responses:
  200:
    examples:
      application/json:
        id: 1001
        status: pendente
        total: 204.90
```

```yaml
# 3.0 — examples dentro de content[mime].examples, com chave nomeada
responses:
  '200':
    content:
      application/json:
        examples:
          default:            # ← nome gerado pelo migrador
            value:
              id: 1001
              status: pendente
              total: 204.9
```

#### Cenário E — por que `x-examples` é perdido

`x-examples` é uma **extensão informal** (não padrão 2.0) usada por algumas ferramentas como
Stoplight para simular named examples em 2.0. O migrador extrai do parâmetro `in: body` apenas
os campos `schema`, `examples` (padrão 2.0) e `description`. Extensões `x-*` nos parâmetros
body são ignoradas durante a construção do `requestBody`.

#### Conclusão

| Tipo de example | Suportado no 2.0? | Migrado para 3.0? |
|-----------------|-------------------|-------------------|
| `example` inline em propriedades de schema | ✅ sim | ✅ sim |
| `example` no nível do schema | ✅ sim | ✅ sim |
| `example` em parâmetros query/path/header | ✅ sim | ✅ sim (dentro de `schema`) |
| `examples` em resposta (por mime type) | ✅ sim | ✅ sim (convertido para `content[mime].examples.default`) |
| `x-examples` (extensão informal) | ⚠️ extensão | ❌ não (descartado) |
| Named examples em `components/examples` | ❌ não existe no 2.0 | ❌ impossível |

> **Resumo:** Tudo que é `example` **padrão 2.0** é migrado corretamente.
> O único gap real é `components/examples` com named examples reutilizáveis — que é
> uma funcionalidade exclusiva do 3.0 sem equivalente no 2.0.

---

## 8. Guia de Referência Rápida

| Aspecto | OpenAPI 2.0 | OpenAPI 3.x |
|---|---|---|
| Campo raiz de versão | `swagger: "2.0"` | `openapi: "3.0.3"` |
| Endpoint base | `host` + `basePath` + `schemes` | `servers[].url` |
| Media type da requisição | `consumes: [application/json]` | `requestBody.content.<mime>` |
| Media type da resposta | `produces: [application/json]` | `responses.*.content.<mime>` |
| Body da requisição | `parameters: [{in: body}]` | `requestBody: {content: {...}}` |
| Upload de arquivo | `{in: formData, type: file}` | `requestBody multipart format:binary` |
| Schemas globais | `definitions.*` | `components/schemas/*` |
| Parâmetros globais | `parameters.*` | `components/parameters/*` |
| Respostas globais | `responses.*` | `components/responses/*` |
| Segurança global | `securityDefinitions.*` | `components/securitySchemes.*` |
| Auth Basic | `type: basic` | `type:http, scheme:basic` |
| Auth Bearer/JWT | `type:apiKey, in:header, name:Authorization` | `type:http, scheme:bearer` |
| OAuth2 flow code | `flow: accessCode` | `flows.authorizationCode` |
| OAuth2 múltiplos flows | Não suportado | `flows: {implicit:{}, authCode:{}}` |
| OpenID Connect | Não suportado | `type: openIdConnect` |
| Parâmetro cookie | Não suportado | `in: cookie` |
| Campo nullable | Não suportado | `nullable: true` |
| Campo writeOnly | Não suportado | `writeOnly: true` |
| Polimorfismo oneOf/anyOf | Não suportado | `oneOf: [...]` / `anyOf: [...]` |
| Links entre operações | Não suportado | `links: {operationId: ...}` |
| Callbacks/Webhooks | Não suportado | `callbacks:` / `webhooks:` |
| Exemplos nomeados | `examples: {mime: valor}` | `examples: {nome: {value:...}}` |
| `$ref` para schemas | `#/definitions/Nome` | `#/components/schemas/Nome` |

---

## 9. Case: Engenharia Reversa no erwin DM — Do 2.0 ao 3.0

### Contexto

API de Gestão de Pedidos existente documentada em Swagger 2.0 (`openapi_2.0_example.yaml`). O objetivo era importar o modelo no erwin Data Modeler para documentar e evoluir a arquitetura de dados. O erwin DM suporta apenas OpenAPI 3.0 como DBMS alvo.

---

### Etapa 1 — Tentativa direta: importar o 2.0 no erwin

O arquivo `openapi_2.0_example.yaml` foi importado diretamente no erwin DM via **Reverse Engineer → OpenAPI 3.0**.

![Engenharia reversa do 2.0 — erros EMU-1003](erwin_images/erwinDM_OpenAPI%20(8).png)

**Resultado observado:**

O erwin concluiu a importação com status *"Completed"*, mas gerou **dezenas de erros EMU-1003** na janela de log:

```
EMU-1003: Property type 'JSON_Col_Array_Options' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'
EMU-1003: Property type 'JSON_Col_Format' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'
EMU-1003: Property type 'JSON_Object_Ref_Property' cannot be set on object type
          'Attribute' for the target DBMS 'OpenAPI 3.0'
... (repetido para cada atributo com type/format/enum direto no parâmetro)
```

**Modelo gerado — estrutura problemática:**

| Nós raiz (colapsado) | Definitions expandido |
|:---:|:---:|
| ![2.0 colapsado](erwin_images/erwinDM_OpenAPI%20(7).png) | ![2.0 definitions](erwin_images/erwinDM_OpenAPI%20(6).png) |

```
openapi_2.0_example (+)
├── components          ← estrutura criada, mas TODOS os nós filhos vazios
│   ├── schemas         ← vazio
│   ├── parameters      ← vazio
│   ├── responses       ← vazio
│   └── ...             ← vazio
├── paths               ← único elemento correto: todas as rotas e verbos OK
└── definitions         ← nó extra criado na raiz (não existe no padrão 3.0)
    ├── Erro
    ├── Endereco
    ├── ItemPedido
    ├── PedidoPatch
    ├── PedidoCriacao
    └── Pedido
```

**Diagnóstico:**

| Problema | Causa |
|---|---|
| `components` vazio | erwin não promoveu `definitions` → `components/schemas` |
| `definitions` como nó raiz | Chave 2.0 reconhecida, mas não convertida |
| Schemas sem integração | `$ref: '#/definitions/X'` inválido no modelo 3.0 do erwin |
| EMU-1003 em massa | `type`/`format` direto nos parâmetros — estrutura 2.0 incompatível |
| `requestBody` ausente | `in: body` e `in: formData` não foram convertidos |
| Segurança ignorada | `securityDefinitions` não mapeado para `components/securitySchemes` |

**Conclusão da etapa:** importação parcialmente funcional apenas para os `paths`. O modelo estava inutilizável para documentação de dados.

---

### Etapa 2 — Conversão para 3.0 com o migrador

```bash
python migrator_2to3.py examples/openapi_2.0_example.yaml
# → output_migrator/openapi_2.0_example_3.0.yaml
```

**O que o migrador executou:**

| Transformação | Antes (2.0) | Depois (3.0) |
|---|---|---|
| Versão | `swagger: "2.0"` | `openapi: "3.0.3"` |
| Servidor | `host` + `basePath` + `schemes` | `servers: [{url: https://api.exemplo.com/v1}]` |
| Schemas | `definitions: {Pedido: ...}` | `components/schemas: {Pedido: ...}` |
| $ref schemas | `$ref: '#/definitions/Pedido'` | `$ref: '#/components/schemas/Pedido'` |
| Parâmetros globais | `parameters: {PedidoId: ...}` raiz | `components/parameters: {PedidoId: ...}` |
| Respostas globais | `responses: {NotFound: ...}` raiz | `components/responses: {NotFound: ...}` |
| Body da requisição | `{in: body, schema: $ref}` | `requestBody: {content: {application/json: {schema: $ref}}}` |
| Upload de arquivo | `{in: formData, type: file}` | `requestBody multipart/form-data format: binary` |
| Parâmetros query | `type: integer` (direto) | `schema: {type: integer}` (envolvido) |
| Segurança Bearer | `type: apiKey, in: header` | `type: http, scheme: bearer` |
| Segurança Basic | `type: basic` | `type: http, scheme: basic` |
| OAuth2 flow | `flow: accessCode` | `flows: {authorizationCode: {...}}` |
| Media types | `consumes`/`produces` globais | `content:` por operação |

---

### Etapa 3 — Validação do arquivo convertido

```bash
python validador_openapi.py output_migrator/openapi_2.0_example_3.0.yaml
```

**Saída esperada:**

```
============================================================
 VALIDADOR OPENAPI — openapi_2.0_example_3.0.yaml
============================================================
  ℹ️  Versão detectada: OpenAPI 3.0.3 (família 3.x)

  RESUMO:
    Erros   : 0
    Avisos  : 0
    Status  : ✅ VÁLIDO
```

---

### Etapa 4 — Reimportação do 3.0 no erwin DM

O arquivo `openapi_2.0_example_3.0.yaml` foi importado no erwin via **Reverse Engineer → OpenAPI 3.0**.

| Árvore 3.0 — schemas expandidos | Árvore 3.0 — components completo |
|:---:|:---:|
| ![3.0 schemas expandidos](erwin_images/erwinDM_OpenAPI%20(3).png) | ![3.0 components](erwin_images/erwinDM_OpenAPI%20(9).png) |

**Resultado observado:**

```
openapi_2.0_example_3.0 (+)
├── components
│   ├── schemas          ← POPULADO
│   │   ├── Pedido           (com todos os atributos: id, status, clienteId...)
│   │   ├── PedidoCriacao    (com atributos e validações)
│   │   ├── PedidoPatch
│   │   ├── ItemPedido
│   │   ├── Endereco
│   │   └── Erro
│   ├── parameters       ← com PedidoId, ClienteId, LimitQuery, OffsetQuery, XCorrelationId
│   ├── responses        ← com NotFound, Unauthorized, BadRequest, InternalError
│   ├── securitySchemes  ← com BearerAuth, BasicAuth, OAuth2
│   ├── requestBodies    ← mapeado
│   └── ...
└── paths                ← idêntico — todas as rotas e verbos preservados
    ├── /pedidos                      get / post
    ├── /pedidos/{pedidoId}           get / put / patch / delete
    ├── /pedidos/{pedidoId}/itens     get
    ├── /clientes/{clienteId}/pedidos get
    └── /produtos/upload              post
```

**Nenhum erro EMU-1003. Nenhum nó `definitions` extra. Modelo completo e navegável.**

---

### Comparativo Final: antes vs depois

| Elemento | 2.0 direto no erwin | 3.0 convertido no erwin |
|---|---|---|
| `components/schemas` | Vazio | ✅ Populado (6 entidades) |
| `components/parameters` | Vazio | ✅ Populado (5 parâmetros) |
| `components/responses` | Vazio | ✅ Populado (4 respostas) |
| `components/securitySchemes` | Vazio | ✅ Populado (3 esquemas) |
| `definitions` (nó extra) | Presente (incorreto) | ✅ Inexistente |
| `paths` | Preservado | ✅ Preservado (igual) |
| Erros EMU-1003 | Dezenas | ✅ Nenhum |
| `requestBody` nas operações | Ausente | ✅ Presente |
| Modelo utilizável | ❌ Não | ✅ Sim |

---

### Lição aprendida

O erwin DM interpreta qualquer arquivo OpenAPI através do seu modelo interno de **OpenAPI 3.0**. Estruturas do 2.0 não são convertidas automaticamente — são apenas mapeadas literalmente, resultando em:

- Chaves 2.0 (`definitions`, `securityDefinitions`) criadas como nós isolados sem integração
- `components` gerado como container vazio
- `paths` preservados (a estrutura interna de paths é compatível entre as versões)

A solução é invariavelmente converter para 3.0 antes de importar. O fluxo correto:

```
openapi_2.0_example.yaml
          │
          ▼ python migrator_2to3.py
          │
output_migrator/openapi_2.0_example_3.0.yaml
          │
          ▼ python validador_openapi.py  →  ✅ VÁLIDO
          │
          ▼ erwin DM — Reverse Engineer → OpenAPI 3.0
          │
Modelo completo: components populado, sem erros, sem nós extras
```

---

## 10. Conclusão

O OpenAPI 3.x representa uma evolução substancial em relação ao 2.0, com foco em maior expressividade, suporte a múltiplos ambientes, polimorfismo de schemas e organização centralizada de componentes. A migração de 2.0 para 3.x é recomendada para qualquer projeto que queira aproveitar ferramentas modernas de geração de código, documentação e engenharia reversa — incluindo o erwin DM.

Para o contexto de uso com erwin DM, a conclusão é clara: **o erwin não suporta nativamente a importação do formato 2.0**. A importação via o importador 3.0 resulta em erros previsíveis e importação parcial. A solução mais robusta é usar o script `migrador_2to3.py` para converter o arquivo antes da importação, seguido de validação com `validador_openapi.py`.

### Checklist de Migração 2.0 → 3.0

- [ ] Converter arquivo com `migrador_2to3.py`
- [ ] Validar saída com `validador_openapi.py`
- [ ] Verificar schemas em `components/schemas` (não em `definitions`)
- [ ] Confirmar `requestBody` em todas as operações com body
- [ ] Checar security schemes em `components/securitySchemes`
- [ ] Validar `$ref`: todos devem apontar para `#/components/...`
- [ ] Testar importação no erwin DM
- [ ] Verificar manualmente entidades geradas e relacionamentos `$ref`
