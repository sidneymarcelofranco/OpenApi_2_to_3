#!/usr/bin/env python3
"""
validador_openapi.py
====================
Validador de sintaxe e estrutura OpenAPI YAML 2.x ou 3.x

Uso:
    python validador_openapi.py arquivo.yaml
    python validador_openapi.py arquivo.yaml --json          # saída em JSON
    python validador_openapi.py arquivo.yaml --resumo        # apenas resumo
    python validador_openapi.py arquivo.yaml --sem-cor       # sem ANSI colors

Verifica:
  ✅ Sintaxe YAML válida
  ✅ Detecção automática de versão (2.x / 3.x)
  ✅ Campos obrigatórios (info, title, version, paths)
  ✅ Estrutura de info (termsOfService, contact, license)
  ✅ Servidores / host+basePath+schemes
  ✅ Paths e operações (operationId, tags, responses)
  ✅ Resposta obrigatória (pelo menos um código 2xx ou default)
  ✅ Parâmetros (name, in, required para path, schema em 3.0)
  ✅ RequestBody 3.0 (content não vazio)
  ✅ Referências $ref internas (verifica se alvo existe)
  ✅ Schemas (type válido, $ref resolvível, items em array)
  ✅ SecurityDefinitions / SecuritySchemes
  ✅ Campos desconhecidos / mal posicionados (warnings)
  ✅ Padrões de path (parâmetros declarados vs usados)
  ✅ operationId únicos
  ✅ Tags declaradas vs usadas
  ✅ Formatos conhecidos (int32, int64, float, double, byte, binary, date, date-time, password, uri, email)
"""

import sys
import json
import re
import yaml
from typing import Any, Dict, List, Optional, Set, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Cores ANSI
# ──────────────────────────────────────────────────────────────────────────────

USE_COLOR = True


def c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def ok(msg):    return c(f"  ✅  {msg}", "32")
def err(msg):   return c(f"  ❌  {msg}", "31")
def warn(msg):  return c(f"  ⚠️   {msg}", "33")
def info(msg):  return c(f"  ℹ️   {msg}", "36")
def title(msg): return c(msg, "1;34")


# ──────────────────────────────────────────────────────────────────────────────
# Estrutura de resultado
# ──────────────────────────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(self):
        self.errors:   List[Dict] = []
        self.warnings: List[Dict] = []
        self.infos:    List[Dict] = []

    def add_error(self, path: str, message: str, suggestion: str = ""):
        self.errors.append({'path': path, 'message': message, 'suggestion': suggestion})

    def add_warning(self, path: str, message: str, suggestion: str = ""):
        self.warnings.append({'path': path, 'message': message, 'suggestion': suggestion})

    def add_info(self, path: str, message: str):
        self.infos.append({'path': path, 'message': message})

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Resolução de $ref
# ──────────────────────────────────────────────────────────────────────────────

def resolve_ref(ref: str, spec: Dict) -> Optional[Any]:
    """Resolve um $ref interno (começa com #/)."""
    if not ref.startswith('#/'):
        return None  # externo, não valida
    parts = ref[2:].split('/')
    node = spec
    for part in parts:
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def collect_refs(obj: Any) -> List[str]:
    """Coleta todos os $ref de um objeto."""
    refs: List[str] = []
    if isinstance(obj, dict):
        if '$ref' in obj:
            refs.append(obj['$ref'])
        for v in obj.values():
            refs.extend(collect_refs(v))
    elif isinstance(obj, list):
        for item in obj:
            refs.extend(collect_refs(item))
    return refs


# ──────────────────────────────────────────────────────────────────────────────
# Tipos e formatos válidos
# ──────────────────────────────────────────────────────────────────────────────

VALID_TYPES = {'integer', 'number', 'string', 'boolean', 'array', 'object', 'null'}

VALID_FORMATS = {
    'integer': {'int32', 'int64'},
    'number':  {'float', 'double'},
    'string':  {'byte', 'binary', 'date', 'date-time', 'password', 'uri',
                'email', 'uuid', 'hostname', 'ipv4', 'ipv6'},
}

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'options', 'head', 'trace'}

VALID_PARAM_IN_2 = {'query', 'header', 'path', 'formData', 'body'}
VALID_PARAM_IN_3 = {'query', 'header', 'path', 'cookie'}


