"""Shared civil-date CTS checks, not a temporal operations implementation.

Only intrinsic date/canonical-set checks, bounded envelope measurement and the
small relation-law oracle live here. No calendar shift/step engine is supplied.
"""
from calendar import monthrange
from datetime import date
import json

from run_aeonic_arithmetic import RawNumber, numeric_token, pairs, require

PROFILE = 'aeonic.operations.temporal.civil-date.v1'
NONE, MARKED = 'none-declared', 'clamping-declared'
CAPABILITIES = {
    'relations': ('Aeonic.Operations.Temporal.CivilDate.Relations', ('equal', 'compare', 'relate')),
    'calendar': ('Aeonic.Operations.Temporal.CivilDate.Calendar', ('shift', 'step', 'materialize')),
}
LIMITS = dict(maxRequestBytes=16384, maxRequestDepth=32, maxInputRanges=128,
              maxCountCharacters=32, maxOutputRanges=128, maxCalendarWork=4096,
              maxOutputCharacters=10, maxResultBytes=16384)


def decode_artifact(text):
    """Keep every logical request's numeric spelling, including integer -0.

    Other protocol/manifest numbers use the existing exact trusted-number
    decoder. Logical request subtrees occur only in fixture.request or chain
    step.request, not in arbitrary extension objects named 'request'.
    """
    def constant(value):
        raise ValueError('Non-JSON constant: ' + value)
    value = json.loads(text, object_pairs_hook=pairs, parse_int=RawNumber,
                       parse_float=RawNumber, parse_constant=constant)
    pending = [(value, ())]
    while pending:
        node, path = pending.pop()
        if isinstance(node, dict):
            for key in node:
                logical = key == 'request' and (path[-1:] == ('fixture',) or
                          (len(path) >= 2 and path[-2] == 'steps' and isinstance(path[-1], int)))
                if logical:
                    continue
                child = node[key]
                if isinstance(child, RawNumber):
                    node[key] = numeric_token(child.text)
                elif isinstance(child, (dict, list)):
                    pending.append((child, path + (key,)))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                if isinstance(child, RawNumber):
                    node[i] = numeric_token(child.text)
                elif isinstance(child, (dict, list)):
                    pending.append((child, path + (i,)))
    return value


def compact_bytes(value, allowance):
    """Measure only through allowance; no complete reserialization allocation.

    Inputs here are decoded JSON data, not native getters/proxies. Individual
    string lengths are checked before bounded escaping/UTF-8 encoding.
    """
    total = 0
    pending = [('value', value)]

    def add(text):
        nonlocal total
        require(len(text) <= allowance - total, 'Successful envelope exceeds selected byte allowance')
        total += len(text.encode('utf-8'))
        require(total <= allowance, 'Successful envelope exceeds selected byte allowance')

    def string(text):
        require(len(text) <= allowance - total, 'Successful envelope exceeds selected byte allowance')
        add(json.dumps(text, ensure_ascii=False, allow_nan=False))

    while pending:
        kind, node = pending.pop()
        if kind == 'text':
            add(node)
        elif kind == 'object':
            iterator, first = node
            try:
                key, child = next(iterator)
            except StopIteration:
                add('}')
                continue
            if not first:
                add(',')
            string(key); add(':')
            pending.append(('object', (iterator, False)))
            pending.append(('value', child))
        elif kind == 'array':
            iterator, first = node
            try:
                child = next(iterator)
            except StopIteration:
                add(']')
                continue
            if not first:
                add(',')
            pending.append(('array', (iterator, False)))
            pending.append(('value', child))
        elif isinstance(node, dict):
            add('{'); pending.append(('object', (iter(node.items()), True)))
        elif isinstance(node, list):
            add('['); pending.append(('array', (iter(node), True)))
        elif isinstance(node, str):
            string(node)
        elif isinstance(node, RawNumber):
            add(node.text)
        else:
            add(json.dumps(node, ensure_ascii=False, allow_nan=False))
    return total


def full_date(text):
    require(isinstance(text, str) and len(text) == 10 and text[4] == text[7] == '-',
            'Expected complete ISO civil date')
    require(text.replace('-', '').isascii() and text.replace('-', '').isdigit(), 'Invalid civil date digits')
    result = date.fromisoformat(text)
    require(result.isoformat() == text, 'Noncanonical civil date')
    return result


