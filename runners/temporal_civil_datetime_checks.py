"""Civil date-time CTS admission, canonical-set and relation checks; no shift engine."""
from calendar import isleap, monthrange
from datetime import date, timedelta
from fractions import Fraction
import re

from run_aeonic_arithmetic import require
from run_aeonic_rational_arithmetic import decimal_integer
from temporal_civil_date_checks import compact_bytes, decode_artifact, validate_pointer_text

PROFILE = 'aeonic.operations.temporal.civil-datetime.v1'
CAPABILITIES = {
    'relations': ('Aeonic.Operations.Temporal.CivilDateTime.Relations', ('equal', 'compare', 'relate')),
    'arithmetic': ('Aeonic.Operations.Temporal.CivilDateTime.Arithmetic', ('shift', 'shiftClock', 'step', 'materialize')),
}
LIMITS = dict(maxRequestBytes=65536, maxRequestDepth=32, maxTemporalCharacters=1024,
              maxInputPieces=512, maxIntermediatePieces=4096, maxOutputPieces=512,
              maxWork=16384, maxFractionDigits=256, maxCountCharacters=32,
              maxNumericCharacters=4096, maxCoefficientDigits=1024,
              maxExponentMagnitude=1000000, maxWorkspaceDigits=4096,
              maxOutputCharacters=1024, maxResultBytes=131072)
B = date.max.toordinal() * 86400
COORD = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?')
AUTH = re.compile(r'([0-9]{4}-(?:[0-9]{2}(?:-[0-9]{2})?)?)T([0-9]{2})(?::([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?)?')
NONE = dict(clamping='none-declared', approximation='none-declared')


def history(bundle):
    return dict(bundle.get('history', NONE))


def origin(bundle):
    td = bundle['temporal']
    if td['category'] == 'civilDateTime':
        ds, ts = td['value'].split('T')
        default_date = 'year' if ds.endswith('-') else 'month' if len(ds) == 7 else 'day'
        default_clock = ('hour', 'minute', 'second')[ts.count(':')]
    else:
        default_date = default_clock = 'undeclared'
    return dict(dateGranularity=bundle.get('originDateGranularity', default_date),
                clockForm=bundle.get('originClockForm', default_clock))


def coordinate(text, limits=LIMITS, generated=False):
    require(isinstance(text, str), 'Expected ordinary coordinate text')
    require(len(text) <= (20 + limits['maxFractionDigits'] if generated else limits['maxTemporalCharacters']),
            'Coordinate exceeds text allowance')
    m = COORD.fullmatch(text); require(m is not None, 'Invalid complete coordinate')
    ds, hh, mm, ss, fraction = m.groups(); fraction = fraction or ''
    require(len(fraction) <= limits['maxFractionDigits'], 'Fraction exceeds allowance')
    require(not fraction or fraction[-1] != '0', 'Noncanonical derived fraction')
    d = date.fromisoformat(ds)
    require(d.isoformat() == ds and int(hh) < 24 and int(mm) < 60 and int(ss) < 60,
            'Invalid coordinate fields')
    return Fraction((d.toordinal()-1)*86400 + int(hh)*3600 + int(mm)*60 + int(ss)) + (Fraction(decimal_integer(fraction), 10**len(fraction)) if fraction else 0)


def decimal_text(value):
    """Render admitted integers without Python's process-global decimal ceiling."""
    if value == 0:
        return '0'
    sign = '-' if value < 0 else ''
    value = abs(value); chunks = []
    while value:
        value, remainder = divmod(value, 10**9)
        chunks.append('%09d' % remainder)
    return sign + chunks[-1].lstrip('0') + ''.join(reversed(chunks[:-1]))


def decimal_factors(denominator):
    twos = (denominator & -denominator).bit_length() - 1
    denominator >>= twos; fives = 0
    while denominator % 5 == 0:
        denominator //= 5; fives += 1
    require(denominator == 1, 'Coordinate is not finite decimal')
    return twos, fives


