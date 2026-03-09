#!/usr/bin/env python3
"""
migrador_2to3.py
================
Migrador OpenAPI YAML 2.x (Swagger) → 3.x

Uso:
    python migrador_2to3.py entrada.yaml saida.yaml
    python migrador_2to3.py entrada.yaml            # salva em output_migrator/

Cobertura de migração:
  ✅ swagger → openapi
  ✅ host + basePath + schemes → servers
  ✅ consumes / produces → requestBody.content e responses.content
  ✅ securityDefinitions → components/securitySchemes
  ✅ definitions → components/schemas
  ✅ parameters (raiz) → components/parameters
  ✅ responses (raiz) → components/responses
  ✅ in:body → requestBody
  ✅ in:formData (arquivo) → requestBody multipart/form-data com format:binary
  ✅ in:formData (campo) → requestBody multipart/form-data com schema
  ✅ type:file → type:string / format:binary
  ✅ Parâmetros: type/format/enum diretos → dentro de schema{}
  ✅ $ref  definitions/ → components/schemas/
  ✅ $ref  parameters/ → components/parameters/
  ✅ $ref  responses/ → components/responses/
  ✅ OAuth2 flow:accessCode → flows.authorizationCode
  ✅ OAuth2 flow:implicit → flows.implicit
  ✅ OAuth2 flow:password → flows.password
  ✅ OAuth2 flow:application → flows.clientCredentials
  ✅ apiKey + basic → http / apiKey
  ✅ response schema + headers mantidos
  ✅ operationId, tags, summary, description, externalDocs mantidos
  ✅ servers com description (Produção / Desenvolvimento por scheme)
  ✅ sem YAML anchors (&id/*id) — cada content type recebe cópia independente do schema
"""

import sys
import copy
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────

def deep_copy(obj: Any) -> Any:
    return copy.deepcopy(obj)


def fix_ref(ref: str) -> str:
    """Atualiza caminhos $ref do 2.0 para 3.0."""
    if ref.startswith('#/definitions/'):
        return ref.replace('#/definitions/', '#/components/schemas/')
    if ref.startswith('#/parameters/'):
        return ref.replace('#/parameters/', '#/components/parameters/')
    if ref.startswith('#/responses/'):
        return ref.replace('#/responses/', '#/components/responses/')
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
# Conversão de Security
# ──────────────────────────────────────────────────────────────────────────────

OAUTH2_FLOW_MAP = {
    'implicit':    'implicit',
    'password':    'password',
    'application': 'clientCredentials',
    'accessCode':  'authorizationCode',
}


def convert_security_scheme(name: str, scheme: Dict) -> Dict:
    """Converte um securityDefinition 2.0 em securityScheme 3.0."""
    stype = scheme.get('type', '')
    result: Dict = {}

    if stype == 'basic':
        result = {'type': 'http', 'scheme': 'basic'}

    elif stype == 'apiKey':
        result = {
            'type': 'apiKey',
            'in':   scheme.get('in', 'header'),
            'name': scheme.get('name', name),
        }

    elif stype == 'oauth2':
        flow_2 = scheme.get('flow', 'implicit')
        flow_3 = OAUTH2_FLOW_MAP.get(flow_2, flow_2)
        flow_obj: Dict = {'scopes': scheme.get('scopes', {})}
        if 'authorizationUrl' in scheme:
            flow_obj['authorizationUrl'] = scheme['authorizationUrl']
        if 'tokenUrl' in scheme:
            flow_obj['tokenUrl'] = scheme['tokenUrl']
        result = {'type': 'oauth2', 'flows': {flow_3: flow_obj}}

    # Bearer / JWT (comum via apiKey Authorization header)
    if (stype == 'apiKey'
            and scheme.get('in') == 'header'
            and scheme.get('name', '').lower() in ('authorization', 'x-authorization')):
        result = {
            'type':          'http',
            'scheme':        'bearer',
            'bearerFormat':  'JWT',
        }

    if 'description' in scheme:
        result['description'] = scheme['description']

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Conversão de Parâmetros
# ──────────────────────────────────────────────────────────────────────────────

PARAM_SCHEMA_FIELDS = {
    'type', 'format', 'enum', 'default', 'minimum', 'maximum',
    'minLength', 'maxLength', 'pattern', 'items', 'minItems',
    'maxItems', 'uniqueItems', 'exclusiveMinimum', 'exclusiveMaximum',
    'multipleOf', 'example',
}

PARAM_TOP_FIELDS = {'name', 'in', 'description', 'required', 'allowEmptyValue'}