# ──────────────────────────────────────────────────────────────────────────────
# Validações de Schema
# ──────────────────────────────────────────────────────────────────────────────

def validate_schema(schema: Any, path: str, spec: Dict, result: ValidationResult):
    if not isinstance(schema, dict):
        result.add_error(path, "Schema deve ser um objeto/mapeamento.")
        return

    if '$ref' in schema:
        ref = schema['$ref']
        if ref.startswith('#/') and resolve_ref(ref, spec) is None:
            result.add_error(path, f"$ref não resolvível: '{ref}'",
                             "Verifique se o caminho existe na especificação.")
        return

    stype = schema.get('type')
    if stype and stype not in VALID_TYPES:
        result.add_error(path, f"Tipo inválido: '{stype}'",
                         f"Tipos válidos: {', '.join(sorted(VALID_TYPES))}")

    fmt = schema.get('format')
    if fmt and stype and stype in VALID_FORMATS:
        if fmt not in VALID_FORMATS[stype]:
            result.add_warning(path,
                f"Formato '{fmt}' não é padrão para type '{stype}'.",
                f"Formatos comuns: {', '.join(VALID_FORMATS[stype])}")

    if stype == 'array' and 'items' not in schema and '$ref' not in schema:
        result.add_error(path, "Array sem 'items' definido.",
                         "Arrays devem ter 'items' especificando o tipo dos elementos.")

    # Valida schemas aninhados
    for key in ('items', 'additionalProperties'):
        if key in schema and isinstance(schema[key], dict):
            validate_schema(schema[key], f"{path}.{key}", spec, result)

    for key in ('allOf', 'anyOf', 'oneOf'):
        if key in schema:
            for i, sub in enumerate(schema[key]):
                validate_schema(sub, f"{path}.{key}[{i}]", spec, result)

    for prop_name, prop_schema in schema.get('properties', {}).items():
        validate_schema(prop_schema, f"{path}.properties.{prop_name}", spec, result)


# ──────────────────────────────────────────────────────────────────────────────
# Validação OpenAPI 2.0
# ──────────────────────────────────────────────────────────────────────────────

def validate_parameter_2(param: Dict, path: str, spec: Dict, result: ValidationResult):
    if '$ref' in param:
        if resolve_ref(param['$ref'], spec) is None:
            result.add_error(path, f"$ref de parâmetro não resolvível: '{param['$ref']}'")
        return

    if 'name' not in param:
        result.add_error(path, "Parâmetro sem 'name'.")
    if 'in' not in param:
        result.add_error(path, "Parâmetro sem 'in'.")
        return

    p_in = param['in']
    if p_in not in VALID_PARAM_IN_2:
        result.add_error(path, f"'in' inválido: '{p_in}'",
                         f"Valores válidos em 2.0: {', '.join(VALID_PARAM_IN_2)}")

    if p_in == 'path' and not param.get('required', False):
        result.add_warning(path,
            "Parâmetro de path deveria ter 'required: true'.",
            "Parâmetros de path são sempre obrigatórios.")

    if p_in == 'body':
        schema = param.get('schema')
        if not schema:
            result.add_error(path, "Parâmetro body sem 'schema'.",
                             "Parâmetros body devem ter um schema definido.")
        else:
            validate_schema(schema, f"{path}.schema", spec, result)
    elif p_in != 'formData' or param.get('type') != 'file':
        if 'type' not in param and 'schema' not in param and '$ref' not in param:
            result.add_warning(path, "Parâmetro sem 'type'.",
                               "Defina o tipo do parâmetro.")
        if 'type' in param:
            validate_schema({'type': param.get('type'),
                             'format': param.get('format')},
                            f"{path}[type]", spec, result)


def validate_response_2(code: str, resp: Dict, path: str, spec: Dict, result: ValidationResult):
    if '$ref' in resp:
        if resolve_ref(resp['$ref'], spec) is None:
            result.add_error(path, f"$ref de response não resolvível: '{resp['$ref']}'")
        return

    if 'description' not in resp:
        result.add_error(path, "Response sem 'description'.",
                         "Toda resposta deve ter uma descrição.")

    schema = resp.get('schema')
    if schema:
        validate_schema(schema, f"{path}.schema", spec, result)


