"""Bounded positive fixture checks for known-offset coordinates; no diagnostic engine."""
import copy
import re
import json
from run_aeonic_arithmetic import RawNumber, equal, pairs, require
from temporal_civil_date_checks import compact_bytes, decode_artifact, validate_pointer_text
from temporal_civil_datetime_checks import (B, coverage as civil_coverage,
    format_coordinate, history, origin as civil_origin, relation_labels)

PROFILE = 'aeonic.operations.temporal.known-offset.v1'
CAPABILITIES = {
    'conversion': ('Aeonic.Operations.Temporal.KnownOffset.Conversion', ('convert',)),
    'relations': ('Aeonic.Operations.Temporal.KnownOffset.Relations', ('equal','compare','relate')),
}
LIMITS = dict(maxRequestBytes=65536, maxRequestDepth=32, maxTemporalCharacters=1024,
              maxInputPieces=1024, maxIntermediatePieces=1024, maxOutputPieces=1024,
              maxWork=2048, maxFractionDigits=256, maxResultBytes=262144)


def offset(text):
    require(isinstance(text,str) and re.fullmatch(r'Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]',text)
            and text!='-00:00','Expected known offset')
    return 0 if text=='Z' else (1 if text[0]=='+' else -1)*(int(text[1:3])*3600+int(text[4:])*60)


def mapped(bundle):
    """Map an eligible bundle to the existing exact civil coverage checker."""
    td=bundle['temporal']; out=copy.deepcopy(bundle)
    out.pop('originalOffset',None)
    require('clockModel' not in out and 'timescale' not in out,'Deferred extra claim')
    if td['category']=='knownOffsetDateTime':
        value=td['value']; m=re.search(r'(Z|[+-][0-9]{2}:[0-9]{2})$',value)
        require(m is not None and 'T' in value and '&' not in value,'Deferred authored form')
        frame=m.group(); offset(frame); text=value[:m.start()]
        if text.endswith(':'): text=text[:-1]
        out['temporal']=dict(category='civilDateTime',value=text)
    else:
        require(td['category']=='knownOffsetDateTimeSet','Deferred descriptor')
        frame=td['offset'];offset(frame)
        out['temporal']=dict(category='civilDateTimeSet',pieces=td['pieces'])
    return out,frame


def coverage(bundle, maximum, limits=LIMITS, generated=False):
    td=bundle['temporal']
    if td['category']=='knownOffsetDateTime':
        require(len(td['value'])<=limits['maxTemporalCharacters'],'Literal exceeds text limit')
    mapped_bundle,_=mapped(bundle)
    return civil_coverage(mapped_bundle,maximum,limits,generated)


def origin(bundle):
    return civil_origin(mapped(bundle)[0])


def original(bundle):
    return mapped(bundle)[1] if bundle['temporal']['category']=='knownOffsetDateTime' else bundle['originalOffset']


def common(bundle, maximum, limits=LIMITS):
    o=offset(mapped(bundle)[1])
    return [(lo-o,hi-o,il,ih) for lo,hi,il,ih in coverage(bundle,maximum,limits)]


def render(spans):
    pieces=[]
    for lo,hi,il,ih in spans:
        if lo==hi:pieces.append(dict(kind='point',at=format_coordinate(lo)))
        else:pieces.append(dict(kind='interval',start=format_coordinate(lo),
            end=dict(boundary='endOfDomain') if hi==B else format_coordinate(hi),
            includeStart=il,includeEnd=ih))
    return pieces


def effective(logical):
    data=logical['input'];policy=data.get('policy',{})
    return dict(policy,profile=policy.get('profile',data.get('context',{}).get('profile')))


def relation_result(op,left,right,label):
    return dict(outcome='value',value=dict(category='symbol',value=label),
        metadata=dict(evaluation='exact-for-policy',clamping='not-applied',
            effectivePolicy=dict(profile=PROFILE),
            operandHistory=dict(left=history(left),right=history(right)),
            operandOrigin=dict(left=origin(left),right=origin(right)),
            operandOriginalOffset=dict(left=original(left),right=original(right))))


def decode_request(text):
    """Strict standalone logical JSON, preserving every numeric token spelling."""
    def constant(value):
        raise ValueError('Non-JSON constant: '+value)
    return json.loads(text, object_pairs_hook=pairs, parse_int=RawNumber,
                      parse_float=RawNumber, parse_constant=constant)


def law_witnesses(values, limits=LIMITS):
    """Require different logical representations of equal coverage and a before triple."""
    spans=[common(value,limits['maxInputPieces'],limits) for value in values]
    labels={(i,j):relation_labels(a,b) for i,a in enumerate(spans) for j,b in enumerate(spans)}
    equality=any(i!=j and not equal(values[i],values[j]) and result['equal']=='equal'
                 for (i,j),result in labels.items())
    before=sum(labels[i,j]['compare']==labels[j,k]['compare']=='before'
               for i in range(len(values)) for j in range(len(values)) for k in range(len(values)))
    require(equality,'Law group needs distinct inputs with equal coverage')
    require(before>0,'Law group needs a strict-before transitivity witness')
    return before


def expected_positive(logical, limits=LIMITS):
    """Check only successful requests; never synthesize staged failure diagnostics."""
    compact_bytes(logical,limits['maxRequestBytes'])
    stack=[(logical,1)]
    while stack:
        node,depth=stack.pop()
        if isinstance(node,(dict,list)):
            require(depth<=limits['maxRequestDepth'],'Request exceeds depth')
            stack.extend((v,depth+1) for v in (node.values() if isinstance(node,dict) else node)
                         if isinstance(v,(dict,list)))
    data=logical['input'];op=logical['operation'];p=effective(logical)
    require(p['profile']==PROFILE,'Unavailable profile')
    operands=[data['value']] if op=='convert' else [data['left'],data['right']]
    remaining=limits['maxInputPieces'];local=[]
    for value in operands:
        parts=coverage(value,remaining,limits);remaining-=len(parts);local.append(parts)
    work=sum(map(len,local));require(work<=limits['maxWork'],'Work exceeds limit')
    if op=='convert':
        require(len(local[0])<=limits['maxIntermediatePieces'],'Candidates exceed limit')
        source=offset(mapped(operands[0])[1]);dest=offset(p['destinationOffset'])
        translated=[(lo+dest-source,hi+dest-source,il,ih) for lo,hi,il,ih in local[0]]
        require(all(lo>=0 and hi<=B and (hi<B or not ih) for lo,hi,il,ih in translated),'Result outside frame domain')
        require(len(translated)<=limits['maxOutputPieces'],'Output pieces exceed limit')
        o=origin(operands[0])
        value=dict(temporal=dict(category='knownOffsetDateTimeSet',offset=p['destinationOffset'],pieces=render(translated)),
            originDateGranularity=o['dateGranularity'],originClockForm=o['clockForm'],
            history=history(operands[0]),originalOffset=original(operands[0]))
        result=dict(outcome='value',value=value,metadata=dict(evaluation='exact-for-policy',clamping='not-applied',effectivePolicy=p))
    else:
        require(op in CAPABILITIES['relations'][1],'Unavailable operation')
        spans=[]
        for value,parts in zip(operands,local):
            o=offset(mapped(value)[1]);spans.append([(lo-o,hi-o,il,ih) for lo,hi,il,ih in parts])
        labels=relation_labels(*spans)
        result=relation_result(op,*operands,labels[op])
    compact_bytes(result,limits['maxResultBytes'])
    return result
