"""Bounded positive-fixture oracle for anchoring, not a staged operations SUT.

No function here returns logical diagnostics. Negative expectations must be
asserted against a separately supplied provider by the lane runner.
"""
from calendar import monthrange
from datetime import date
import re

from run_aeonic_arithmetic import require
from temporal_civil_date_checks import compact_bytes, decode_artifact, full_date, validate_pointer_text

PROFILE = 'aeonic.operations.temporal.civil-anchor.v1'
CAPABILITY = 'Aeonic.Operations.Temporal.CivilAnchor'
LIMITS = dict(maxRequestBytes=65536, maxRequestDepth=32, maxTemporalCharacters=1024,
              maxInputRanges=128, maxInputPieces=512, maxRelativeDayDigits=256,
              maxFractionDigits=256, maxWork=16384, maxIntermediatePieces=4096,
              maxOutputPieces=512, maxResultBytes=131072)
UPPER = date(9999, 12, 31).toordinal()  # Exclusive, zero-based ordinal boundary.
INTEGER = re.compile(r'0|-?[1-9][0-9]*')
AUTH = re.compile(r'([0-9]{2}):(?:([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?)?')
FULL = re.compile(r'([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?')


def clock(text, limits, authored=False):
    require(isinstance(text, str), 'Clock must be text')
    require(len(text) <= limits['maxTemporalCharacters'], 'Clock text allowance')
    match = (AUTH if authored else FULL).fullmatch(text)
    require(match is not None, 'Invalid clock grammar')
    h, m, s, fraction = match.groups(); fraction = fraction or ''
    require(len(fraction) <= limits['maxFractionDigits'], 'Fraction allowance')
    require(authored or not fraction or fraction[-1] != '0', 'Noncanonical fraction')
    require(int(h) < 24 and int(m or 0) < 60 and int(s or 0) < 60, 'Invalid clock fields')
    form = 'hour' if m is None else 'minute' if s is None else 'second'
    return int(h)*3600 + int(m or 0)*60 + int(s or 0), fraction.rstrip('0'), form


def coordinate(value, limits):
    day = value['day']
    require(isinstance(day, str), 'Day must be text')
    require(len(day[1:] if day.startswith('-') else day) <= limits['maxRelativeDayDigits'], 'Day digit allowance')
    require(INTEGER.fullmatch(day) is not None, 'Noncanonical day')
    second, fraction, _ = clock(value['time'], limits)
    return day, second, fraction


def signed_compare(a, b):
    """Compare canonical integer strings without conversion or decimal padding."""
    negative_a, negative_b = a.startswith('-'), b.startswith('-')
    if negative_a != negative_b:
        return -1 if negative_a else 1
    x, y = a.lstrip('-'), b.lstrip('-')
    comparison = (len(x) > len(y)) - (len(x) < len(y)) or (x > y) - (x < y)
    return -comparison if negative_a else comparison


def compare(a, b):
    c = signed_compare(a[0], b[0]) or (a[1] > b[1]) - (a[1] < b[1])
    if c:
        return c
    # Fractions are trailing-zero-free; lexical order is exact, with the shorter
    # common prefix implicitly padded by zeros. No common grid is constructed.
    return (a[2] > b[2]) - (a[2] < b[2])


def date_text(text, limits, reduced=False):
    require(isinstance(text, str) and len(text) <= limits['maxTemporalCharacters'], 'Date text allowance')
    if reduced and re.fullmatch(r'[0-9]{4}-', text):
        y = int(text[:4]); return date(y, 1, 1), date(y, 12, 31), 'year'
    if reduced and re.fullmatch(r'[0-9]{4}-[0-9]{2}', text):
        y, m = int(text[:4]), int(text[5:]); return date(y, m, 1), date(y, m, monthrange(y, m)[1]), 'month'
    d = full_date(text)
    return d, d, 'day'


def dates(bundle, limits):
    td = bundle['temporal']
    if td['category'] == 'civilDate':
        require(limits['maxInputRanges'] >= 1, 'Implicit input range allowance')
        lo, hi, origin = date_text(td['value'], limits, True); spans = [(lo, hi)]
    else:
        require(td['category'] == 'civilDateSet', 'Positive anchor must be a supported date')
        raw = td['ranges']
        require(isinstance(raw, list) and 0 < len(raw) <= limits['maxInputRanges'], 'Input range allowance')
        spans = []; origin = 'undeclared'
        for p in raw:
            lo = date_text(p['start'], limits)[0]; hi = date_text(p['end'], limits)[0]
            require(lo <= hi, 'Inverted range')
            require(not spans or spans[-1][1].toordinal()+1 < lo.toordinal(), 'Noncanonical ranges')
            spans.append((lo, hi))
    return spans, bundle.get('originGranularity', origin)


