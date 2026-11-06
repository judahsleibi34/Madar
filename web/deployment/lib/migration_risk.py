"""Conservative PostgreSQL17 AST analysis, never a compatibility certificate.

Only a small audited additive grammar can yield A. Unknown/dynamic/unparseable
SQL yields D. Declared metadata cannot lower this result. Native database,
old/new application, grants, locks, source and protected policy gates remain
independent requirements even for A.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

PARSER_VERSION = 'v7.21'
MAX_PARSE_BYTES = 2 * 1024 * 1024
MAX_NODES = 100000
IDENTIFIER = re.compile('[a-z][a-z0-9_]{0,62}')
RANK = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
BUILTINS = {'bool', 'int2', 'int4', 'int8', 'text', 'varchar', 'numeric', 'uuid',
            'timestamp', 'timestamptz', 'date', 'jsonb', 'bytea', 'float4', 'float8'}
CRITICAL = {'auth', 'storage', 'notification_deliveries', 'notification_outbox',
    'data_deletion_requests', 'data_deletion_steps', 'data_deletion_effects',
    'notification_delivery_protocol', 'notification_outbox_protocol', 'data_deletion_ownership_protocol',
    'builder_reservations', 'payments', 'subscriptions', 'orders', 'users', 'tenants',
    'application_schema_state'}


def guard_sql(origin):
    if type(origin) is not int or not 0 < origin < 10**9:
        raise RuntimeError('migration_guard_origin_invalid')
    return ("DO $madar_guard$\nDECLARE\n"
        " v_schema_version public.application_schema_state.schema_version%TYPE;\nBEGIN\n"
        " SELECT schema_version INTO v_schema_version FROM public.application_schema_state\n"
        " WHERE contract_key = 'core' FOR UPDATE;\n"
        f" IF v_schema_version <> {origin} OR v_schema_version IS NULL THEN\n"
        "  RAISE EXCEPTION 'migration_origin_mismatch';\n END IF;\nEND\n$madar_guard$;")


def transition_sql(target):
    if type(target) is not int or not 0 < target < 10**9:
        raise RuntimeError('migration_guard_target_invalid')
    return f"UPDATE public.application_schema_state SET schema_version = {target} WHERE contract_key = 'core';"


def scaffold(origin, target, body):
    if type(origin) is not int or type(target) is not int or target != origin + 1 or not isinstance(body, str):
        raise RuntimeError('migration_scaffold_transition_invalid')
    return ('BEGIN;\n' + guard_sql(origin) + '\n' + body + '\n' + transition_sql(target) + '\nCOMMIT;\n').encode()


def _strip_locations(value):
    if isinstance(value, dict):
        return {k: _strip_locations(v) for k, v in value.items() if k not in {'location', 'stmt_location', 'stmt_len', 'arg_location'}}
    if isinstance(value, list): return [_strip_locations(v) for v in value]
    return value


def _nodes(value, *, depth=0, budget=None):
    budget = [MAX_NODES] if budget is None else budget
    budget[0] -= 1
    if depth > 64 or budget[0] < 0: raise RuntimeError('migration_ast_limit')
    yield value
    if isinstance(value, dict):
        for child in value.values(): yield from _nodes(child, depth=depth+1, budget=budget)
    elif isinstance(value, list):
        for child in value: yield from _nodes(child, depth=depth+1, budget=budget)


def _strings(value):
    return {v for node in _nodes(value) if isinstance(node, dict)
            for k, v in node.items() if k in {'sval', 'relname', 'schemaname', 'rolename', 'defname'} and isinstance(v, str)}


def _isolated_create(value):
    if set(value) - {'relation', 'tableElts', 'oncommit'} or value.get('oncommit') != 'ONCOMMIT_NOOP': return False
    relation = value.get('relation', {})
    if (set(relation) - {'schemaname', 'relname', 'inh', 'relpersistence'}
            or relation.get('schemaname') != 'public' or relation.get('relpersistence') != 'p'
            or not IDENTIFIER.fullmatch(relation.get('relname', ''))): return False
    columns = value.get('tableElts', [])
    if not columns or len(columns) > 128: return False
    names = []
    for element in columns:
        if set(element) != {'ColumnDef'}: return False
        col = element['ColumnDef']
        if set(col) - {'colname', 'typeName', 'is_local', 'constraints'}: return False
        if not IDENTIFIER.fullmatch(col.get('colname', '')) or col.get('is_local') is not True: return False
        names.append(col['colname']); typ = col.get('typeName', {})
        if set(typ) != {'names', 'typemod'} or typ['typemod'] != -1: return False
        parts = typ['names']
        if (not isinstance(parts, list) or len(parts) != 2 or parts[0] != {'String': {'sval': 'pg_catalog'}}
                or parts[1] not in [{'String': {'sval': name}} for name in BUILTINS]): return False
        for constraint in col.get('constraints', []):
            if (set(constraint) != {'Constraint'} or set(constraint['Constraint']) != {'contype'}
                    or constraint['Constraint']['contype'] not in {'CONSTR_PRIMARY', 'CONSTR_UNIQUE', 'CONSTR_NOTNULL'}): return False
    return len(names) == len(set(names))


@dataclass(frozen=True)
class Risk:
    classification: str
    reasons: tuple[str, ...]
    transactional: bool
    schema_envelope_verified: bool
    parser: str

    def document(self):
        return {'class': self.classification, 'reasons': list(self.reasons),
                'transactional': self.transactional, 'schema_envelope_verified': self.schema_envelope_verified,
                'parser': self.parser, 'runtime_compatibility_proven': False, 'authority_issued': False}


def analyze(sql, *, origin, target):
    if type(sql) is not bytes or not 0 < len(sql) <= MAX_PARSE_BYTES:
        return Risk('D', ('sql_analysis_size_or_type_limit',), False, False, PARSER_VERSION)
    try:
        import pglast
        from pglast import parser
        if pglast.__version__ != PARSER_VERSION or parser.get_postgresql_version()[0] != 17:
            raise RuntimeError('parser_version')
        parsed = json.loads(parser.parse_sql_json(sql.decode('utf-8')))
        statements = [_strip_locations(row['stmt']) for row in parsed.get('stmts', [])]
        for _ in _nodes(statements): pass
    except ImportError:
        return Risk('D', ('postgresql_parser_unavailable',), False, False, PARSER_VERSION)
    except Exception:
        return Risk('D', ('sql_unparseable_or_parser_unsupported',), False, False, PARSER_VERSION)
    begin = {'TransactionStmt': {'kind': 'TRANS_STMT_BEGIN'}}
    commit = {'TransactionStmt': {'kind': 'TRANS_STMT_COMMIT'}}
    transactional = len(statements) >= 4 and statements[0] == begin and statements[-1] == commit
    try:
        guard = _strip_locations(json.loads(parser.parse_sql_json(guard_sql(origin)))['stmts'][0]['stmt'])
        transition = _strip_locations(json.loads(parser.parse_sql_json(transition_sql(target)))['stmts'][0]['stmt'])
        envelope = transactional and statements[1] == guard and statements[-2] == transition and target == origin + 1
    except Exception:
        envelope = False
    reasons = set(); classification = 'A'
    def escalate(level, reason):
        nonlocal classification
        if RANK[level] > RANK[classification]: classification = level
        reasons.add(reason)
    if not transactional: escalate('D', 'explicit_single_transaction_required')
    if not envelope: escalate('D', 'canonical_locked_schema_envelope_required')
    body = statements[2:-2] if envelope else statements
    if not body: escalate('D', 'migration_payload_missing')
    for statement in body:
        if len(statement) != 1:
            escalate('D', 'unknown_statement_shape'); continue
        kind, value = next(iter(statement.items()))
        tokens = _strings(statement)
        if tokens & CRITICAL: escalate('C', 'critical_runtime_or_authorization_contract')
        if kind == 'CreateStmt':
            if not _isolated_create(value): escalate('D', 'create_table_outside_audited_additive_subset')
        elif kind == 'IndexStmt':
            if value.get('concurrent'): escalate('D', 'nontransactional_concurrent_index_unsupported')
            else: escalate('B', 'index_build_requires_live_lock_and_size_review')
        elif kind == 'AlterTableStmt':
            subtypes = {cmd.get('AlterTableCmd', {}).get('subtype') for cmd in value.get('cmds', [])}
            if subtypes & {'AT_DropColumn', 'AT_DropConstraint', 'AT_AlterColumnType', 'AT_DropExpression'}:
                escalate('D', 'destructive_or_rewrite_alter_table')
            elif subtypes & {'AT_EnableRowSecurity', 'AT_DisableRowSecurity', 'AT_ForceRowSecurity', 'AT_NoForceRowSecurity'}:
                escalate('C', 'row_security_contract_change')
            elif subtypes and subtypes <= {'AT_AddColumn', 'AT_AddConstraint', 'AT_ColumnDefault',
                                         'AT_SetNotNull', 'AT_DropNotNull', 'AT_ValidateConstraint'}:
                escalate('B', 'alter_table_requires_live_lock_and_data_review')
            else: escalate('D', 'unrecognized_alter_table_operation')
        elif kind in {'GrantStmt', 'GrantRoleStmt', 'CreateFunctionStmt', 'CreatePolicyStmt', 'AlterPolicyStmt',
                      'AlterRoleStmt', 'CreateRoleStmt', 'CreateTrigStmt', 'AlterOwnerStmt'}:
            escalate('C', 'privileged_or_runtime_contract_change')
        elif kind in {'UpdateStmt', 'DeleteStmt'}:
            if not value.get('whereClause'): escalate('D', 'unbounded_data_mutation')
            else: escalate('B', 'data_mutation_requires_volume_and_invariant_review')
        elif kind in {'DropStmt', 'TruncateStmt'}: escalate('D', 'destructive_statement')
        elif kind in {'DoStmt', 'CallStmt'}: escalate('D', 'dynamic_or_procedural_sql_requires_review')
        else: escalate('D', 'unrecognized_statement_' + kind)
    if classification == 'A': reasons.add('isolated_new_table_only_not_runtime_compatibility_proof')
    return Risk(classification, tuple(sorted(reasons)), transactional, envelope, PARSER_VERSION)


def measured_operations(sql, *, origin, target):
    """Audited Class B shapes, never a lower classification or permission.

    Measurements/lock budgets apply only to nullable builtin columns without
    defaults and ordinary nonunique btree indexes on plain builtin columns.
    Expressions, predicates, opclasses, rewrites and best-effort DDL remain
    outside automatic support even when their overall classification is B.
    """
    risk=analyze(sql,origin=origin,target=target)
    if risk.classification!='B' or not risk.schema_envelope_verified:return []
    from pglast import parser
    rows=[_strip_locations(r['stmt']) for r in json.loads(parser.parse_sql_json(sql.decode()))['stmts']][2:-2]
    operations=[]
    def name(value):return isinstance(value,str) and IDENTIFIER.fullmatch(value) is not None
    for row in rows:
        kind,value=next(iter(row.items()));relation=value.get('relation',{})
        if (set(relation)-{'schemaname','relname','inh','relpersistence'}
                or relation.get('schemaname')!='public' or relation.get('relpersistence')!='p'
                or not name(relation.get('relname'))):return []
        base={'schema':'public','table':relation['relname']}
        if kind=='IndexStmt':
            if (set(value)-{'idxname','relation','accessMethod','indexParams'}
                    or not name(value.get('idxname')) or value.get('accessMethod')!='btree'):return []
            columns=[]
            for entry in value.get('indexParams',[]):
                item=entry.get('IndexElem',{})
                if (set(entry)!={'IndexElem'} or set(item)!={'name','ordering','nulls_ordering'}
                        or not name(item['name']) or item['ordering']!='SORTBY_DEFAULT'
                        or item['nulls_ordering']!='SORTBY_NULLS_DEFAULT'):return []
                columns.append(item['name'])
            if not 1<=len(columns)<=8 or len(set(columns))!=len(columns):return []
            operations.append({**base,'kind':'create_btree_index','index':value['idxname'],'columns':columns})
        elif kind=='AlterTableStmt':
            if set(value)!={'relation','cmds','objtype'} or value['objtype']!='OBJECT_TABLE':return []
            if len(value['cmds'])!=1:return []
            command=value['cmds'][0].get('AlterTableCmd',{})
            if (set(command)!={'subtype','def','behavior'} or command['subtype']!='AT_AddColumn'
                    or command['behavior']!='DROP_RESTRICT' or set(command['def'])!={'ColumnDef'}):return []
            column=command['def']['ColumnDef'];typ=column.get('typeName',{})
            if (set(column)!={'colname','typeName','is_local'} or column['is_local'] is not True
                    or not name(column['colname']) or set(typ)!={'names','typemod'} or typ['typemod']!=-1
                    or len(typ['names'])!=2 or typ['names'][0]!={'String':{'sval':'pg_catalog'}}
                    or typ['names'][1] not in [{'String':{'sval':t}} for t in BUILTINS]):return []
            operations.append({**base,'kind':'add_nullable_column','column':column['colname'],
                               'type':typ['names'][1]['String']['sval']})
        else:return []
    return operations
