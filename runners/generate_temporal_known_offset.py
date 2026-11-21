#!/usr/bin/env python3
"""Regenerate only mutable known-offset fixtures; no implementation oracle or capture."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from temporal_known_offset_checks import PROFILE, CAPABILITIES, LIMITS, expected_positive

ROOT=Path(__file__).resolve().parents[1]
LANE='aeonic-temporal-known-offset'
TARGET=ROOT/'cts'/LANE/'v1'

def authored(text,**markers):return dict(temporal=dict(category='knownOffsetDateTime',value=text),**markers)
def point(text):return dict(kind='point',at=text)
def interval(start,end,il=True,ih=False):return dict(kind='interval',start=start,end=end,includeStart=il,includeEnd=ih)
def derived(pieces,frame='Z',original='undeclared',**markers):
    out=dict(temporal=dict(category='knownOffsetDateTimeSet',offset=frame,pieces=pieces),
        originDateGranularity='undeclared',originClockForm='undeclared',
        history=dict(clamping='none-declared',approximation='none-declared'),originalOffset=original)
    out.update(markers);return out

def request(op,a,b=None,dest='Z'):
    inp=dict(value=a,policy=dict(destinationOffset=dest)) if op=='convert' else dict(left=a,right=b)
    inp['context']=dict(profile=PROFILE)
    return dict(operation=op,input=inp)

def diagnostic(reason,stage,path=None):return dict(outcome='diagnostic',reason=reason,context=dict(stage=stage,path=path))
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=True,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(specs):
    suites={name:[] for name in ('01-conversion','02-relations','03-operands','04-policy-precedence','05-resources-transport','06-chains-laws')}
    def positive(name,r,suite='01-conversion',limits=None):
        lim=dict(LIMITS,**(limits or {}));t=dict(id=name,requires=['conversion' if r['operation']=='convert' else 'relations'],fixture=dict(request=r),expected=expected_positive(r,lim))
        if limits is not None:t['policy']=dict(resourceLimits=limits)
        suites[suite].append(t);return t
    def negative(name,r,reason,stage,path=None,suite='03-operands',limits=None,text=False,requires=None):
        op=r.get('operation') if isinstance(r,dict) else None
        req=requires if requires is not None else ['conversion'] if op=='convert' else ['relations'] if op in ('equal','compare','relate') else []
        t=dict(id=name,requires=req,fixture={'requestText' if text else 'request':r},expected=diagnostic(reason,stage,path))
        if limits is not None:t['policy']=dict(resourceLimits=limits)
        suites[suite].append(t);return t
    A=authored('2024-03-01T10:00:00+01:00');Z=authored('2024-03-01T09:00:00Z')
    for date in ('2024-','2024-03','2024-03-01'):
        for clock in ('09','09:','09:30','09:30:00','09:30:00.1000'):
            positive('completion-'+date+'-'+clock,request('convert',authored(date+'T'+clock+'+01:00'),dest='+02:00'))
    for dest in ('Z','+00:00','+01:00','-01:00','+23:59','-23:59'):
        positive('destination-'+dest,request('convert',A,dest=dest))
    for src in ('Z','+00:00','+23:59','-23:59'):
        positive('source-'+src,request('convert',authored('2024-03-01T00:00:00'+src)))
    positive('year-carry',request('convert',authored('2023-12-31T23:45-01:00')))
    positive('leap-day-minute',request('convert',authored('2024-03T00:30+01:00')))
    positive('upper-boundary-to-ordinary',request('convert',authored('9999-12-31T23:59+02:00'),dest='+01:00'))
    positive('ordinary-to-upper-boundary',request('convert',authored('9999-12-31T22:59+01:00'),dest='+02:00'))
    positive('same-upper-marker',request('convert',authored('9999-12-31T23:59Z')))
    marked=authored('2024-03-01T09:00:00.1+01:00',originDateGranularity='year',originClockForm='hour',history=dict(clamping='clamping-declared',approximation='approximation-declared'))
    positive('preserve-all-markers',request('convert',marked,dest='+00:00'))
    gap=derived([interval('2024-03-01T09:00:00','2024-03-01T10:00:00',False,False),interval('2024-03-01T10:00:00','2024-03-01T11:00:00',False,True)])
    positive('excluded-shared-point-remains-missing',request('convert',gap,dest='+01:00'))
    positive('long-continuous-interval-one-piece',request('convert',derived([interval('2024-01-01T00:00:00','2025-01-01T00:00:00')]),dest='+01:00'),limits=dict(maxWork=1,maxIntermediatePieces=1,maxOutputPieces=1,maxInputPieces=1))
    for il in (False,True):
        for ih in (False,True):positive('flags-%s-%s'%(il,ih),request('convert',derived([interval('2024-03-01T00:00:00','2024-03-01T00:00:00.1',il,ih)]),dest='-23:59'))
    fraction='0'*300+'1'
    positive('raised-exact-fraction',request('convert',authored('2024-03-01T00:00:00.'+fraction+'Z')),limits=dict(maxFractionDigits=301))
    positive('derived-undeclared-origin',request('convert',derived([point('2024-03-01T00:00:00')],frame='+01:00')))
    positive('authored-explicit-metadata',request('convert',authored('2024-03-01T00:00:00Z',originDateGranularity='undeclared',originClockForm='undeclared')))
    day='2024-03-01T';minute=authored(day+'09:00Z');start=authored(day+'09:00:00Z');end=authored(day+'09:01:00Z')
    straddle=derived([point(day+'10:00:00'),point(day+'12:00:00')],frame='+01:00')
    middle=authored(day+'12:00:00+02:00')
    pairs=[('cross-frame-equal',A,Z),('zero-form-equal',Z,authored(day+'09:00:00+00:00')),
      ('contains-start',minute,start),('excluded-end',minute,end),('strict-before',start,end),
      ('disjoint-interleaved',straddle,middle),('overlapping',minute,derived([interval(day+'09:00:30',day+'09:01:30')])),
      ('below-zero-common',authored('0001-01-01T00:30:00+01:00'),authored('0001-01-01T00:00:00Z')),
      ('above-B-common',authored('9999-12-31T23:59:59-01:00'),authored('9999-12-31T23:59:59Z')),
      ('metadata-distinct',marked,authored('2024-03-01T08:00:00.1Z')),
      ('year-completion-equality',authored('2024-T09:30Z'),authored('2024-T10:30+01:00'))]
    for name,left,right in pairs:
        for op in ('equal','compare','relate'):
            for reverse in (False,True):
                positive(name+'-'+op+('-reverse' if reverse else ''),request(op,right if reverse else left,left if reverse else right),suite='02-relations')
    positive('relations-no-output-piece-charge',request('compare',start,end),suite='02-relations',limits=dict(maxIntermediatePieces=0,maxOutputPieces=0))
    for text in ('2024-02-30T09:00Z','0000-01-01T09:00Z','2024-01-01T24:00Z','2024-01-01T09:60Z','2024-01-01T09:00:61Z','2024-01-01T09:00:00,1Z','2024-01-01T09:00+24:00','2024-01-01T09:00+01:00:01','2024-01-01T09:00Z&','2024-01-01T09:00Z\n','T09:30Z'):
        negative('malformed-'+repr(text),request('convert',authored(text)),'invalid_operand',4,'/input/value/temporal/value')
    deferred_texts=('2024-03-01T09:00','2024-03-01T09:00-00:00','09:30Z','09:+01:00','2024-03-01T09:00:60Z','2024-03-01T23:59:60.1+01:00','2024-03-01T09:00Z&Europe/Paris','2024-03-01T09:00+01:00&local')
    for text in deferred_texts:negative('deferred-'+text,request('convert',authored(text)),'unsupported_domain',5,'/input/value/temporal/category')
    for key,value in [('clockModel','direct'),('clockModel','smear'),('timescale','TAI')]:
        negative('deferred-claim-'+value,request('convert',authored(day+'09:00Z',**{key:value})),'unsupported_domain',5,'/input/value/temporal/category')
    for key,value in [('clockModel',''),('timescale',None),('history',{}),('originClockForm','nano'),('originDateGranularity','week'),('originalOffset','Z')]:
        path='/input/value/'+key+('/clamping' if key=='history' else '')
        negative('invalid-marker-'+key,request('convert',authored(day+'09:00Z',**{key:value})),'invalid_operand',4,path)
    raw=derived([point(day+'09:00:00')])
    for key in ('originDateGranularity','originClockForm','history','originalOffset'):
        val=copy.deepcopy(raw);val.pop(key);negative('missing-derived-'+key,request('convert',val),'invalid_operand',4,'/input/value/'+key)
    negative('empty-derived',request('convert',derived([])),'invalid_operand',4,'/input/value/temporal/pieces')
    for frame in ('-00:00',):negative('unknown-derived-frame',request('convert',derived([point(day+'09:00:00')],frame=frame)),'unsupported_domain',5,'/input/value/temporal/category')
    for text in (day+'09:00:00.10',day+'09:00:00.0',day+'09:00:60',day+'09:00',day+'09:00:00Z'):
        negative('bad-derived-coordinate-'+text,request('convert',derived([point(text)])),'invalid_operand',4,'/input/value/temporal/pieces/0/at')
    for label,pieces in [('zero',[interval(day+'09:00:00',day+'09:00:00',True,True)]),('reversed',[interval(day+'10:00:00',day+'09:00:00')]),('overlap',[interval(day+'09:00:00',day+'10:00:00'),point(day+'09:30:00')]),('unsorted',[point(day+'10:00:00'),point(day+'09:00:00')]),('mergeable',[interval(day+'09:00:00',day+'10:00:00'),interval(day+'10:00:00',day+'11:00:00')])]:
        field='0/end' if label in ('zero','reversed') else '1/'+('start' if label=='mergeable' else 'at')
        negative('noncanonical-'+label,request('convert',derived(pieces)),'invalid_operand',4,'/input/value/temporal/pieces/'+field)
    for label,piece,path in [('point',point(dict(boundary='endOfDomain')),'at'),('start',interval(dict(boundary='endOfDomain'),day+'10:00:00'),'start'),('included',interval(day+'09:00:00',dict(boundary='endOfDomain'),True,True),'includeEnd')]:
        negative('invalid-boundary-'+label,request('convert',derived([piece])),'invalid_operand',4,'/input/value/temporal/pieces/0/'+path)
    for tag in ('civilDate','civilClockSet','exactRational','container','temporal'):
        negative('opaque-'+tag,request('convert',dict(temporal=dict(category=tag,payload={'anything':[1,2,3]}))),'unsupported_domain',5,'/input/value/temporal/category')
    negative('unknown-category',request('convert',dict(temporal=dict(category='typo'))),'invalid_operand',4,'/input/value/temporal/category')
    # Configuration and competing failures.
    suite='04-policy-precedence'
    for dest in ('-00:00','+24:00','+01:00:01','',None):
        negative('invalid-destination-'+repr(dest),request('convert',A,dest=dest),'invalid_policy',3,'/input/policy/destinationOffset',suite)
    r=request('convert',A);r['input']['policy'].pop('destinationOffset');negative('missing-destination',r,'invalid_policy',3,'/input/policy/destinationOffset',suite)
    r=request('convert',A);r['input'].pop('policy');negative('missing-policy',r,'invalid_policy',3,'/input/policy',suite)
    r=request('convert',A);r['input'].pop('context');negative('missing-profile',r,'invalid_policy',3,'/input/policy/profile',suite)
    r=request('convert',A);r['input']['context']['profile']='future';negative('unavailable-profile',r,'unsupported_profile',3,'/input/context/profile',suite)
    r=request('convert',A);r['input']['context']['profile']='future';r['input']['policy']['profile']=PROFILE;positive('policy-overrides-context',r,suite)
    r=request('convert',A);r['input']['context']['profile']=None;r['input']['policy']['profile']=PROFILE;negative('bad-overridden-context',r,'invalid_policy',3,'/input/context/profile',suite)
    r=request('compare',A,Z);r['input']['policy']=dict(destinationOffset='Z');negative('relation-destination-forbidden',r,'invalid_policy',3,'/input/policy/destinationOffset',suite)
    r=request('compare',authored('09:30Z'),authored('2024-02-30T09:30Z'));negative('malformed-right-beats-deferred-left',r,'invalid_operand',4,'/input/right/temporal/value',suite)
    r=request('compare',authored('2024-02-30T09:30Z'),authored('2024-02-31T09:30Z'));negative('malformed-left-before-right',r,'invalid_operand',4,'/input/left/temporal/value',suite)
    r=request('compare',authored('09:30Z'),authored('10:30Z'));negative('deferred-left-before-right',r,'unsupported_domain',5,'/input/left/temporal/category',suite)
    r=request('convert',authored('bad'),dest='-00:00');negative('bad-policy-before-operand',r,'invalid_policy',3,'/input/policy/destinationOffset',suite)
    r=dict(operation='future',input=dict(value=authored('bad'),policy=None));negative('dispatch-before-policy',r,'unsupported_operation',2,'/operation',suite,requires=[])
    negative('unknown-request-field',dict(request('convert',A),extra=True),'invalid_operand',2,'/extra',suite)
    r=request('convert',A);r['input']['extra']=True;negative('unknown-input-field',r,'invalid_operand',2,'/input/extra',suite)
    out=request('convert',authored('0001-01-01T00:30:00+01:00'))
    negative('lower-domain',out,'unrepresentable_result',6,suite=suite)
    negative('work-before-domain',out,'resource_limit',6,suite=suite,limits=dict(maxWork=0))
    negative('candidate-before-domain',out,'resource_limit',6,suite=suite,limits=dict(maxIntermediatePieces=0))
    negative('domain-before-output',out,'unrepresentable_result',6,suite=suite,limits=dict(maxOutputPieces=0,maxResultBytes=0))
    negative('upper-domain',request('convert',authored('9999-12-31T23:59:59-01:00')),'unrepresentable_result',6,suite=suite)
    # Capacity boundaries and JSON admission.
    suite='05-resources-transport'
    for key in ('maxInputPieces','maxWork','maxIntermediatePieces','maxOutputPieces','maxResultBytes'):
        negative('zero-'+key,request('convert',A),'resource_limit',4 if key=='maxInputPieces' else 7 if key in ('maxOutputPieces','maxResultBytes') else 6,'/input/value/temporal' if key=='maxInputPieces' else None,suite,limits={key:0})
    positive('exact-one-piece-capacity',request('convert',A),suite,dict(maxInputPieces=1,maxWork=1,maxIntermediatePieces=1,maxOutputPieces=1))
    negative('same-frame-pays-work',request('convert',Z),'resource_limit',6,suite=suite,limits=dict(maxWork=0))
    positive('two-input-exact-total',request('equal',A,Z),suite,dict(maxInputPieces=2,maxWork=2))
    negative('two-input-total-over',request('equal',A,Z),'resource_limit',4,'/input/right/temporal',suite,limits=dict(maxInputPieces=1))
    negative('relation-summed-work-over',request('equal',A,Z),'resource_limit',6,suite=suite,limits=dict(maxWork=1))
    year=authored('2024-T09:30Z')
    positive('year-expansion-exact-366',request('convert',year),suite,dict(maxInputPieces=366,maxWork=366,maxIntermediatePieces=366,maxOutputPieces=366))
    negative('year-expansion-over-365',request('convert',year),'resource_limit',4,'/input/value/temporal',suite,limits=dict(maxInputPieces=365))
    positive('two-year-expansion-exact-732',request('equal',year,year),suite,dict(maxInputPieces=732,maxWork=732))
    negative('two-year-total-over-731',request('equal',year,year),'resource_limit',4,'/input/right/temporal',suite,limits=dict(maxInputPieces=731))
    negative('array-budget-before-malformed-content',request('convert',derived([point('bad')])),'resource_limit',4,'/input/value/temporal/pieces',suite,limits=dict(maxInputPieces=0))
    negative('fraction-before-canonicality',request('convert',derived([point(day+'09:00:00.10')])),'resource_limit',4,'/input/value/temporal/pieces/0/at',suite,limits=dict(maxFractionDigits=1))
    negative('authored-fraction-counts-trailing-zeroes',request('convert',authored(day+'09:00:00.100Z')),'resource_limit',4,'/input/value/temporal/value',suite,limits=dict(maxFractionDigits=2))
    negative('text-before-grammar',request('convert',authored('bad')),'resource_limit',4,'/input/value/temporal/value',suite,limits=dict(maxTemporalCharacters=2))
    r=request('convert',A);text=json.dumps(r,separators=(',',':'))
    n=len(text.encode());positive('exact-request-bytes',r,suite,dict(maxRequestBytes=n))
    negative('request-bytes-one-over',text,'resource_limit',1,suite=suite,limits=dict(maxRequestBytes=n-1),text=True,requires=['conversion'])
    success=expected_positive(r);n=len(json.dumps(success,separators=(',',':')).encode())
    positive('exact-result-bytes',r,suite,dict(maxResultBytes=n))
    negative('result-bytes-one-over',r,'resource_limit',7,suite=suite,limits=dict(maxResultBytes=n-1))
    negative('request-depth',r,'resource_limit',1,suite=suite,limits=dict(maxRequestDepth=1))
    negative('duplicate-key','{"operation":"convert","operation":"equal","input":{}}','invalid_operand',2,suite=suite,text=True,requires=[])
    negative('malformed-json','{','invalid_operand',2,suite=suite,text=True,requires=[])
    negative('nonobject-request',None,'invalid_operand',2,suite=suite,requires=[])
    negative('negative-zero-opaque-text','{"operation":"convert","input":{"value":{"temporal":{"category":"container","payload":-0}},"context":{"profile":"'+PROFILE+'"},"policy":{"destinationOffset":"Z"}}}','unsupported_domain',5,'/input/value/temporal/category',suite,text=True,requires=['conversion'])
    # Transport preserves the exact raw token spelling when admitting bytes.
    raw='{"operation":"convert","input":{"value":{"temporal":{"category":"container","payload":-0}},"context":{"profile":"'+PROFILE+'"},"policy":{"destinationOffset":"Z"}}}'
    negative('negative-zero-exact-byte-limit',raw,'unsupported_domain',5,'/input/value/temporal/category',suite,limits=dict(maxRequestBytes=len(raw.encode())),text=True,requires=['conversion'])
    negative('negative-zero-byte-limit-minus-one',raw,'resource_limit',1,suite=suite,limits=dict(maxRequestBytes=len(raw.encode())-1),text=True,requires=['conversion'])
    t=positive('raw-success-whitespace',request('convert',A),suite)
    t['fixture']={'requestText':json.dumps(t['fixture']['request'],indent=2)}
    # Literal source chain expected placeholders are replaced at validation and execution.
    suite='06-chains-laws'
    for mixed in (False,True):
        r0=request('convert',marked,dest='Z');e0=expected_positive(r0)
        r1=request('convert',e0['value'],dest='+02:00');e1=expected_positive(r1)
        steps=[dict(request=r0,expected=e0),dict(request=request('convert',A,dest='+02:00'),expected=e1)]
        links=[dict(fromStep=0,toStep=1,input='value')]
        if mixed:
            r2=request('equal',e1['value'],authored('2024-03-01T08:00:00.1Z'));e2=expected_positive(r2)
            steps.append(dict(request=request('equal',A,Z),expected=e2));links.append(dict(fromStep=1,toStep=2,input='left'))
            steps[2]['request']['input']['right']=r2['input']['right']
        suites[suite].append(dict(id='actual-returned-chain'+('-relations' if mixed else ''),kind='chain',requires=['conversion','relations'] if mixed else ['conversion'],steps=steps,links=links))
    suites[suite].append(dict(id='cross-frame-ordering-laws',kind='laws',requires=['relations'],values=[A,Z,end]))
    for key,tests in suites.items():write(TARGET/'suites'/(key+'.json'),dict(id=key,tests=tests))
    binding=json.loads((ROOT/'cts/aeonic-temporal-civil-anchor/v1/binding.schema.json').read_text())
    binding['$id']='urn:aeonic-temporal-known-offset:cts-binding:v1:working';binding['properties']['lane']['const']=LANE
    schema=json.loads((specs/'resources/aeonic-operations/v1/known-offset-contract.schema.json').read_text())
    binding['properties']['policy']['properties']['resourceLimits']=schema['$defs']['resourceLimits']
    write(TARGET/'binding.schema.json',binding)
    helpers=['runners/run_aeonic_arithmetic.py','runners/run_aeonic_rational_arithmetic.py','runners/temporal_civil_date_checks.py','runners/temporal_civil_datetime_checks.py','runners/temporal_known_offset_checks.py']
    import subprocess
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=specs,text=True).strip()
    meta=dict(version='0.1.0-dev.0',lane=LANE,profile=PROFILE,capabilities={k:dict(id=v[0],operations=list(v[1])) for k,v in CAPABILITIES.items()},sut_protocol='cts.protocol.v1',conformance=dict(surface='working-next',stable=False),description='Mutable known-offset coordinate contract; no immutable or stable conformance claim.',snapshot_id=LANE+'-cts-v1-snapshot-0.1',specification_revision=revision,specification_source='sources/aes/v1/aeonic-temporal-known-offset-v1.aeon',specification_schema='resources/aeonic-operations/v1/known-offset-contract.schema.json',binding_schema='binding.schema.json',helpers={f:sha(ROOT/f) for f in helpers},resource_limits=LIMITS)
    for key in ('specification_source','specification_schema'):meta[key+'_sha256']=sha(specs/meta[key])
    meta['binding_schema_sha256']=sha(TARGET/'binding.schema.json')
    write(TARGET/(LANE+'-cts.v1.next.json'),dict(meta=meta,suites=[dict(id=k,file='suites/'+k+'.json',content_sha256=sha(TARGET/'suites'/(k+'.json'))) for k in suites]))
    print('Generated',sum(map(len,suites.values())),'cases in',len(suites),'suites')

if __name__=='__main__':generate(Path(sys.argv[1]).resolve())
