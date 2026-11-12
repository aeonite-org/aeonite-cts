"""Immutable arithmetic boundary recipe reference; verified, not imported by the runner."""
import json
PROFILE = 'aeonic.operations.arithmetic.exact.v1'
NONE, MARKED = ('none-declared', 'approximation-declared')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def number(value, history=None):
    bundle = {"number": {"category": "finiteNumber", "value": value}}
    if history is not None:
        bundle["history"] = history
    return bundle

def exact(c, e, history=NONE):
    return {"number": {"category": "exactNumber", "coefficient": c, "exponent": e}, "history": history}

def request(operation, a, b=None, **settings):
    data = {"value": a} if operation == "materialize" else {"left": a, "right": b}
    data.update(settings)
    return {"operation": operation, "input": data}

def success(bundle, **policy):
    return {"outcome": "value", "value": bundle,
            "metadata": {"evaluation": "exact-for-operands", "effectivePolicy": dict(profile=PROFILE, **policy)}}

def diagnostic(reason, stage, path=None):
    return {"outcome": "diagnostic", "reason": reason, "context": {"stage": stage, "path": path}}

def boundary(name):
    """Reviewed generators; expected results use closed-form identities."""
    require(name in {"numeric-at-limit", "numeric-one-over", "coefficient-at-limit", "coefficient-one-over",
                     "workspace-at-limit", "workspace-one-over", "output-at-limit", "output-one-over",
                     "exponent-at-limit", "exponent-one-over", "normalized-exponent-one-over",
                     "request-bytes-at-limit", "request-bytes-one-over", "depth-at-limit", "depth-one-over",
                     "long-zero-exponent"}, "Unknown boundary recipe: " + name)
    policy = {}
    if name.startswith("numeric-"):
        policy = {"resourceLimits": {"maxNumericCharacters": 65536}}
        n = 65536 + int(name.endswith("one-over"))
        logical = request("add", number("1" * n), number("0"))
        expected = (success(exact("1" * n, "0")) if n == 65536 else
                    diagnostic("resource_limit", 4, "/input/left/number/value"))
    elif name.startswith("coefficient-"):
        n = 65536 + int(name.endswith("one-over"))
        logical = request("add", exact("1" * n, "0"), number("0"))
        policy = {"resourceLimits": {"maxNumericCharacters": 65538, "maxCoefficientDigits": 65536}}
        expected = (success(exact("1" * n, "0")) if n == 65536 else
                    diagnostic("resource_limit", 4, "/input/left/number/coefficient"))
    elif name.startswith("workspace-"):
        n = 65536
        logical = request("multiply", number("9" * n), number("9" * n))
        policy = {"resourceLimits": {"maxCoefficientDigits": 131072,
                                    "maxWorkspaceDigits": 131072 if name.endswith("at-limit") else 131071}}
        expected = (success(exact("9" * (n - 1) + "8" + "0" * (n - 1) + "1", "0"))
                    if name.endswith("at-limit") else diagnostic("resource_limit", 6))
    elif name.startswith("output-"):
        policy = {"resourceLimits": {"maxOutputCharacters": 65536}}
        e = 65535 + int(name.endswith("one-over"))
        logical = request("materialize", exact("1", str(e)), policy={"family": "integer"})
        expected = (success(number("1" + "0" * e, NONE), family="integer", zeroSign="positive")
                    if e == 65535 else diagnostic("resource_limit", 7))
    elif name in {"exponent-at-limit", "exponent-one-over"}:
        policy = {"resourceLimits": {"maxExponentMagnitude": 1000000}}
        e = 1000000 + int(name.endswith("one-over"))
        logical = request("multiply", number("1e" + str(e)), number("1"))
        expected = (success(exact("1", str(e))) if e == 1000000 else
                    diagnostic("resource_limit", 4, "/input/left/number/value"))
    elif name == "normalized-exponent-one-over":
        policy = {"resourceLimits": {"maxExponentMagnitude": 1000000}}
        logical = request("multiply", number("5e1000000"), number("2"))
        expected = diagnostic("resource_limit", 6)
    elif name.startswith("request-bytes-"):
        text = json.dumps(request("add", number("1"), number("1")), separators=(",", ":"))
        count = 4194304 + int(name.endswith("one-over"))
        expected = success(exact("2", "0")) if count == 4194304 else diagnostic("resource_limit", 1)
        return {"id": name, "fixture": {"requestText": text + " " * (count - len(text))},
                "policy": {"resourceLimits": {"maxRequestBytes": 4194304}}, "expected": expected}
    elif name.startswith("depth-"):
        policy = {"resourceLimits": {"maxRequestDepth": 32}}
        payload = 0
        for _ in range(28 + int(name.endswith("one-over"))):
            payload = [payload]
        logical = request("add", {"number": {"category": "container", "payload": payload}}, number("1"))
        expected = (diagnostic("resource_limit", 1) if name.endswith("one-over") else
                    diagnostic("unsupported_domain", 5, "/input/left/number/category"))
    elif name == "long-zero-exponent":
        policy = {"resourceLimits": {"maxNumericCharacters": 65536}}
        logical = request("add", number("1e" + "0" * 65534), number("0"))
        expected = success(exact("1", "0"))
    else:
        raise ValueError("Unknown boundary recipe: " + name)
    return {"id": name, "fixture": {"request": logical}, "policy": policy, "expected": expected}