def convert_parameter(param: Dict) -> Dict:
    """Converte parâmetro 2.0 (exceto body/formData) para 3.0."""
    if '$ref' in param:
        return {'$ref': fix_ref(param['$ref'])}

    p_in = param.get('in', '')
    result: Dict = {}

    for field in PARAM_TOP_FIELDS:
        if field in param:
            result[field] = param[field]

    # Monta schema a partir dos campos de tipo
    schema: Dict = {}
    for field in PARAM_SCHEMA_FIELDS:
        if field in param:
            schema[field] = param[field]
    if '$ref' in param:
        schema['$ref'] = fix_ref(param['$ref'])
    if schema:
        result['schema'] = fix_refs_recursive(schema)

    if 'example' in param and 'schema' not in result:
        result['example'] = param['example']

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Construção de requestBody a partir de parâmetros body/formData
# ──────────────────────────────────────────────────────────────────────────────

def build_request_body(
    body_params: list,
    form_params: list,
    global_consumes: list,
) -> Optional[Dict]:
    """Constrói requestBody 3.0 a partir de params body/formData 2.0."""

    # ── body ──────────────────────────────────────────────────────────────
    if body_params:
        param = body_params[0]
        schema = param.get('schema', {})
        schema = fix_refs_recursive(schema)
        required = param.get('required', False)

        consumes = global_consumes or ['application/json']
        content: Dict = {}
        for mime in consumes:
            entry: Dict = {}
            if schema:
                entry['schema'] = deep_copy(schema)
            if 'examples' in param:
                entry['examples'] = deep_copy(param['examples'])
            content[mime] = entry

        rb: Dict = {'required': required, 'content': content}
        if 'description' in param:
            rb['description'] = param['description']
        return rb

    # ── formData ──────────────────────────────────────────────────────────
    if form_params:
        props: Dict = {}
        required_fields: list = []

        for p in form_params:
            fname = p.get('name', '')
            ptype = p.get('type', 'string')

            if ptype == 'file':
                field_schema: Dict = {'type': 'string', 'format': 'binary'}
            else:
                field_schema = {}
                for f in PARAM_SCHEMA_FIELDS - {'example'}:
                    if f in p:
                        field_schema[f] = p[f]
                if not field_schema:
                    field_schema = {'type': ptype}

            if 'description' in p:
                field_schema['description'] = p['description']
            props[fname] = field_schema

            if p.get('required', False):
                required_fields.append(fname)

        form_schema: Dict = {'type': 'object', 'properties': props}
        if required_fields:
            form_schema['required'] = required_fields

        return {
            'required': True,
            'content': {
                'multipart/form-data': {'schema': form_schema}
            }
        }

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Conversão de Respostas
# ──────────────────────────────────────────────────────────────────────────────

def convert_response(resp: Dict, global_produces: list) -> Dict:
    """Converte uma resposta 2.0 em resposta 3.0."""
    if '$ref' in resp:
        return {'$ref': fix_ref(resp['$ref'])}

    result: Dict = {}
    if 'description' in resp:
        result['description'] = resp['description']

    # headers
    if 'headers' in resp:
        result['headers'] = {}
        for hname, hval in resp['headers'].items():
            header_3: Dict = {}
            schema: Dict = {}
            for f in PARAM_SCHEMA_FIELDS:
                if f in hval:
                    schema[f] = hval[f]
            if schema:
                header_3['schema'] = schema
            if 'description' in hval:
                header_3['description'] = hval['description']
            result['headers'][hname] = header_3

    # schema → content
    schema = resp.get('schema')
    if schema:
        schema = fix_refs_recursive(schema)
        produces = global_produces or ['application/json']
        content: Dict = {}
        for mime in produces:
            entry: Dict = {'schema': deep_copy(schema)}
            if 'examples' in resp:
                ex_val = resp['examples'].get(mime)
                if ex_val is not None:
                    entry['examples'] = {'default': {'value': ex_val}}
            content[mime] = entry
        result['content'] = content

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Conversão de Operação
# ──────────────────────────────────────────────────────────────────────────────

OPERATION_TOP_FIELDS = {
    'tags', 'summary', 'description', 'operationId',
    'deprecated', 'security', 'externalDocs', 'callbacks',
}


