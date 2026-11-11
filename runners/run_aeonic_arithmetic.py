#!/usr/bin/env python3
"""Execute the mutable exact-arithmetic target; Python 3.9+, jsonschema 4.18+.

Uses cts.protocol.v1, pinned local artifacts and shell-free SUT commands.
Passing this working target never establishes frozen-snapshot conformance.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import shlex
import subprocess
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "aeonic.operations.arithmetic.exact.v1"
NONE, MARKED = "none-declared", "approximation-declared"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def decode(text):
    def constant(value):
        raise ValueError("Non-JSON constant: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if type(a) in {int, float} and type(b) in {int, float}:
        return a == b
    return type(a) is type(b) and a == b


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


class Runner:
    def __init__(self, args):
        self.args = args
        self.artifacts = {}
        self.executions = self.assertions = 0
        self.manifest_path = args.manifest.resolve()
        self.manifest = self.read(self.manifest_path)
        meta = self.manifest["meta"]
        require(meta["lane"] == "aeonic-arithmetic" and meta["conformance"] == {"surface": "working-next", "stable": False},
                "Expected mutable arithmetic target")
        root = self.manifest_path.parent

        def pinned(base, relative, sha):
            path = (base / relative).resolve()
            require(base.resolve() in path.parents, "Artifact must be inside its owning repository")
            content = path.read_bytes()
            require(hashlib.sha256(content).hexdigest() == sha, "Artifact digest mismatch: " + relative)
            self.artifacts[path] = sha
            return decode(content.decode("utf-8"))

        schema = pinned(args.specs_root, meta["specification_schema"], meta["specification_schema_sha256"])
        binding = pinned(root, meta["binding_schema"], meta["binding_schema_sha256"])
        source = (args.specs_root / meta["specification_source"]).resolve()
        require(args.specs_root.resolve() in source.parents and digest(source) == meta["specification_source_sha256"], "Source digest mismatch")
        self.artifacts[source] = meta["specification_source_sha256"]
        Draft202012Validator.check_schema(schema)
        Draft202012Validator.check_schema(binding)
        registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
        self.result_schema = Draft202012Validator({"$ref": schema["$id"] + "#/$defs/result"}, registry=registry)
        self.binding_schema = Draft202012Validator(binding)
        self.resource_limits = meta["resource_limits"]
        limit_names = set(binding["properties"]["policy"]["properties"]["resourceLimits"]["properties"])
        require(isinstance(self.resource_limits, dict) and set(self.resource_limits) == limit_names,
                "Target must explicitly select every harness resource limit")
        self.binding_schema.validate(dict(lane="aeonic-arithmetic", case_id="target-limits", fixture={"request": {}},
                                          policy={"resourceLimits": self.resource_limits}))
        self.tests = []
        seen = set()
        for suite in self.manifest["suites"]:
            data = pinned(root, suite["file"], suite["content_sha256"])
            require(data["id"] == suite["id"], "Suite identity mismatch")
            for test in data["tests"]:
                require(test["id"] not in seen, "Duplicate case ID")
                seen.add(test["id"]); self.tests.append(test)
        require(bool(self.tests), "An empty target cannot pass conformance")

    def read(self, path):
        content = path.read_bytes()
        self.artifacts[path] = hashlib.sha256(content).hexdigest()
        return decode(content.decode("utf-8"))

    def invoke(self, case_id, fixture, policy):
        envelope = dict(lane="aeonic-arithmetic", case_id=case_id, fixture=fixture, policy=policy)
        self.binding_schema.validate(envelope)
        envelope["policy"] = {"resourceLimits": dict(self.resource_limits, **policy.get("resourceLimits", {}))}
        result = subprocess.run(shlex.split(self.args.sut), input=json.dumps(envelope, ensure_ascii=True),
                                text=True, capture_output=True, cwd=self.args.cwd, timeout=self.args.timeout)
        self.executions += 1
        require(result.returncode == 0, "SUT harness failure: " + result.stderr[:300])
        output = decode(result.stdout)
        require(isinstance(output, dict), "Protocol output must be an object")
        actual = output.get("result")
        self.result_schema.validate(actual)
        ok = actual["outcome"] == "value"
        require(type(output.get("ok")) is bool and output["ok"] == ok, "Protocol ok mismatch")
        require(output.get("warnings") == [], "Unexpected warnings")
        errors = output.get("errors")
        if ok:
            require(errors == [], "Unexpected errors")
        else:
            require(isinstance(errors, list) and len(errors) == 1 and isinstance(errors[0], dict), "One error is required")
            for key, value in dict(code=actual["reason"], path=None, span=None, phase=None).items():
                require(key in errors[0] and equal(errors[0][key], value), "Protocol diagnostic mismatch")
        return actual

    def operation(self, test):
        actual = self.invoke(test["id"], test["fixture"], test.get("policy", {}))
        if actual["outcome"] == "diagnostic":
            actual = {k: v for k, v in actual.items() if k != "message"}
        require(equal(actual, test["expected"]), "Result mismatch: " + json.dumps(actual)[:300])
        return actual

    def chain(self, test):
        outputs = []
        links = set()
        require(bool(test["steps"]), "A chain cannot be empty")
        for link in test["links"]:
            require(set(link) == {"fromStep", "toStep", "input"}, "Malformed chain link")
            a, b = link["fromStep"], link["toStep"]
            require(type(a) is int and type(b) is int and 0 <= a < b < len(test["steps"]), "Chain link must point backwards within the chain")
            require(link["input"] in {"left", "right", "value"} and link["input"] in test["steps"][b]["request"]["input"], "Invalid chain input")
            target = (b, link["input"])
            require(target not in links, "Duplicate chain target")
            links.add(target)
        for i, step in enumerate(test["steps"]):
            logical = copy.deepcopy(step["request"])
            for link in test["links"]:
                if link["toStep"] == i:
                    require(0 <= link["fromStep"] < i, "Chain link must point backwards")
                    require(link["input"] in {"left", "right", "value"}, "Invalid chain input")
                    logical["input"][link["input"]] = copy.deepcopy(outputs[link["fromStep"]]["value"])
            outputs.append(self.operation(dict(id=test["id"] + "/" + str(i), fixture={"request": logical},
                                               policy=step.get("policy", {}), expected=step["expected"])))

    def law_value(self, op, a, b):
        result = self.invoke("law-" + str(self.executions), {"request": request(op, a, b)}, {})
        history = MARKED if MARKED in {a.get("history", NONE), b.get("history", NONE)} else NONE
        require(result["outcome"] == "value", "Law input must produce a value")
        require(result["value"]["number"]["category"] == "exactNumber", "Law result must remain derived")
        require(result["value"]["history"] == history, "History union law")
        require(result["metadata"] == {"evaluation": "exact-for-operands", "effectivePolicy": {"profile": PROFILE}}, "Law metadata mismatch")
        self.assertions += 1
        return result["value"]

    def assertion(self, condition, law):
        require(condition, "Arithmetic law: " + law)
        self.assertions += 1

    def laws(self, test):
        values = test["values"]
        require(len(values) >= 3, "Law group needs at least three values")
        for a, b in itertools.product(values, repeat=2):
            for op in ["add", "multiply"]:
                self.assertion(equal(self.law_value(op, a, b), self.law_value(op, b, a)), op + " commutativity")
            left = self.law_value("subtract", a, b)
            right = self.law_value("subtract", b, a)
            inverse = copy.deepcopy(right)
            c = inverse["number"]["coefficient"]
            inverse["number"]["coefficient"] = c if c == "0" else c[1:] if c.startswith("-") else "-" + c
            self.assertion(equal(left, inverse), "subtraction reversal")
        for a in values:
            self.assertion(equal(self.law_value("add", a, number("0")), self.law_value("multiply", a, number("1"))), "identities")
        for a, b, c in [values[i:i + 3] for i in range(len(values) - 2)]:
            left = self.law_value("multiply", a, self.law_value("add", b, c))
            right = self.law_value("add", self.law_value("multiply", a, b), self.law_value("multiply", a, c))
            self.assertion(equal(left, right), "distributivity")

    def run(self):
        failures = []; counts = dict(operation_cases=0, chains=0, resource_boundaries=0, law_groups=0)
        for test in self.tests:
            try:
                kind = test.get("kind", "operation")
                if kind == "boundary":
                    self.operation(boundary(test["id"])); counts["resource_boundaries"] += 1
                elif kind == "chain":
                    self.chain(test); counts["chains"] += 1
                elif kind == "laws":
                    self.laws(test); counts["law_groups"] += 1
                elif kind == "operation":
                    self.operation(test); counts["operation_cases"] += 1
                else:
                    raise ValueError("Unknown test kind")
            except Exception as error:
                failures.append(dict(id=test["id"], failure=str(error)[:1500]))
        for path, sha in self.artifacts.items():
            if not path.exists() or digest(path) != sha:
                failures.append(dict(id="artifact-integrity", failure="Artifact changed during execution: " + path.name))
        return dict(status="failed" if failures else "passed", target=self.manifest["meta"]["snapshot_id"],
                    target_status="mutable-working", stable_conformance_claim=False,
                    manifest_sha256=self.artifacts[self.manifest_path],
                    specification_source_sha256=self.manifest["meta"]["specification_source_sha256"],
                    specification_schema_sha256=self.manifest["meta"]["specification_schema_sha256"],
                    resource_limits=self.resource_limits,
                    sut=self.args.sut, cwd=str(self.args.cwd.resolve()), **counts,
                    sut_executions=self.executions, arithmetic_assertions=self.assertions, failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "cts/aeonic-arithmetic/v1/aeonic-arithmetic-cts.v1.next.json")
    parser.add_argument("--specs-root", type=Path, default=ROOT.parent / "aeonite-specs")
    parser.add_argument("--sut", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    require(0 < args.timeout < float("inf"), "Timeout must be positive and finite")
    report = Runner(args).run()
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("CTS harness failure: " + str(error), file=sys.stderr)
        sys.exit(2)
