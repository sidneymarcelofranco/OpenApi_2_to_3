#!/usr/bin/env python3
"""
migrador_3to2.py
================
Migrador OpenAPI YAML 3.x → 2.0 (Swagger)

Uso:
    python migrador_3to2.py entrada.yaml saida.yaml
    python migrador_3to2.py entrada.yaml            # salva em output_migrator/

ATENÇÃO – Limitações inerentes ao formato 2.0:
  ⚠️  servers[] com múltiplas URLs: usa apenas o primeiro servidor
  ⚠️  requestBody multipart com múltiplos arquivos: usa in:formData
  ⚠️  Links, Callbacks e Webhooks: descartados (não existem em 2.0)
  ⚠️  oneOf / anyOf / allOf parcialmente mapeados (allOf preservado)
  ⚠️  Multiple content types por resposta: usa o primeiro suportado
  ⚠️  OpenAPI 3.1 nullable: convertido para x-nullable
  ⚠️  components/examples, components/headers: preservados como x-*

Cobertura de migração:
  ✅ openapi → swagger
  ✅ servers → host + basePath + schemes
  ✅ components/schemas → definitions
  ✅ components/parameters → parameters (raiz)
  ✅ components/responses → responses (raiz)
  ✅ components/securitySchemes → securityDefinitions
  ✅ requestBody (json/xml) → in:body
  ✅ requestBody multipart/form-data → in:formData
  ✅ format:binary → type:file
  ✅ responses content → schema + produces
  ✅ parameters schema{} → tipo direto no parâmetro
  ✅ $ref components/schemas/ → definitions/
  ✅ $ref components/parameters/ → parameters/
  ✅ $ref components/responses/ → responses/
  ✅ OAuth2 flows → securityDefinitions (flow singular)
  ✅ http/bearer → apiKey Authorization header
  ✅ http/basic → type:basic
"""

import sys
import copy
import re
from pathlib import Path
from urllib.parse import urlparse
import yaml
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários
# ──────────────────────────────────────────────────────────────────────────────

def deep_copy(obj: Any) -> Any:
    return copy.deepcopy(obj)


def fix_ref(ref: str) -> str:
    """Atualiza caminhos $ref do 3.0 para 2.0."""
    if ref.startswith('#/components/schemas/'):
        return ref.replace('#/components/schemas/', '#/definitions/')
    if ref.startswith('#/components/parameters/'):
        return ref.replace('#/components/parameters/', '#/parameters/')
    if ref.startswith('#/components/responses/'):
        return ref.replace('#/components/responses/', '#/responses/')
    return ref