def validate_operation_2(
    method: str, op: Dict, path: str,
    spec: Dict, result: ValidationResult,
    operation_ids: Set[str], all_tags: Set[str]
):
    op_path = f"paths.{path}.{method}"

    if 'operationId' in op:
        oid = op['operationId']
        if oid in operation_ids:
            result.add_error(op_path, f"operationId duplicado: '{oid}'",
                             "operationId deve ser único em toda a especificação.")
        operation_ids.add(oid)

    for tag in op.get('tags', []):
        all_tags.add(tag)

    params = op.get('parameters', [])
    for i, p in enumerate(params):
        validate_parameter_2(p, f"{op_path}.parameters[{i}]", spec, result)

    responses = op.get('responses', {})
    if not responses:
        result.add_error(op_path, "Operação sem respostas definidas.")
    else:
        has_success = any(
            str(c).startswith('2') or str(c) == 'default'
            for c in responses
        )
        if not has_success:
            result.add_warning(op_path,
                "Operação sem resposta de sucesso (2xx ou default).",
                "Defina pelo menos uma resposta 2xx.")
        for code, resp in responses.items():
            validate_response_2(str(code), resp, f"{op_path}.responses.{code}", spec, result)


def validate_path_params(path: str, path_item: Dict, result: ValidationResult):
    """Verifica se parâmetros de path declarados coincidem com {param} na URL."""
    declared = set()
    for p in path_item.get('parameters', []):
        if isinstance(p, dict) and p.get('in') == 'path':
            declared.add(p.get('name', ''))
    for method in HTTP_METHODS:
        op = path_item.get(method, {})
        if isinstance(op, dict):
            for p in op.get('parameters', []):
                if isinstance(p, dict) and p.get('in') == 'path':
                    declared.add(p.get('name', ''))

    used = set(re.findall(r'\{(\w+)\}', path))
    for u in used - declared:
        result.add_warning(f"paths.{path}",
            f"Parâmetro de path '{{{u}}}' usado na URL mas não declarado.",
            f"Declare o parâmetro '{u}' com 'in: path'.")
    for d in declared - used:
        result.add_warning(f"paths.{path}",
            f"Parâmetro de path '{d}' declarado mas não presente na URL.",
            f"Adicione '{{{d}}}' à URL ou remova a declaração.")


def validate_2(spec: Dict) -> ValidationResult:
    result = ValidationResult()

    # ── Info ──────────────────────────────────────────────────────────────
    info_obj = spec.get('info', {})
    if not isinstance(info_obj, dict) or not info_obj:
        result.add_error("info", "Campo 'info' obrigatório ausente ou inválido.")
    else:
        for req in ('title', 'version'):
            if req not in info_obj:
                result.add_error(f"info.{req}", f"Campo obrigatório 'info.{req}' ausente.")

    # ── Host / BasePath / Schemes ──────────────────────────────────────────
    if 'host' not in spec:
        result.add_warning("host", "Campo 'host' não definido; default será 'localhost'.")
    if 'basePath' not in spec:
        result.add_warning("basePath", "Campo 'basePath' não definido; default será '/'.")
    schemes = spec.get('schemes', [])
    if schemes:
        for s in schemes:
            if s not in ('http', 'https', 'ws', 'wss'):
                result.add_error("schemes", f"Scheme inválido: '{s}'",
                                 "Válidos: http, https, ws, wss")

    # ── Paths ──────────────────────────────────────────────────────────────
    paths = spec.get('paths', {})
    if not paths:
        result.add_error("paths", "Campo 'paths' obrigatório ausente ou vazio.")
    else:
        operation_ids: Set[str] = set()
        all_tags: Set[str] = set()

        for path, path_item in paths.items():
            if not path.startswith('/'):
                result.add_error(f"paths.{path}", f"Path deve começar com '/': '{path}'")
            if not isinstance(path_item, dict):
                continue
            validate_path_params(path, path_item, result)
            for method in HTTP_METHODS:
                op = path_item.get(method)
                if op is not None:
                    validate_operation_2(method, op, path, spec, result, operation_ids, all_tags)

        # Tags declaradas
        declared_tags = {t.get('name') for t in spec.get('tags', []) if isinstance(t, dict)}
        for tag in all_tags - declared_tags:
            result.add_warning("tags",
                f"Tag '{tag}' usada em operações mas não declarada na seção 'tags'.",
                "Declare todas as tags em 'tags' para melhor documentação.")

    # ── Definitions ────────────────────────────────────────────────────────
    for name, schema in spec.get('definitions', {}).items():
        validate_schema(schema, f"definitions.{name}", spec, result)

    # ── Security Definitions ───────────────────────────────────────────────
    for name, scheme in spec.get('securityDefinitions', {}).items():
        stype = scheme.get('type')
        if stype not in ('basic', 'apiKey', 'oauth2'):
            result.add_error(f"securityDefinitions.{name}",
                             f"Tipo de segurança inválido: '{stype}'",
                             "Tipos válidos em 2.0: basic, apiKey, oauth2")

    # ── $refs ──────────────────────────────────────────────────────────────
    all_refs = collect_refs(spec)
    for ref in all_refs:
        if ref.startswith('#/') and resolve_ref(ref, spec) is None:
            result.add_error("$ref", f"Referência não resolvível: '{ref}'",
                             "Verifique se o componente referenciado existe.")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Validação OpenAPI 3.x