def coverage(bundle, maximum):
    descriptor = bundle['temporal']
    if descriptor['category'] == 'civilDate':
        require(maximum >= 1, 'Authored date exceeds selected input-range allowance')
        text = descriptor['value']
        if len(text) == 5 and text.endswith('-'):
            y = int(text[:4]); spans = [(date(y, 1, 1), date(y, 12, 31))]
        elif len(text) == 7:
            y, m = int(text[:4]), int(text[5:]); spans = [(date(y, m, 1), date(y, m, monthrange(y, m)[1]))]
        else:
            d = full_date(text); spans = [(d, d)]
    else:
        raw = descriptor['ranges']
        require(isinstance(raw, list) and 0 < len(raw) <= maximum, 'Date ranges exceed selected allowance')
        spans = [(full_date(item['start']), full_date(item['end'])) for item in raw]
    previous = None
    for a, b in spans:
        require(a <= b, 'Reversed date range')
        require(previous is None or a.toordinal() > previous.toordinal() + 1,
                'Date ranges must be sorted, disjoint and nonadjacent')
        previous = b
    return [(a.isoformat(), b.isoformat()) for a, b in spans]


def history(bundle):
    return bundle.get('history', NONE)


def origin(bundle):
    if 'originGranularity' in bundle:
        return bundle['originGranularity']
    descriptor = bundle['temporal']
    if descriptor['category'] != 'civilDate':
        return 'undeclared'
    return {5: 'year', 7: 'month', 10: 'day'}[len(descriptor['value'])]


def whole_period(spans, granularity):
    if len(spans) != 1:
        return False
    a, b = (full_date(text) for text in spans[0])
    if granularity == 'day':
        return a == b
    if granularity == 'month':
        return a.year == b.year and a.month == b.month and a.day == 1 and b.day == monthrange(b.year, b.month)[1]
    return a.year == b.year and a.month == a.day == 1 and b.month == 12 and b.day == 31


def positive_work(logical, spans):
    """Check the agreed positive-fixture preflight, without building an image."""
    op = logical['operation']; policy = logical['input'].get('policy', {})
    if op in CAPABILITIES['relations'][1]:
        return sum(len(part) for part in spans)
    source = spans[0]
    if op in {'step', 'materialize'}:
        require(whole_period(source, policy['granularity']), 'Successful fixture needs a complete selected period')
    if op == 'materialize':
        return 1
    unit = policy.get('unit', policy.get('granularity')); text = policy['count']
    bound = str({'day':3652058, 'month':119987, 'eom':119987, 'year':9998, 'eoy':9998}[unit])
    magnitude = text.lstrip('-')
    require((len(magnitude), magnitude) <= (len(bound), bound), 'Successful fixture has out-of-domain displacement')
    n = int(text)  # At most seven digits after the lexical bound; no process integer-string changes.
    first = full_date(source[0][0]); last = full_date(source[-1][1])
    if unit == 'day':
        require(first.toordinal() + n >= 1 and last.toordinal() + n <= date.max.toordinal(), 'Successful fixture leaves year domain')
    elif unit in {'month', 'eom'}:
        require((first.year - 1)*12 + first.month - 1 + n >= 0
                and (last.year - 1)*12 + last.month - 1 + n <= 119987, 'Successful fixture leaves year domain')
    else:
        require(first.year + n >= 1 and last.year + n <= 9999, 'Successful fixture leaves year domain')
    if op == 'step':
        return 1
    if n == 0 or unit == 'day':
        return len(source)
    if unit == 'eoy':
        return sum(int(b[:4]) - int(a[:4]) + 1 for a, b in source)
    return sum((int(b[:4]) - int(a[:4]))*12 + int(b[5:7]) - int(a[5:7]) + 1 for a, b in source)


def effective(logical):
    data = logical['input']; policy = data.get('policy', {})
    profile = policy.get('profile', data.get('context', {}).get('profile'))
    require(profile == PROFILE, 'Successful fixture needs the selected civil-date profile')
    return dict(profile=PROFILE, **{k: v for k, v in policy.items() if k != 'profile'})


def relation_labels(a, b):
    def subset(left, right):
        j = 0
        for first, last in left:
            while j < len(right) and right[j][1] < first:
                j += 1
            if j == len(right) or right[j][0] > first or right[j][1] < last:
                return False
        return True
    same = a == b
    chronology = 'equal' if same else 'before' if a[-1][1] < b[0][0] else 'after' if b[-1][1] < a[0][0] else 'indeterminate'
    i = j = 0; intersection = False
    while i < len(a) and j < len(b):
        if a[i][1] < b[j][0]:
            i += 1
        elif b[j][1] < a[i][0]:
            j += 1
        else:
            intersection = True; break
    relation = ('equal' if same else 'contains' if subset(b, a) else 'containedBy' if subset(a, b)
                else 'overlaps' if intersection else 'disjoint')
    return dict(equal='equal' if same else 'notEqual', compare=chronology, relate=relation)


def relation_result(operation, left, right, label):
    return dict(outcome='value', value=dict(category='symbol', value=label),
                metadata=dict(evaluation='exact-for-policy', clamping='not-applied',
                              effectivePolicy=dict(profile=PROFILE),
                              operandHistory=dict(left=history(left), right=history(right))))