def pieces(bundle, limits):
    td = bundle['temporal']
    if td['category'] == 'civilClock':
        sec, frac, origin = clock(td['value'], limits, True)
        require(limits['maxRelativeDayDigits'] >= 1 and limits['maxInputPieces'] >= 1, 'Implicit clock capacity')
        lo = ('0', sec, frac); width = dict(hour=3600, minute=60, second=0)[origin]
        hi = (str((sec+width)//86400), (sec+width)%86400, '') if width else lo
        result = [(lo, hi, True, not width)]
    else:
        require(td['category'] == 'civilClockSet', 'Positive clock must be a supported clock')
        raw = td['pieces']
        require(isinstance(raw, list) and 0 < len(raw) <= limits['maxInputPieces'], 'Input piece allowance')
        result = []; origin = 'undeclared'
        for p in raw:
            if p['kind'] == 'point':
                at = coordinate(p['at'], limits); span = (at, at, True, True)
            else:
                a, b = coordinate(p['start'], limits), coordinate(p['end'], limits)
                require(compare(a, b) < 0, 'Nonpositive interval')
                require(type(p['includeStart']) is bool and type(p['includeEnd']) is bool, 'Boolean flags required')
                span = a, b, p['includeStart'], p['includeEnd']
            if result:
                c = compare(result[-1][1], span[0])
                require(c < 0 or c == 0 and not (result[-1][3] or span[2]), 'Noncanonical pieces')
            result.append(span)
    return result, bundle.get('originClockForm', origin)


def target_ordinal(value, anchor, excluded_end=False):
    """Reject huge relative days before integer/calendar conversion or rendering."""
    relative, sec, fraction = value; ordinal = anchor.toordinal()-1
    require(signed_compare(relative, str(-ordinal)) >= 0 and
            signed_compare(relative, str(UPPER-ordinal)) <= 0, 'Image outside date-time domain')
    target = ordinal + int(relative)  # Now bounded to seven decimal digits.
    if target == UPPER and sec == 0 and not fraction and excluded_end:
        return target
    require(target < UPPER, 'Image outside date-time domain')
    return target


def translated(value, anchor, excluded_end=False):
    target = target_ordinal(value, anchor, excluded_end)
    if target == UPPER:
        return dict(boundary='endOfDomain')
    _, sec, fraction = value
    d = date.fromordinal(target+1)
    return ('%04d-%02d-%02dT%02d:%02d:%02d' % (d.year,d.month,d.day,sec//3600,sec//60%60,sec%60)
            + ('.'+fraction if fraction else ''))


def expected_positive(logical, limits):
    """Check successful-fixture admission and compute its exact image only."""
    compact_bytes(logical, limits['maxRequestBytes'])
    pending = [(logical, 1)]
    while pending:
        node, depth = pending.pop()
        if isinstance(node, (dict, list)):
            require(depth <= limits['maxRequestDepth'], 'Input depth allowance')
            children = node.values() if isinstance(node, dict) else node
            pending.extend((v, depth+1) for v in children if isinstance(v, (dict, list)))
    data = logical['input']
    selected = data.get('policy', {}).get('profile', data.get('context', {}).get('profile'))
    require(selected == PROFILE, 'Explicit anchoring profile required')
    a, c = data['anchor'], data['clock']
    ranges, date_origin = dates(a, limits); spans, clock_origin = pieces(c, limits)
    require(len(ranges)+len(spans) <= limits['maxWork'], 'Work allowance')
    require(len(spans) <= limits['maxIntermediatePieces'], 'Intermediate allowance')
    require(len(ranges) == 1 and ranges[0][0] == ranges[0][1], 'Single-day eligibility')
    # Domain outranks output count, while output count guards calendar/text
    # construction. Do not serialize or render an oversized successful image.
    for lo, hi, il, ih in spans:
        target_ordinal(lo, ranges[0][0])
        target_ordinal(hi, ranges[0][0], compare(lo, hi) != 0 and not ih)
    require(len(spans) <= limits['maxOutputPieces'], 'Output allowance')
    rendered = []
    for lo, hi, il, ih in spans:
        if compare(lo, hi) == 0:
            rendered.append(dict(kind='point', at=translated(lo, ranges[0][0])))
        else:
            rendered.append(dict(kind='interval', start=translated(lo, ranges[0][0]),
                                 end=translated(hi, ranges[0][0], not ih), includeStart=il, includeEnd=ih))
    result = dict(outcome='value', value=dict(temporal=dict(category='civilDateTimeSet', pieces=rendered),
                  originDateGranularity=date_origin, originClockForm=clock_origin,
                  history=dict(clamping=a.get('history', 'none-declared'), approximation=c.get('history', 'none-declared'))),
                  metadata=dict(evaluation='exact-for-policy', clamping='not-applied', effectivePolicy=dict(profile=PROFILE)))
    compact_bytes(result, limits['maxResultBytes'])
    return result