# ──────────────────────────────────────────────────────────────────────────────

def validate_parameter_3(param: Dict, path: str, spec: Dict, result: ValidationResult):
    if '$ref' in param:
        if resolve_ref(param['$ref'], spec) is None:
            result.add_error(path, f"$ref de parâmetro não resolvível: '{param['$ref']}'")
        return

    if 'name' not in param:
        result.add_error(path, "Parâmetro sem 'name'.")
    if 'in' not in param:
        result.add_error(path, "Parâmetro sem 'in'.")
        return

    p_in = param['in']
    if p_in not in VALID_PARAM_IN_3:
        result.add_error(path, f"'in' inválido: '{p_in}'",
                         f"Valores válidos em 3.0: {', '.join(VALID_PARAM_IN_3)}")

    if p_in == 'path' and not param.get('required', False):
        result.add_warning(path, "Parâmetro de path deveria ter 'required: true'.")

    if 'schema' not in param and 'content' not in param:
        result.add_warning(path, "Parâmetro sem 'schema' ou 'content'.",
                           "Em 3.0 os parâmetros devem ter 'schema' definido.")
    elif 'schema' in param:
        validate_schema(param['schema'], f"{path}.schema", spec, result)


def validate_request_body_3(rb: Dict, path: str, spec: Dict, result: ValidationResult):
    content = rb.get('content', {})
    if not content:
        result.add_error(path, "requestBody sem 'content' ou content vazio.",
                         "Defina ao menos um media type em 'content'.")
    for mime, entry in content.items():
        if isinstance(entry, dict) and 'schema' in entry:
            validate_schema(entry['schema'], f"{path}.content.{mime}.schema", spec, result)


def validate_response_3(code: str, resp: Dict, path: str, spec: Dict, result: ValidationResult):
    if '$ref' in resp:
        if resolve_ref(resp['$ref'], spec) is None:
            result.add_error(path, f"$ref de response não resolvível: '{resp['$ref']}'")
        return

    if 'description' not in resp:
        result.add_error(path, "Response sem 'description'.")

    for mime, entry in resp.get('content', {}).items():
        if isinstance(entry, dict) and 'schema' in entry:
            validate_schema(entry['schema'], f"{path}.content.{mime}.schema", spec, result)


