"""Civil-clock artifact admission and exact fixture checks; not an operations SUT.

Only successful fixtures are evaluated here. Staged diagnostics remain fixed
assertions against a provider, not observations produced by this module.
"""
from fractions import Fraction
import re

from run_aeonic_arithmetic import require
from run_aeonic_rational_arithmetic import decimal_integer
from temporal_civil_date_checks import compact_bytes, decode_artifact, validate_pointer_text
from temporal_civil_datetime_checks import decimal_factors, decimal_text, decimal_properties, subset, relation_labels

PROFILE = 'aeonic.operations.temporal.civil-clock.v1'
CAPABILITIES = {
    'relations': ('Aeonic.Operations.Temporal.CivilClock.Relations', ('equal', 'compare', 'relate')),
    'arithmetic': ('Aeonic.Operations.Temporal.CivilClock.Arithmetic', ('shiftClock', 'step', 'materialize')),
}
LIMITS = dict(maxRequestBytes=65536, maxRequestDepth=32, maxTemporalCharacters=1024,
              maxInputPieces=512, maxIntermediatePieces=4096, maxOutputPieces=512,
              maxWork=16384, maxFractionDigits=256, maxRelativeDayDigits=256,
              maxCountCharacters=32, maxNumericCharacters=4096, maxCoefficientDigits=1024,
              maxExponentMagnitude=1000000, maxWorkspaceDigits=4096,
              maxOutputCharacters=1024, maxResultBytes=131072)
COORD = re.compile(r'([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?')
AUTH = re.compile(r'([0-9]{2}):(?:([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?)?')
INTEGER = re.compile(r'0|-?[1-9][0-9]*')
WIDTH = dict(hour=3600, minute=60, second=1)


def history(bundle):
    return bundle.get('history', 'none-declared')


def origin(bundle):
    if 'originClockForm' in bundle:
        return bundle['originClockForm']
    if bundle['temporal']['category'] != 'civilClock':
        return 'undeclared'
    text = bundle['temporal']['value']
    return 'hour' if text.endswith(':') else 'minute' if text.count(':') == 1 else 'second'


def clock_value(text, limits, generated=False, authored=False):
    require(isinstance(text, str), 'Clock must be text')
    maximum = (limits['maxOutputCharacters'] if authored else 9 + limits['maxFractionDigits']) if generated else limits['maxTemporalCharacters']
    require(len(text) <= maximum, 'Clock exceeds text allowance')
    m = (AUTH if authored else COORD).fullmatch(text)
    require(m is not None, 'Invalid ordinary clock text')
    hh, mm, ss, fraction = m.groups(); fraction = fraction or ''
    require(len(fraction) <= limits['maxFractionDigits'], 'Fraction exceeds allowance')
    require(authored or not fraction or fraction[-1] != '0', 'Noncanonical derived fraction')
    require(int(hh) < 24 and (mm is None or int(mm) < 60) and (ss is None or int(ss) < 60), 'Invalid clock fields')
    x = Fraction(int(hh)*3600 + (int(mm)*60 if mm is not None else 0) + (int(ss) if ss is not None else 0))
    if fraction:
        x += Fraction(decimal_integer(fraction), 10**len(fraction))
    return x, 3600 if mm is None else 60 if ss is None else 0


def coordinate(pair, limits=LIMITS, generated=False):
    require(isinstance(pair, dict) and set(pair) == {'day', 'time'}, 'Closed coordinate required')
    day = pair['day']; require(isinstance(day, str), 'Day must be text')
    require(len(day[1:] if day.startswith('-') else day) <= limits['maxRelativeDayDigits'], 'Day exceeds digit allowance')
    require(INTEGER.fullmatch(day) is not None, 'Noncanonical relative day')
    # No conversion or decimal expansion before the supplied field guards.
    x, _ = clock_value(pair['time'], limits, generated)
    return decimal_integer(day)*86400 + x