def convert_operation(
    op: Dict,
    global_consumes: list,
    global_produces: list,
) -> Dict:
    """Converte um objeto de operação 2.0 para 3.0."""
    result: Dict = {}

    for field in OPERATION_TOP_FIELDS:
        if field in op:
            result[field] = deep_copy(op[field])

    op_consumes = op.get('consumes', global_consumes)
    op_produces = op.get('produces', global_produces)

    # Parâmetros
    normal_params: list = []
    body_params: list = []
    form_params: list = []

    for p in op.get('parameters', []):
        p_in = p.get('in', '')
        if p_in == 'body':
            body_params.append(p)
        elif p_in == 'formData':
            form_params.append(p)
        else:
            normal_params.append(convert_parameter(p))

    if normal_params:
        result['parameters'] = normal_params

    rb = build_request_body(body_params, form_params, op_consumes)
    if rb:
        result['requestBody'] = rb

    # Respostas
    if 'responses' in op:
        result['responses'] = {}
        for code, resp in op['responses'].items():
            result['responses'][str(code)] = convert_response(resp, op_produces)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Conversão Principal
# ──────────────────────────────────────────────────────────────────────────────

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'options', 'head', 'trace'}


def migrate_2_to_3(spec_2: Dict) -> Dict:
    """Converte um spec OpenAPI 2.x completo para 3.0.3."""

    out: Dict = {'openapi': '3.0.3'}

    # ── info ──────────────────────────────────────────────────────────────
    if 'info' in spec_2:
        out['info'] = deep_copy(spec_2['info'])

    # ── servers ───────────────────────────────────────────────────────────
    host     = spec_2.get('host', 'localhost')
    base     = spec_2.get('basePath', '/')
    schemes  = spec_2.get('schemes', ['https'])
    scheme_desc = {'https': 'Produção', 'http': 'Desenvolvimento'}
    servers  = []
    for scheme in schemes:
        url = f"{scheme}://{host}{base}"
        entry: Dict = {'url': url.rstrip('/')}
        if scheme in scheme_desc:
            entry['description'] = scheme_desc[scheme]
        servers.append(entry)
    out['servers'] = servers

    # ── tags ──────────────────────────────────────────────────────────────
    if 'tags' in spec_2:
        out['tags'] = deep_copy(spec_2['tags'])

    # ── security global ───────────────────────────────────────────────────
    if 'security' in spec_2:
        out['security'] = deep_copy(spec_2['security'])

    global_consumes = spec_2.get('consumes', ['application/json'])
    global_produces = spec_2.get('produces', ['application/json'])

    # ── paths ─────────────────────────────────────────────────────────────
    out['paths'] = {}
    for path, path_item in spec_2.get('paths', {}).items():
        new_path_item: Dict = {}

        # Parâmetros de nível de path
        path_params: list = []
        for p in path_item.get('parameters', []):
            p_in = p.get('in', '')
            if p_in not in ('body', 'formData'):
                path_params.append(convert_parameter(p))
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

    # ── components ────────────────────────────────────────────────────────
    components: Dict = {}

    # schemas (definitions)
    if 'definitions' in spec_2:
        components['schemas'] = fix_refs_recursive(deep_copy(spec_2['definitions']))

    # parameters globais
    if 'parameters' in spec_2:
        comp_params: Dict = {}
        for pname, param in spec_2['parameters'].items():
            p_in = param.get('in', '')
            if p_in not in ('body', 'formData'):
                comp_params[pname] = convert_parameter(param)
        if comp_params:
            components['parameters'] = comp_params

    # responses globais
    if 'responses' in spec_2:
        comp_responses: Dict = {}
        for rname, resp in spec_2['responses'].items():
            comp_responses[rname] = convert_response(resp, global_produces)
        components['responses'] = comp_responses

    # securitySchemes (securityDefinitions)
    if 'securityDefinitions' in spec_2:
        sec_schemes: Dict = {}
        for sname, scheme in spec_2['securityDefinitions'].items():
            sec_schemes[sname] = convert_security_scheme(sname, scheme)
        components['securitySchemes'] = sec_schemes

    if components:
        out['components'] = components

    # ── externalDocs ──────────────────────────────────────────────────────
    if 'externalDocs' in spec_2:
        out['externalDocs'] = deep_copy(spec_2['externalDocs'])

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
        saida = str(OUTPUT_DIR / f'{stem}_3.0.yaml')

    print(f"[INFO] Lendo: {entrada}", file=sys.stderr)
    with open(entrada, 'r', encoding='utf-8') as f:
        spec_2 = yaml.safe_load(f)

    versao = str(spec_2.get('swagger', spec_2.get('openapi', '')))
    if not versao.startswith('2'):
        print(f"[AVISO] Versão detectada: '{versao}'. "
              "Este migrador espera OpenAPI/Swagger 2.x.", file=sys.stderr)

    print("[INFO] Migrando 2.0 → 3.0...", file=sys.stderr)
    spec_3 = migrate_2_to_3(spec_2)

    yaml_out = yaml.dump(
        spec_3,
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