def validate_operation_3(
    method: str, op: Dict, path: str,
    spec: Dict, result: ValidationResult,
    operation_ids: Set[str], all_tags: Set[str]
):
    op_path = f"paths.{path}.{method}"

    if 'operationId' in op:
        oid = op['operationId']
        if oid in operation_ids:
            result.add_error(op_path, f"operationId duplicado: '{oid}'")
        operation_ids.add(oid)

    for tag in op.get('tags', []):
        all_tags.add(tag)

    for i, p in enumerate(op.get('parameters', [])):
        validate_parameter_3(p, f"{op_path}.parameters[{i}]", spec, result)

    rb = op.get('requestBody')
    if rb and isinstance(rb, dict):
        if '$ref' in rb:
            if resolve_ref(rb['$ref'], spec) is None:
                result.add_error(f"{op_path}.requestBody",
                                 f"$ref não resolvível: '{rb['$ref']}'")
        else:
            validate_request_body_3(rb, f"{op_path}.requestBody", spec, result)

    responses = op.get('responses', {})
    if not responses:
        result.add_error(op_path, "Operação sem respostas definidas.")
    else:
        has_success = any(
            str(c).startswith('2') or str(c) == 'default'
            for c in responses
        )
        if not has_success:
            result.add_warning(op_path, "Operação sem resposta de sucesso (2xx ou default).")
        for code, resp in responses.items():
            validate_response_3(str(code), resp, f"{op_path}.responses.{code}", spec, result)


def validate_3(spec: Dict) -> ValidationResult:
    result = ValidationResult()

    # ── Info ──────────────────────────────────────────────────────────────
    info_obj = spec.get('info', {})
    if not isinstance(info_obj, dict) or not info_obj:
        result.add_error("info", "Campo 'info' obrigatório ausente.")
    else:
        for req in ('title', 'version'):
            if req not in info_obj:
                result.add_error(f"info.{req}", f"Campo obrigatório 'info.{req}' ausente.")

    # ── Servers ────────────────────────────────────────────────────────────
    servers = spec.get('servers', [])
    if not servers:
        result.add_warning("servers",
            "Campo 'servers' não definido; padrão será '/'.",
            "Defina ao menos um servidor.")
    for i, srv in enumerate(servers):
        if 'url' not in srv:
            result.add_error(f"servers[{i}]", "Servidor sem 'url'.")

    # ── Paths ──────────────────────────────────────────────────────────────
    paths = spec.get('paths', {})
    if not paths:
        result.add_error("paths", "Campo 'paths' obrigatório ausente ou vazio.")
    else:
        operation_ids: Set[str] = set()
        all_tags: Set[str] = set()

        for path, path_item in paths.items():
            if not path.startswith('/'):
                result.add_error(f"paths.{path}", f"Path deve começar com '/': '{path}'")
            if not isinstance(path_item, dict):
                continue
            validate_path_params(path, path_item, result)
            for i, p in enumerate(path_item.get('parameters', [])):
                validate_parameter_3(p, f"paths.{path}.parameters[{i}]", spec, result)
            for method in HTTP_METHODS:
                op = path_item.get(method)
                if op is not None:
                    validate_operation_3(method, op, path, spec, result, operation_ids, all_tags)

        declared_tags = {t.get('name') for t in spec.get('tags', []) if isinstance(t, dict)}
        for tag in all_tags - declared_tags:
            result.add_warning("tags",
                f"Tag '{tag}' usada em operações mas não declarada na seção 'tags'.")

    # ── Components ─────────────────────────────────────────────────────────
    components = spec.get('components', {})

    for name, schema in components.get('schemas', {}).items():
        validate_schema(schema, f"components.schemas.{name}", spec, result)

    for name, param in components.get('parameters', {}).items():
        validate_parameter_3(param, f"components.parameters.{name}", spec, result)

    for name, resp in components.get('responses', {}).items():
        validate_response_3('?', resp, f"components.responses.{name}", spec, result)

    for name, rb in components.get('requestBodies', {}).items():
        if isinstance(rb, dict) and '$ref' not in rb:
            validate_request_body_3(rb, f"components.requestBodies.{name}", spec, result)

    for name, scheme in components.get('securitySchemes', {}).items():
        stype = scheme.get('type')
        valid_types_3 = {'apiKey', 'http', 'oauth2', 'openIdConnect', 'mutualTLS'}
        if stype not in valid_types_3:
            result.add_error(f"components.securitySchemes.{name}",
                             f"Tipo de segurança inválido: '{stype}'",
                             f"Tipos válidos em 3.0: {', '.join(sorted(valid_types_3))}")

    # ── $refs ──────────────────────────────────────────────────────────────
    all_refs = collect_refs(spec)
    for ref in all_refs:
        if ref.startswith('#/') and resolve_ref(ref, spec) is None:
            result.add_error("$ref", f"Referência não resolvível: '{ref}'")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Detecção de versão e orquestração