def format_coordinate(x):
    day = x // 86400; clock = x - day*86400
    whole = clock.numerator // clock.denominator
    text = '%02d:%02d:%02d' % (whole//3600, whole//60%60, whole%60)
    fraction = clock-whole
    if fraction:
        twos, fives = decimal_factors(fraction.denominator); scale = max(twos, fives)
        digits = decimal_text(fraction.numerator * 2**(scale-twos) * 5**(scale-fives)).zfill(scale).rstrip('0')
        text += '.' + digits
    return dict(day=decimal_text(day), time=text)


def coverage(bundle, maximum, limits=LIMITS, generated=False):
    td = bundle['temporal']
    if td['category'] == 'civilClock':
        x, width = clock_value(td['value'], limits, generated, authored=True)
        require(limits['maxRelativeDayDigits'] >= 1 and maximum >= 1, 'Implicit clock day/piece exceeds allowance')
        return [(x, x+width, True, width == 0)]
    require(td['category'] == 'civilClockSet', 'Deferred temporal domain')
    raw = td['pieces']
    require(isinstance(raw, list) and 0 < len(raw) <= maximum, 'Set exceeds piece allowance')
    spans = []
    for piece in raw:
        if piece['kind'] == 'point':
            at = coordinate(piece['at'], limits, generated); span = (at, at, True, True)
        else:
            lo = coordinate(piece['start'], limits, generated); hi = coordinate(piece['end'], limits, generated)
            require(type(piece['includeStart']) is bool and type(piece['includeEnd']) is bool, 'Boolean endpoint flags required')
            require(lo < hi, 'Nonpositive interval width')
            span = (lo, hi, piece['includeStart'], piece['includeEnd'])
        if spans:
            previous = spans[-1]
            require(previous[1] < span[0] or (previous[1] == span[0] and not previous[3] and not span[2]), 'Noncanonical set order, overlap or mergeable boundary')
        spans.append(span)
    return spans


def effective(logical):
    data = logical['input']; policy = data.get('policy', {})
    return dict(policy, profile=policy.get('profile', data.get('context', {}).get('profile')))


def dimensions(bundle):
    """Text-derived D,p after coverage admission; include excluded endpoints."""
    td = bundle['temporal']
    if td['category'] == 'civilClock':
        text = td['value']; return 1, len(text.split('.')[1].rstrip('0')) if '.' in text else 0
    coords = [p['at'] for p in td['pieces'] if p['kind'] == 'point']
    coords += [p[key] for p in td['pieces'] if p['kind'] == 'interval' for key in ('start', 'end')]
    return (max(len(c['day'].lstrip('-')) for c in coords),
            max(len(c['time'].split('.')[1]) if '.' in c['time'] else 0 for c in coords))


def workspace(logical, limits=LIMITS):
    data = logical['input']; D, p = dimensions(data['value'])
    if logical['operation'] == 'shiftClock':
        c, e = decimal_properties(data['amount'], limits)
        if c == '0': return 0, p
        q = max(p, max(0, -e)); A = len(c.lstrip('-')) + e + q
        W = max(D + 5 + q, A) + 1
    elif logical['operation'] == 'step':
        count = data['policy']['count']
        require(len(count) <= limits['maxCountCharacters'], 'Count exceeds allowance')
        require(INTEGER.fullmatch(count) is not None, 'Noncanonical count')
        if count == '0': return 0, p
        q = p; W = max(D + 5 + q, len(count.lstrip('-')) + len(str(WIDTH[data['policy']['clockForm']])) + q) + 1
    else: return 0, p
    require(W <= limits['maxWorkspaceDigits'], 'Clock workspace exceeds allowance')
    require(q <= limits['maxFractionDigits'], 'Generated fraction exceeds allowance')
    return W, q


def template(logical, spans):
    cf = logical['input']['policy']['clockForm']; x = spans[0][0]
    if cf == 'second': return [(x, x, True, True)]
    u = WIDTH[cf]; lo = (x // u)*u
    return [(lo, lo+u, True, False)]


def positive_cost(logical, spans, limits=LIMITS):
    op = logical['operation']; P = len(spans[0])
    if op in CAPABILITIES['relations'][1]: return sum(map(len, spans)), 0
    if op == 'shiftClock': workspace(logical, limits); return P, P
    require(P+1 <= limits['maxWork'] and 1 <= limits['maxIntermediatePieces'], 'Source matching exceeds allowance')
    source = template(logical, spans[0]); require(source == spans[0], 'Successful fixture does not match complete form')
    if op == 'materialize':
        require(source[0][0] // 86400 == 0, 'Materialization would discard relative day')
        return P+1, 1
    require(P+2 <= limits['maxWork'] and 2 <= limits['maxIntermediatePieces'], 'Target matching exceeds allowance')
    workspace(logical, limits)
    return P+2, 2


def expected_spans(logical, source, limits=LIMITS):
    """Check admitted positive arithmetic vectors by exact translation, not staged API."""
    op = logical['operation']
    if op == 'materialize': return source
    if op == 'step':
        count = logical['input']['policy']['count']
        delta = decimal_integer(count)*WIDTH[logical['input']['policy']['clockForm']]
    else:
        c,e = decimal_properties(logical['input']['amount'], limits)
        delta = Fraction(0) if c == '0' else Fraction(decimal_integer(c))* (10**e if e >= 0 else Fraction(1, 10**(-e)))
    return [(a+delta, b+delta, il, ih) for a,b,il,ih in source]


def relation_result(op, left, right, label):
    return dict(outcome='value', value=dict(category='symbol', value=label),
        metadata=dict(evaluation='exact-for-policy', effectivePolicy=dict(profile=PROFILE),
                      operandHistory=dict(left=history(left), right=history(right)),
                      operandOrigin=dict(left=origin(left), right=origin(right))))