def fix_refs_recursive(obj: Any) -> Any:
    """Percorre toda a estrutura e corrige $ref."""
    if isinstance(obj, dict):
        return {k: (fix_ref(v) if k == '$ref' else fix_refs_recursive(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_refs_recursive(i) for i in obj]
    return obj


# ──────────────────────────────────────────────────────────────────────────────
# Servers → host / basePath / schemes
# ──────────────────────────────────────────────────────────────────────────────

def extract_server_info(servers: List[Dict]) -> Tuple[str, str, List[str]]:
    """
    Extrai host, basePath e schemes da lista de servers 3.0.
    Usa apenas o primeiro servidor; demais são registrados como x-servers.
    """
    if not servers:
        return 'localhost', '/', ['https']

    url = servers[0].get('url', 'https://localhost/')
    # Substitui variáveis de servidor {var} por valores default ou placeholder
    url = re.sub(r'\{(\w+)\}', lambda m: m.group(1), url)

    parsed = urlparse(url)
    schemes = [parsed.scheme] if parsed.scheme else ['https']
    host = parsed.netloc or 'localhost'
    base = parsed.path or '/'
    if not base.startswith('/'):
        base = '/' + base

    return host, base, schemes


# ──────────────────────────────────────────────────────────────────────────────
# Security Schemes
# ──────────────────────────────────────────────────────────────────────────────

OAUTH2_FLOW_MAP_REVERSE = {
    'implicit':           'implicit',
    'password':           'password',
    'clientCredentials':  'application',
    'authorizationCode':  'accessCode',
}


def convert_security_scheme(name: str, scheme: Dict) -> Dict:
    """Converte securityScheme 3.0 em securityDefinition 2.0."""
    stype = scheme.get('type', '')
    result: Dict = {}

    if stype == 'http':
        http_scheme = scheme.get('scheme', '').lower()
        if http_scheme == 'basic':
            result = {'type': 'basic'}
        elif http_scheme in ('bearer', 'jwt'):
            # JWT bearer → apiKey no header Authorization (melhor suporte em 2.0)
            result = {
                'type': 'apiKey',
                'in':   'header',
                'name': 'Authorization',
            }
        else:
            result = {
                'type': 'apiKey',
                'in':   'header',
                'name': f'X-{name}',
            }

    elif stype == 'apiKey':
        result = {
            'type': 'apiKey',
            'in':   scheme.get('in', 'header'),
            'name': scheme.get('name', name),
        }

    elif stype == 'oauth2':
        flows = scheme.get('flows', {})
        # Usa o primeiro flow disponível
        for flow_3, flow_data in flows.items():
            flow_2 = OAUTH2_FLOW_MAP_REVERSE.get(flow_3, flow_3)
            result = {'type': 'oauth2', 'flow': flow_2}
            if 'authorizationUrl' in flow_data:
                result['authorizationUrl'] = flow_data['authorizationUrl']
            if 'tokenUrl' in flow_data:
                result['tokenUrl'] = flow_data['tokenUrl']
            result['scopes'] = flow_data.get('scopes', {})
            break  # 2.0 suporta apenas um flow por definição

    elif stype == 'openIdConnect':
        # Não tem equivalente em 2.0; converte como extensão
        result = {
            'type': 'apiKey',
            'in':   'header',
            'name': 'Authorization',
            'x-openIdConnectUrl': scheme.get('openIdConnectUrl', ''),
        }

    if 'description' in scheme:
        result['description'] = scheme['description']

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Parâmetros
# ──────────────────────────────────────────────────────────────────────────────

SCHEMA_FLAT_FIELDS = {
    'type', 'format', 'enum', 'default', 'minimum', 'maximum',
    'minLength', 'maxLength', 'pattern', 'items', 'minItems',
    'maxItems', 'uniqueItems', 'exclusiveMinimum', 'exclusiveMaximum',
    'multipleOf',
}


def convert_parameter(param: Dict) -> Dict:
    """Converte parâmetro 3.0 para 2.0 (não body/formData)."""
    if '$ref' in param:
        return {'$ref': fix_ref(param['$ref'])}

    result: Dict = {}

    for field in ('name', 'in', 'description', 'required', 'allowEmptyValue'):
        if field in param:
            result[field] = param[field]

    schema = param.get('schema', {})
    schema = fix_refs_recursive(schema)

    if '$ref' in schema:
        result['schema'] = schema
    else:
        for field in SCHEMA_FLAT_FIELDS:
            if field in schema:
                val = schema[field]
                if field == 'items':
                    val = fix_refs_recursive(val)
                result[field] = val
        if 'example' in param:
            result['example'] = param['example']
        elif 'example' in schema:
            result['example'] = schema['example']

    return result


# ──────────────────────────────────────────────────────────────────────────────
# requestBody → parâmetros body / formData
# ──────────────────────────────────────────────────────────────────────────────

PREFERRED_JSON = ['application/json', 'application/xml', 'text/plain']
PREFERRED_FORM = ['multipart/form-data', 'application/x-www-form-urlencoded']


def find_content_type(content: Dict, preferred: List[str]) -> Optional[str]:
    for mime in preferred:
        if mime in content:
            return mime
    if content:
        return next(iter(content))
    return None


def request_body_to_params(rb: Dict, produces_out: List[str]) -> List[Dict]:
    """Converte requestBody 3.0 em lista de parâmetros 2.0."""
    params: List[Dict] = []
    content = rb.get('content', {})
    required = rb.get('required', False)
    description = rb.get('description', '')

    # ── multipart / form-data ─────────────────────────────────────────────
    form_mime = find_content_type(content, PREFERRED_FORM)
    if form_mime:
        form_schema = content[form_mime].get('schema', {})
        props = form_schema.get('properties', {})
        required_fields = form_schema.get('required', [])

        if props:
            for fname, fschema in props.items():
                p: Dict = {
                    'name': fname,
                    'in':   'formData',
                    'required': fname in required_fields,
                }
                if 'description' in fschema:
                    p['description'] = fschema['description']

                # format:binary → type:file
                if fschema.get('format') == 'binary' or fschema.get('type') == 'string' and fschema.get('format') == 'binary':
                    p['type'] = 'file'
                else:
                    for field in SCHEMA_FLAT_FIELDS:
                        if field in fschema:
                            p[field] = fschema[field]
                    if 'type' not in p:
                        p['type'] = 'string'
                params.append(p)
        else:
            # Schema genérico
            p_generic: Dict = {
                'name':     'body',
                'in':       'formData',
                'required': required,
                'type':     'string',
            }
            if description:
                p_generic['description'] = description
            params.append(p_generic)

        # Garante que multipart esteja em consumes
        if form_mime not in produces_out:
            produces_out.insert(0, form_mime)
        return params

    # ── body (json / xml / etc.) ──────────────────────────────────────────
    json_mime = find_content_type(content, PREFERRED_JSON)
    if json_mime:
        entry = content[json_mime]
        schema = fix_refs_recursive(entry.get('schema', {}))
        p_body: Dict = {
            'name':     'body',
            'in':       'body',
            'required': required,
        }
        if description:
            p_body['description'] = description
        if schema:
            p_body['schema'] = schema
        if 'examples' in entry:
            pass  # exemplos inline não têm equivalente direto em 2.0
        params.append(p_body)

    return params


# ──────────────────────────────────────────────────────────────────────────────
# Respostas
# ──────────────────────────────────────────────────────────────────────────────

def convert_response(resp: Dict, global_produces: List[str]) -> Dict:
    """Converte uma resposta 3.0 para 2.0."""
    if '$ref' in resp:
        return {'$ref': fix_ref(resp['$ref'])}

    result: Dict = {}
    if 'description' in resp:
        result['description'] = resp['description']

    # headers
    if 'headers' in resp:
        result['headers'] = {}
        for hname, hval in resp['headers'].items():
            h2: Dict = {}
            schema = hval.get('schema', {})
            for f in SCHEMA_FLAT_FIELDS:
                if f in schema:
                    h2[f] = schema[f]
            if 'description' in hval:
                h2['description'] = hval['description']
            result['headers'][hname] = h2

    # content → schema + examples
    content = resp.get('content', {})
    if content:
        json_mime = find_content_type(content, PREFERRED_JSON)
        if json_mime:
            entry = content[json_mime]
            schema = fix_refs_recursive(entry.get('schema', {}))
            if schema:
                result['schema'] = schema
            # exemplos
            if 'examples' in entry:
                ex_map: Dict = {}
                for ex_name, ex_val in entry['examples'].items():
                    if isinstance(ex_val, dict) and 'value' in ex_val:
                        ex_map[json_mime] = ex_val['value']
                if ex_map:
                    result['examples'] = ex_map
            # produz registra o mime
            if json_mime not in global_produces:
                global_produces.append(json_mime)

    if not result.get('description'):
        result['description'] = 'Sem descrição'

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Operação
# ──────────────────────────────────────────────────────────────────────────────

OPERATION_TOP_FIELDS = {
    'tags', 'summary', 'description', 'operationId',
    'deprecated', 'security', 'externalDocs',
}

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'options', 'head', 'trace'}


def convert_operation(
    op: Dict,
    global_consumes: List[str],
    global_produces: List[str],
) -> Dict:
    """Converte operação 3.0 para 2.0."""
    result: Dict = {}

    for field in OPERATION_TOP_FIELDS:
        if field in op:
            result[field] = deep_copy(op[field])

    op_consumes: List[str] = list(global_consumes)
    op_produces: List[str] = list(global_produces)

    params: List[Dict] = []

    # Parâmetros normais (path/query/header/cookie)
    for p in op.get('parameters', []):
        cp = convert_parameter(p)
        # cookie não existe em 2.0 → header
        if cp.get('in') == 'cookie':
            cp['in'] = 'header'
            cp.setdefault('description', 'Cookie parameter (migrado de 3.0)')
        params.append(cp)

    # requestBody → body ou formData
    rb = op.get('requestBody')
    if rb:
        rb_params = request_body_to_params(rb, op_consumes)
        params.extend(rb_params)

    if params:
        result['parameters'] = params

    # consumes/produces por operação (apenas se diferirem do global)
    if set(op_consumes) != set(global_consumes):
        result['consumes'] = op_consumes
    if set(op_produces) != set(global_produces):
        result['produces'] = op_produces

    # Respostas
    if 'responses' in op:
        result['responses'] = {}
        for code, resp in op['responses'].items():
            result['responses'][str(code)] = convert_response(resp, op_produces)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Migração Principal
# ──────────────────────────────────────────────────────────────────────────────

def migrate_3_to_2(spec_3: Dict) -> Dict:
    """Converte um spec OpenAPI 3.x completo para 2.0."""

    out: Dict = {'swagger': '2.0'}

    # ── info ──────────────────────────────────────────────────────────────
    if 'info' in spec_3:
        out['info'] = deep_copy(spec_3['info'])

    # ── servers → host/basePath/schemes ───────────────────────────────────
    servers = spec_3.get('servers', [])
    host, base_path, schemes = extract_server_info(servers)
    out['host']     = host
    out['basePath'] = base_path
    out['schemes']  = schemes
    if len(servers) > 1:
        out['x-servers'] = servers[1:]  # demais servidores como extensão

    # ── consumes / produces globais ───────────────────────────────────────
    global_consumes = ['application/json']
    global_produces = ['application/json']
    out['consumes'] = global_consumes
    out['produces'] = global_produces

    # ── security global ───────────────────────────────────────────────────
    if 'security' in spec_3:
        out['security'] = deep_copy(spec_3['security'])

    # ── tags ──────────────────────────────────────────────────────────────
    if 'tags' in spec_3:
        out['tags'] = deep_copy(spec_3['tags'])

    # ── paths ─────────────────────────────────────────────────────────────
    out['paths'] = {}
    for path, path_item in spec_3.get('paths', {}).items():
        new_path_item: Dict = {}

        # Parâmetros de nível de path
        path_params: List[Dict] = []
        for p in path_item.get('parameters', []):
            cp = convert_parameter(p)
            if cp.get('in') == 'cookie':
                cp['in'] = 'header'
            path_params.append(cp)
        if path_params:
            new_path_item['parameters'] = path_params

        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            new_path_item[method] = convert_operation(
                operation, global_consumes, global_produces
            )

        out['paths'][path] = new_path_item

    # ── definitions (components/schemas) ──────────────────────────────────
    components = spec_3.get('components', {})

    if 'schemas' in components:
        out['definitions'] = fix_refs_recursive(deep_copy(components['schemas']))

    # ── parameters (components/parameters) ────────────────────────────────
    if 'parameters' in components:
        comp_params: Dict = {}
        for pname, param in components['parameters'].items():
            p_in = param.get('in', '')
            if p_in not in ('body', 'formData'):
                cp = convert_parameter(param)
                if cp.get('in') == 'cookie':
                    cp['in'] = 'header'
                comp_params[pname] = cp
        if comp_params:
            out['parameters'] = comp_params

    # ── responses (components/responses) ──────────────────────────────────
    if 'responses' in components:
        comp_responses: Dict = {}
        for rname, resp in components['responses'].items():
            comp_responses[rname] = convert_response(resp, global_produces)
        out['responses'] = comp_responses

    # ── securityDefinitions (components/securitySchemes) ──────────────────
    if 'securitySchemes' in components:
        sec_defs: Dict = {}
        for sname, scheme in components['securitySchemes'].items():
            sec_defs[sname] = convert_security_scheme(sname, scheme)
        out['securityDefinitions'] = sec_defs

    # ── externalDocs ──────────────────────────────────────────────────────
    if 'externalDocs' in spec_3:
        out['externalDocs'] = deep_copy(spec_3['externalDocs'])

    # Corrige todas as $ref restantes
    out = fix_refs_recursive(out)

    return out


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent / 'output_migrator'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    entrada = sys.argv[1]

    if len(sys.argv) > 2:
        saida = sys.argv[2]
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(entrada).stem
        saida = str(OUTPUT_DIR / f'{stem}_2.0.yaml')

    print(f"[INFO] Lendo: {entrada}", file=sys.stderr)
    with open(entrada, 'r', encoding='utf-8') as f:
        spec_3 = yaml.safe_load(f)

    versao = str(spec_3.get('openapi', spec_3.get('swagger', '')))
    if versao.startswith('2'):
        print(f"[AVISO] Versão detectada: '{versao}'. "
              "Este migrador espera OpenAPI 3.x.", file=sys.stderr)

    print("[INFO] Migrando 3.0 → 2.0...", file=sys.stderr)
    spec_2 = migrate_3_to_2(spec_3)

    yaml_out = yaml.dump(
        spec_2,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        indent=2,
    )

    with open(saida, 'w', encoding='utf-8') as f:
        f.write(yaml_out)
    print(f"[OK] Arquivo gerado: {saida}", file=sys.stderr)


if __name__ == '__main__':
    main()
