#!/usr/bin/env python3
"""Validate the explicitly selected property preparation target; never execute a SUT."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'cts/sansa/v1/sansa-property-selectors-cts.v1.next.json'
PROFILE = 'sansa-properties-read-only-candidate-0.1'
PROTOCOL = 'sansa-properties-preparation-v0.1'

class PreparationError(ValueError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreparationError(message)

def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(PreparationError('Non-JSON constant: '+value)))

def child(root: Path, relative: str) -> Path:
    require(isinstance(relative,str), 'Expected relative artefact path')
    path=(root/relative).resolve()
    require(path.is_relative_to(root.resolve()), 'Artefact path escapes its root')
    return path

def verified(root: Path, entry: dict, path_key='file', digest_key='content_sha256') -> Path:
    path=child(root,entry[path_key])
    require(path.is_file(), 'Missing artefact: '+entry[path_key])
    require(hashlib.sha256(path.read_bytes()).hexdigest()==entry[digest_key], 'Digest mismatch: '+entry[path_key])
    return path

def expand(generated: dict):
    """Construct bounded fixture input; this is not a selector parser/evaluator."""
    count=generated['count'];kind=generated['kind'];form=generated['form']
    require(type(count) is int and 0<=count<=65537, 'Generated fixture exceeds preparation allowance')
    selector={'type':'propertyFilter','property':'key','value':'x'}
    selectors=[]
    if kind=='payload':
        selector['value']=generated.get('scalar','x')*count;selectors=[selector]
        payload=json.dumps(selector['value'],ensure_ascii=False)
        if generated.get('encoding')=='escaped':payload='\"'+('\\u{'+format(ord(generated.get('scalar','x')),'X')+'}')*count+'\"'
        source='$&key('+payload+')'
    elif kind=='selectors':
        selectors=[dict(selector) for _ in range(count)]
        source='$'+'&key("x")'*count
    else:
        require(kind=='canonical' and count>=16, 'Invalid canonical fixture length')
        name='@'+'x'*(count-16)
        selectors=[{'type':'member','name':name,'quoted':True},selector]
        source='$.["'+name+'"]&key("x")'
        require(len(source)==count, 'Canonical fixture construction mismatch')
    if form=='text':return source
    return {'type':'SansaAddress','root':{'type':'root','kind':'absolute'},'selectors':selectors,'qualifierExpression':None,'canonical':'untrusted','isExact':True}

def check(manifest_path: Path, specs_root: Path) -> dict:
    manifest_path=manifest_path.resolve();lane=manifest_path.parent;manifest=load(manifest_path);meta=manifest['meta']
    require(meta.get('lane')=='sansa-properties' and meta.get('profile')==PROFILE, 'Wrong candidate lane/profile')
    require(meta.get('preparation_only') is True and meta.get('sut_protocol')==PROTOCOL, 'Not a preparation-only protocol')
    require(meta.get('conformance')=={'surface':'experimental','experimental_default':'exclude'}, 'Candidate must be explicitly excluded by default')
    revision=meta.get('specification_revision','')
    require(re.fullmatch('[0-9a-f]{40}',revision) is not None and revision!='0'*40, 'Pin a real owning specification revision before retention')
    spec=manifest['specification']
    verified(specs_root,{'file':spec['source'],'content_sha256':spec['source_sha256']})
    resource_path=verified(specs_root,{'file':spec['resource'],'content_sha256':spec['resource_sha256']})
    schema_path=verified(specs_root,{'file':spec['schema'],'content_sha256':spec['schema_sha256']})
    schema=load(schema_path);Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(load(resource_path))
    contract=load(resource_path)
    require(contract['status']=='proposal-unpublished-unimplemented' and contract['defaultSelection']=='exclude', 'Contract must remain unpublished/unimplemented')
    assets={entry['file']:verified(lane,entry) for entry in manifest['assets']}
    require(len(assets)==len(manifest['assets']), 'Duplicate candidate asset')
    suite_schema=load(assets['property-candidate-suite.schema.json']);Draft202012Validator.check_schema(suite_schema);validator=Draft202012Validator(suite_schema)
    fixture=load(assets['fixtures/property-selectors-v1.json']);namespace=fixture['namespace'];bindings=namespace['bindings'];by_id={b['id']:b for b in bindings}
    require(len(by_id)==len(bindings), 'Duplicate fixture binding IDs')
    require(namespace['root'] in by_id, 'Unknown fixture root')
    require(set(namespace['properties'])==set(contract['keyCallbacks']+contract['tagCallbacks']), 'Fixture facet coverage differs from contract')
    for binding in bindings:
        require(binding['nodeKind'] in contract['nodeKinds'], 'Unknown fixture node kind')
        for field in ['key','tag']:
            if field in binding:require(isinstance(binding[field],str), 'Fixture strings must be explicit; use a fault for malformed metadata')
        refs=binding.get('children',[])+binding.get('heads',[])+list(binding.get('localSpaces',{}).values())+([binding['attributeSpace']] if 'attributeSpace' in binding else [])
        require(all(ref in by_id for ref in refs), 'Unknown fixture navigation/head handle')
        for head in binding.get('heads',[]):require(by_id[head]['nodeKind']=='NodeHead', 'Base direct-head graph must be valid; use a fault for wrong kind')
    seen=set();coverage=set();counts={}
    allowed={'property-parser':{'parse-address'},'property-resolve':{'resolve'},'property-query':{'query','parse-query'},'property-boundaries':{'consumer-boundary'}}
    require(len(manifest['suites'])==len(allowed) and {ref['id'] for ref in manifest['suites']}==set(allowed), 'Missing/extra/duplicate candidate suite')
    for ref in manifest['suites']:
        suite=load(verified(lane,ref));validator.validate(suite)
        require(suite['id']==ref['id'] and suite['meta']['suite_id']==ref['id'] and suite['meta']['lane']=='sansa-properties' and suite['meta']['profile']==PROFILE and suite['meta']['sut_protocol']==PROTOCOL, 'Suite identity/protocol mismatch')
        counts[suite['id']]=len(suite['tests'])
        for case in suite['tests']:
            require(case['id'] not in seen, 'Duplicate case ID');seen.add(case['id']);coverage.update(case['covers']);request=case['input'];expected=case['expected'];op=request['operation']
            require(op in allowed[suite['id']], 'Operation belongs in another suite')
            require(sum(name in request for name in ['source','ast','generate'])==1, 'Exactly one source/AST/generator required')
            if 'generate' in request:expand(request['generate'])
            if op in ['resolve','query','consumer-boundary']:require(request.get('namespace')==namespace['id'], 'Unknown namespace')
            for name in ['rebasedRoot','contextualRoot']:
                if name in request:require(request[name] in by_id, 'Unknown scoped root handle')
            for fault in request.get('faults',[]):require(fault['binding'] in by_id, 'Unknown fault binding')
            if op=='resolve':
                require('bindings' in expected and 'addresses' in expected, 'Resolve requires both binding and address expectations')
                require(all(x in by_id for x in expected['bindings']), 'Unknown expected binding')
                require(expected['addresses']==[by_id[x]['address'] for x in expected['bindings']], 'Canonical address witnesses differ from expected original handles')
                if not expected['ok']:require(expected['bindings']==expected['addresses']==[], 'Failure cannot return partial bindings')
            if op=='query':
                require('records' in expected, 'Query requires records, including an explicit empty set')
                for record in expected['records']:
                    require(record['candidate'] in by_id and all(x in by_id for x in record['valueBindings']), 'Unknown Query handle witness')
                if not expected['ok']:require(expected['records']==[], 'Failure cannot return partial Query records')
            if not expected['ok'] and op!='consumer-boundary':require('error' in expected, 'Failed operation requires an error identifier')
            if op=='consumer-boundary':require(request['consumer'] in contract['notAdmitted'] and expected.get('mustNotResolve') is True and expected['ok'] is False, 'Consumer admission was not granted by this candidate')
            if op=='parse-address' and expected['ok']:require('isExact' in expected, 'Successful parse requires explicit exactness')
            if 'repeat' in request:require(op=='query', 'Repeat probe is a Query invocation check')
            if 'reenter' in request:require(op=='query' and expected.get('nestedResultsOk') is True, 'Reentrant Query requires a nested-result assertion')
    require(set(fixture['coverageRequirements'])<=coverage, 'Missing required coverage family')
    return {'status':'prepared','cases':len(seen),'suites':counts,'specificationRevision':revision,'schemaAndDigestsValid':True,'sutExecuted':False,'acceptanceQualification':False,'defaultSelection':'exclude','methodAdopted':False}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,default=DEFAULT);parser.add_argument('--specs-root',type=Path,required=True);parser.add_argument('--check',action='store_true',required=True)
    args=parser.parse_args()
    try:print(json.dumps(check(args.manifest,args.specs_root)));return 0
    except Exception as error:
        # The message contains structural/schema context, never evaluated SUT data.
        print('Property preparation validation failed: '+str(error),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
