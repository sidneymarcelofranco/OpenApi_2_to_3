# OpenAPI 2 ↔ 3 Migrator

A set of Python scripts to migrate OpenAPI specifications between versions 2.0 (Swagger) and 3.0, plus a validator for both formats.

## Project Structure

```
OpenApi_2_to_3/
├── examples/
│   ├── openapi_2.0_example.yaml   # Sample Swagger 2.0 spec
│   └── openapi_3.0_example.yaml   # Sample OpenAPI 3.0 spec
├── output_migrator/               # Default output directory for migrated files
├── migrator_2to3.py               # Swagger 2.x → OpenAPI 3.0 migrator
├── migrator_3to2.py               # OpenAPI 3.x → Swagger 2.0 migrator
├── validador_openapi.py           # YAML spec validator (2.x and 3.x)
├── main.py
└── pyproject.toml
```

## Requirements

- Python 3.13+
- [PyYAML](https://pypi.org/project/PyYAML/)

```bash
pip install pyyaml
```

## Usage

### Migrate Swagger 2.x → OpenAPI 3.0

```bash
# Output saved automatically to output_migrator/<name>_3.0.yaml
python migrator_2to3.py examples/openapi_2.0_example.yaml

# Output to a custom path
python migrator_2to3.py examples/openapi_2.0_example.yaml my_api_v3.yaml
```

### Migrate OpenAPI 3.x → Swagger 2.0

```bash
# Output saved automatically to output_migrator/<name>_2.0.yaml
python migrator_3to2.py examples/openapi_3.0_example.yaml

# Output to a custom path
python migrator_3to2.py examples/openapi_3.0_example.yaml my_api_v2.yaml
```

### Validate an OpenAPI spec

```bash
# Full report with colors
python validador_openapi.py examples/openapi_3.0_example.yaml

# Summary only
python validador_openapi.py examples/openapi_3.0_example.yaml --resumo

# JSON output (for tooling/CI)
python validador_openapi.py examples/openapi_2.0_example.yaml --json

# Disable ANSI colors
python validador_openapi.py examples/openapi_3.0_example.yaml --sem-cor
```

The validator exits with code `0` if the spec is valid, `1` otherwise — suitable for use in CI pipelines.

## Migration Coverage

### 2.0 → 3.0 (`migrator_2to3.py`)

| Feature | Status |
|---|---|
| `swagger` → `openapi` | ✅ |
| `host` + `basePath` + `schemes` → `servers` | ✅ |
| `consumes` / `produces` → `requestBody.content` / `responses.content` | ✅ |
| `securityDefinitions` → `components/securitySchemes` | ✅ |
| `definitions` → `components/schemas` | ✅ |
| Root `parameters` → `components/parameters` | ✅ |
| Root `responses` → `components/responses` | ✅ |
| `in:body` → `requestBody` | ✅ |
| `in:formData` (file) → `requestBody` multipart with `format:binary` | ✅ |
| `in:formData` (field) → `requestBody` multipart with schema | ✅ |
| `type:file` → `type:string / format:binary` | ✅ |
| Parameter `type`/`format`/`enum` → inside `schema{}` | ✅ |
| `$ref` path rewrites (`definitions/` → `components/schemas/`, etc.) | ✅ |
| OAuth2 flow names (`accessCode` → `authorizationCode`, etc.) | ✅ |
| `apiKey` + `basic` → `http` / `apiKey` schemes | ✅ |
| Response schemas and headers preserved | ✅ |
| `operationId`, `tags`, `summary`, `description`, `externalDocs` preserved | ✅ |

### 3.0 → 2.0 (`migrator_3to2.py`)

| Feature | Status |
|---|---|
| `openapi` → `swagger` | ✅ |
| `servers` → `host` + `basePath` + `schemes` | ✅ |
| `components/schemas` → `definitions` | ✅ |
| `components/parameters` → root `parameters` | ✅ |
| `components/responses` → root `responses` | ✅ |
| `components/securitySchemes` → `securityDefinitions` | ✅ |
| `requestBody` (json/xml) → `in:body` | ✅ |
| `requestBody` multipart/form-data → `in:formData` | ✅ |
| `format:binary` → `type:file` | ✅ |
| `responses.content` → `schema` + `produces` | ✅ |
| Parameter `schema{}` → flat type fields | ✅ |
| `$ref` path rewrites (`components/schemas/` → `definitions/`, etc.) | ✅ |
| OAuth2 flow names (`authorizationCode` → `accessCode`, etc.) | ✅ |
| `http/bearer` → `apiKey` Authorization header | ✅ |
| `http/basic` → `type:basic` | ✅ |

**Known limitations (inherent to Swagger 2.0):**
- Multiple `servers`: only the first server URL is used; others are kept as `x-servers`
- `Links`, `Callbacks`, and `Webhooks` are discarded (not supported in 2.0)
- `oneOf` / `anyOf` partially mapped (`allOf` is preserved)
- Multiple content types per response: only the first supported type is used
- `cookie` parameters are converted to `header`

## Validation Coverage (`validador_openapi.py`)

- Valid YAML syntax
- Auto-detection of spec version (2.x / 3.x)
- Required fields (`info`, `title`, `version`, `paths`)
- `info` structure (`termsOfService`, `contact`, `license`)
- Servers / `host` + `basePath` + `schemes`
- Paths and operations (`operationId`, `tags`, `responses`)
- At least one success response (2xx or `default`) per operation
- Parameters (`name`, `in`, `required` for path params, `schema` in 3.0)
- `requestBody` in 3.0 (non-empty `content`)
- Internal `$ref` resolution
- Schemas (valid `type`, resolvable `$ref`, `items` on arrays)
- `securityDefinitions` / `securitySchemes`
- Unknown or misplaced fields (warnings)
- Path parameter consistency (declared vs. used in URL template)
- Unique `operationId` values
- Declared vs. used tags
- Known formats (`int32`, `int64`, `float`, `double`, `byte`, `binary`, `date`, `date-time`, `password`, `uri`, `email`)