def format_coordinate(x):
    """Render an already bounded finite coordinate for a complete-form template."""
    whole = x.numerator // x.denominator
    d = date.fromordinal(whole//86400 + 1); sec = whole % 86400
    text = '%04d-%02d-%02dT%02d:%02d:%02d' % (d.year,d.month,d.day,sec//3600,sec//60%60,sec%60)
    f = x-whole
    if f:
        twos,fives=decimal_factors(f.denominator)
        scale=max(twos,fives)
        digits=decimal_text(f.numerator * 2**(scale-twos) * 5**(scale-fives)).zfill(scale).rstrip('0')
        text+='.'+digits
    return text


def period(first, granularity):
    if granularity == 'day': return first, 1
    if granularity == 'month': return date(first.year,first.month,1), monthrange(first.year,first.month)[1]
    return date(first.year,1,1), 366 if isleap(first.year) else 365


def coverage(bundle, maximum, limits=LIMITS, generated=False):
    td=bundle['temporal']
    if td['category'] == 'civilDateTime':
        value=td['value']; require(len(value) <= (limits['maxOutputCharacters'] if generated else limits['maxTemporalCharacters']), 'Literal exceeds text allowance')
        m=AUTH.fullmatch(value); require(m is not None, 'Invalid unqualified literal')
        ds,hh,mm,ss,fraction=m.groups(); fraction=fraction or ''
        require(len(fraction) <= limits['maxFractionDigits'], 'Fraction exceeds allowance')
        require(int(hh)<24 and (mm is None or int(mm)<60) and (ss is None or int(ss)<60), 'Invalid clock')
        gran='year' if ds.endswith('-') else 'month' if len(ds)==7 else 'day'
        first=date(int(ds[:4]), int(ds[5:7]) if gran!='year' else 1, int(ds[8:10]) if gran=='day' else 1)
        first,n=period(first,gran); require(n <= maximum, 'Literal expansion exceeds piece allowance')
        sec=Fraction(int(hh)*3600 + (int(mm)*60 if mm is not None else 0) + (int(ss) if ss is not None else 0))
        if fraction: sec+=Fraction(decimal_integer(fraction),10**len(fraction))
        width=3600 if mm is None else 60 if ss is None else 0
        return [(Fraction((first.toordinal()-1+i)*86400)+sec, Fraction((first.toordinal()-1+i)*86400)+sec+width, True, width==0) for i in range(n)]
    require(td['category']=='civilDateTimeSet', 'Deferred temporal domain')
    raw=td['pieces']; require(isinstance(raw,list) and 0<len(raw)<=maximum, 'Set exceeds piece allowance')
    spans=[]
    for p in raw:
        if p['kind']=='point':
            at=coordinate(p['at'],limits,generated); span=(at,at,True,True)
        else:
            start=coordinate(p['start'],limits,generated)
            if isinstance(p['end'],dict):
                require(p['end']==dict(boundary='endOfDomain') and p['includeEnd'] is False, 'Invalid upper boundary')
                end=Fraction(B)
            else: end=coordinate(p['end'],limits,generated)
            require(start<end, 'Nonpositive interval width')
            span=(start,end,p['includeStart'],p['includeEnd'])
        if spans:
            previous=spans[-1]
            require(previous[1]<span[0] or (previous[1]==span[0] and not previous[3] and not span[2]), 'Noncanonical set order, overlap or mergeable boundary')
        spans.append(span)
    return spans


def effective(logical):
    data=logical['input']; policy=data.get('policy',{})
    return dict(policy, profile=policy.get('profile',data.get('context',{}).get('profile')))


def decimal_properties(bundle, limits=LIMITS):
    n=bundle['number']; kind=n['category']
    if kind=='finiteNumber':
        raw=n['value']; require(len(raw)<=limits['maxNumericCharacters'], 'Amount text exceeds allowance')
        m=re.fullmatch(r'([+-]?)([0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?',raw)
        require(m is not None, 'Invalid finite amount'); sign,mantissa,exp=m.groups(); exp=exp or '0'
        digits=exp.lstrip('+-').lstrip('0') or '0'; maximum=str(limits['maxExponentMagnitude'])
        require(len(digits)<len(maximum) or (len(digits)==len(maximum) and digits<=maximum), 'Authored exponent exceeds allowance')
        exponent=int(('-' if exp.startswith('-') else '')+digits); fractional=len(mantissa.split('.')[1]) if '.' in mantissa else 0
        coefficient=mantissa.replace('.','').lstrip('0')
        if not coefficient: coefficient='0'; exponent=0
        else:
            exponent-=fractional; removed=len(coefficient)-len(coefficient.rstrip('0')); coefficient=coefficient.rstrip('0'); exponent+=removed
            if sign=='-':coefficient='-'+coefficient
    else:
        require(kind=='exactNumber','Deferred amount domain'); coefficient=n['coefficient']; exp=n['exponent']
        require(len(coefficient)+len(exp)<=limits['maxNumericCharacters'], 'Amount text exceeds allowance')
        require(re.fullmatch(r'0|-?[1-9](?:[0-9]*[1-9])?',coefficient) is not None and re.fullmatch(r'0|-?[1-9][0-9]*',exp) is not None,'Noncanonical amount')
        digits=exp.lstrip('-');maximum=str(limits['maxExponentMagnitude'])
        require(len(digits)<len(maximum) or (len(digits)==len(maximum) and digits<=maximum), 'Exponent exceeds allowance')
        exponent=int(exp); require(coefficient!='0' or exponent==0, 'Noncanonical zero amount')
    require(len(coefficient.lstrip('-'))<=limits['maxCoefficientDigits'] and abs(exponent)<=limits['maxExponentMagnitude'], 'Normalized amount exceeds allowance')
    return coefficient,exponent


def template(logical, spans, maximum, limits=LIMITS, target=False):
    """Construct the single selected complete form; not a shift implementation."""
    p=logical['input']['policy']; dg=p['dateGranularity']; cf=p['clockForm']; x=spans[0][0]
    first=date.fromordinal(int(x//86400)+1); first,n=period(first,dg); source_count=n
    if target:
        count=p['count']; require(len(count)<=limits['maxCountCharacters'] and len(count.lstrip('-'))<=7,'Positive step count exceeds domain')
        count=int(count)
        if dg=='year': first=date(first.year+count,1,1)
        elif dg=='month':
            index=(first.year-1)*12+first.month-1+count; first=date(index//12+1,index%12+1,1)
        else:first+=timedelta(days=count)
        first,n=period(first,dg)
    if target:
        require(len(spans)+source_count+n<=limits['maxWork'],'Target template work exceeds allowance')
    require(n<=maximum,'Template expansion exceeds allowance')
    clock=format_coordinate(x).split('T')[1]
    clock=clock[:2] if cf=='hour' else clock[:5] if cf=='minute' else clock
    ds=('%04d-'%first.year) if dg=='year' else ('%04d-%02d'%(first.year,first.month)) if dg=='month' else first.isoformat()
    bundle=dict(temporal=dict(category='civilDateTime',value=ds+'T'+clock))
    return bundle,coverage(bundle,maximum,limits)


def positive_cost(logical, spans, limits=LIMITS):
    op=logical['operation'];p=logical['input'].get('policy',{});P=len(spans[0])
    if op in CAPABILITIES['relations'][1]:return sum(map(len,spans)),0
    if op=='shiftClock':
        c,e=decimal_properties(logical['input']['amount'],limits)
        # Reduced decimal denominators determine precision without rendering text.
        f=max(max(decimal_factors(x.denominator)) for part in spans[0] for x in part[:2] if x<B)
        q=max(f,max(0,-e));require((0 if c=='0' else 13+q)<=limits['maxWorkspaceDigits'],'Clock workspace exceeds allowance')
        require(c=='0' or max(0,-e)<=limits['maxFractionDigits'],'Generated fraction exceeds allowance')
        return P,P
    if op=='shift':
        count=p['count'];require(len(count)<=limits['maxCountCharacters'],'Count exceeds allowance')
        if p['unit']=='day' or count=='0':return P,P
        D=0
        for lo,hi,il,ih in spans[0]:
            last=hi//86400
            if hi>lo and hi%86400==0 and not ih:last-=1
            D+=last-lo//86400+1
        return D,D
    dg=p['dateGranularity']; anchor=date.fromordinal(int(spans[0][0][0]//86400)+1);S=period(anchor,dg)[1]
    require(P+S<=limits['maxWork'] and S<=limits['maxIntermediatePieces'],'Source template exceeds allowance')
    _,source=template(logical,spans[0],S,limits);require(source==spans[0],'Positive fixture does not match selected complete form')
    if op=='materialize':return P+S,S
    _,target=template(logical,spans[0],limits['maxIntermediatePieces']-S,limits,True)
    T=len(target);return P+S+T,S+T


def subset(a,b):
    j=0
    for lo,hi,il,ih in a:
        while j<len(b) and (b[j][1]<lo or (b[j][1]==lo and (lo<hi or not b[j][3]))):j+=1
        if j==len(b):return False
        x,y,ix,iy=b[j]
        if x>lo or y<hi or (x==lo and il and not ix) or (y==hi and ih and not iy):return False
    return True


def relation_labels(a,b):
    same=a==b
    def before(x,y):return x[-1][1]<y[0][0] or (x[-1][1]==y[0][0] and not(x[-1][3] and y[0][2]))
    i=j=0;intersects=False
    while i<len(a) and j<len(b):
        lo=max(a[i][0],b[j][0]);hi=min(a[i][1],b[j][1])
        def includes(p,x):return p[0]<x<p[1] or (x==p[0] and p[2]) or (x==p[1] and p[3])
        if lo<hi or (lo==hi and includes(a[i],lo) and includes(b[j],lo)):intersects=True;break
        if a[i][1]<b[j][1]:i+=1
        elif b[j][1]<a[i][1]:j+=1
        else:i+=1;j+=1
    return dict(equal='equal' if same else 'notEqual',compare='equal' if same else 'before' if before(a,b) else 'after' if before(b,a) else 'indeterminate',relate='equal' if same else 'contains' if subset(b,a) else 'containedBy' if subset(a,b) else 'overlaps' if intersects else 'disjoint')


def relation_result(op,left,right,label):
    return dict(outcome='value',value=dict(category='symbol',value=label),metadata=dict(evaluation='exact-for-policy',clamping='not-applied',effectivePolicy=dict(profile=PROFILE),operandHistory=dict(left=history(left),right=history(right)),operandOrigin=dict(left=origin(left),right=origin(right))))