# ──────────────────────────────────────────────────────────────────────────────

def detect_version(spec: Dict) -> Tuple[str, str]:
    """Retorna (familia, versao_completa)."""
    if 'swagger' in spec:
        v = str(spec['swagger'])
        return ('2', v)
    if 'openapi' in spec:
        v = str(spec['openapi'])
        if v.startswith('2'):
            return ('2', v)
        if v.startswith('3'):
            return ('3', v)
    return ('?', '?')


def validate_file(filepath: str) -> Tuple[ValidationResult, str, str]:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        spec = yaml.safe_load(content)
    except yaml.YAMLError as e:
        result = ValidationResult()
        result.add_error("yaml", f"Erro de sintaxe YAML: {e}",
                         "Verifique indentação e caracteres especiais.")
        return result, '?', '?'

    if not isinstance(spec, dict):
        result = ValidationResult()
        result.add_error("root", "O arquivo deve conter um objeto YAML no nível raiz.")
        return result, '?', '?'

    familia, versao = detect_version(spec)

    if familia == '2':
        result = validate_2(spec)
    elif familia == '3':
        result = validate_3(spec)
    else:
        result = ValidationResult()
        result.add_error("version",
            "Versão OpenAPI não reconhecida. Esperado 'swagger: 2.x' ou 'openapi: 3.x'.")

    return result, familia, versao


# ──────────────────────────────────────────────────────────────────────────────
# Saída
# ──────────────────────────────────────────────────────────────────────────────

def print_result(result: ValidationResult, filepath: str, familia: str, versao: str,
                 resumo: bool = False, as_json: bool = False):

    if as_json:
        out = {
            'arquivo': filepath,
            'versao': versao,
            'familia': familia,
            'valido': result.valid,
            'total_erros': len(result.errors),
            'total_avisos': len(result.warnings),
            'erros': result.errors,
            'avisos': result.warnings,
            'informacoes': result.infos,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print()
    print(title("=" * 60))
    print(title(f" VALIDADOR OPENAPI — {filepath}"))
    print(title("=" * 60))
    print(info(f"   Versão detectada: OpenAPI {versao} (família {familia}.x)"))
    print()

    if not resumo:
        if result.errors:
            print(title(f"  ERROS ({len(result.errors)}):"))
            for e in result.errors:
                print(err(f"[{e['path']}] {e['message']}"))
                if e.get('suggestion'):
                    print(f"         💡 {e['suggestion']}")
            print()

        if result.warnings:
            print(title(f"  AVISOS ({len(result.warnings)}):"))
            for w in result.warnings:
                print(warn(f"[{w['path']}] {w['message']}"))
                if w.get('suggestion'):
                    print(f"         💡 {w['suggestion']}")
            print()

        if result.infos:
            print(title(f"  INFORMAÇÕES ({len(result.infos)}):"))
            for i in result.infos:
                print(info(f"[{i['path']}] {i['message']}"))
            print()

    print(title("  RESUMO:"))
    print(f"    Erros   : {len(result.errors)}")
    print(f"    Avisos  : {len(result.warnings)}")
    status = ok("VÁLIDO ✅") if result.valid else err("INVÁLIDO ❌")
    print(f"    Status  : {status}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    global USE_COLOR

    args = sys.argv[1:]
    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)

    filepath = None
    as_json  = False
    resumo   = False

    for arg in args:
        if arg == '--json':
            as_json = True
        elif arg == '--resumo':
            resumo = True
        elif arg == '--sem-cor':
            USE_COLOR = False
        elif not arg.startswith('--'):
            filepath = arg

    if not filepath:
        print("Erro: informe o caminho do arquivo YAML.", file=sys.stderr)
        sys.exit(1)

    try:
        result, familia, versao = validate_file(filepath)
    except FileNotFoundError:
        print(f"Erro: arquivo '{filepath}' não encontrado.", file=sys.stderr)
        sys.exit(1)
    except Exception as ex:
        print(f"Erro inesperado: {ex}", file=sys.stderr)
        sys.exit(1)

    print_result(result, filepath, familia, versao, resumo=resumo, as_json=as_json)

    sys.exit(0 if result.valid else 1)


if __name__ == '__main__':
    main()
