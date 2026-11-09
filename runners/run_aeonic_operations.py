#!/usr/bin/env python3
"""Run an exact Aeonic Operations comparison target through cts.protocol.v1.

Requires Python 3.9+ and jsonschema 4.18+. Each SUT invocation receives one
envelope and must exit zero for an operation diagnostic. Command strings are
split with shlex and executed without a shell. No stable snapshot is released
by running this tool.
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
BASELINE = "aeonic.operations.comparison.baseline.v1"
CODEPOINT = "aeonic.operations.string.codepoint.v1"
DECLARED = "aeonic.operations.symbol.declared-order.v1"
CAPABILITIES = {
    "baseline": {"comparison-baseline"},
    "baseline-with-declared-order": {"comparison-baseline", "symbol-declared-order"},
}


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON member: " + repr(key))
        result[key] = value
    return result


def constant(value):
    raise ValueError("Non-JSON constant: " + value)


def decode(text):
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def read(path):
    return decode(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def operand(category, value):
    return {"category": category, "value": value}


def request(left=None, right=None):
    return {"operation": "compare", "input": {
        "left": left or operand("finiteNumber", "1"),
        "right": right or operand("finiteNumber", "2"),
    }}


def diagnostic(reason, stage, path):
    return {"outcome": "diagnostic", "reason": reason,
            "context": {"stage": stage, "path": path}}


def expected_value(symbol, logical):
    data = logical["input"]
    context, policy = data.get("context", {}), data.get("policy", {})
    strings = policy.get("strings", context.get("strings", {"profile": CODEPOINT}))
    selection = policy.get("symbols", context.get("symbols", {
        "mode": "string-profile", "profile": CODEPOINT}))
    symbols = copy.deepcopy(selection)
    if symbols["mode"] == "declared-order":
        declaration = symbols.pop("declaration")
        reference = declaration.get("reference")
        resolved = next(entry for entry in context["declarations"]
                        if entry["id"] == reference["id"] and
                        entry["version"] == reference["version"]) if reference else declaration
        symbols.update(profile=DECLARED, order=copy.deepcopy(resolved["order"]))
        if reference:
            symbols["reference"] = copy.deepcopy(reference)
    domain = data["left"]["category"]
    method = {"finiteNumber": "exact-numeric", "boolean": "boolean"}.get(
        domain, symbols["mode"] if domain == "symbol" else "string-profile")
    return {"outcome": "value", "value": operand("symbol", symbol), "metadata": {
        "effectivePolicy": {"profile": BASELINE, "domain": domain,
                            "comparison": method, "strings": strings, "symbols": symbols}}}


def materialize(recipe):
    """Build exact capacity inputs from named, reviewed recipes, not free text."""
    name = recipe["id"]
    logical = request()
    if name == "minimum_coefficient_capacity":
        logical = request(operand("finiteNumber", "1" + "0" * 65535),
                          operand("finiteNumber", "2" + "0" * 65535))
    elif name == "integer_exponent_equivalence_at_capacity":
        logical = request(operand("finiteNumber", "1" + "0" * 65535),
                          operand("finiteNumber", "1e65535"))
    elif name == "minimum_exponent_capacity":
        logical = request(operand("finiteNumber", "1e" + "9" * 65534),
                          operand("finiteNumber", "1e" + "9" * 65533 + "8"))
    elif name == "configured_numeric_limit_exceeded":
        logical = request(operand("finiteNumber", "1" + "0" * 65536), operand("finiteNumber", "1"))
    elif name.startswith(("string_", "symbol_")):
        category = recipe["category"]
        if "configured_scalar_limit_exceeded" in name:
            left, right = "\U00010000" * 65537, "a"
        elif "last_scalar_difference" in name:
            left, right = "\U00010000" * 65535 + "A", "\U00010000" * 65535 + "B"
        elif "scalar_not_utf16_order" in name:
            left, right = "\U00010000" * 65536, "\U00010000" * 65535 + "\ue000"
        else:
            left = right = "\U00010000" * 65536
        logical = request(operand(category, left), operand(category, right))
    elif name in {"minimum_inline_order_capacity", "configured_order_count_limit_exceeded"}:
        count = 1025 if name.startswith("configured") else 1024
        order = [operand("symbol", "s{:04d}".format(i)) for i in range(count)]
        logical = request(operand("symbol", "s0000"), operand("symbol", "s1023"))
        logical["input"]["policy"] = {"symbols": {"mode": "declared-order",
                                                  "declaration": {"order": order}}}
    elif name in {"minimum_named_registry_capacity", "combined_declaration_count_capacities",
                  "configured_registry_count_limit_exceeded"}:
        combined = name == "combined_declaration_count_capacities"
        count = 65 if name.startswith("configured") else 64
        order = ([operand("symbol", "s{:04d}".format(i)) for i in range(1024)] if combined
                 else [operand("symbol", "low"), operand("symbol", "high")])
        logical = request(copy.deepcopy(order[0]), copy.deepcopy(order[-1]))
        logical["input"]["context"] = {"declarations": [
            {"id": "domain." + str(i), "version": "1", "order": copy.deepcopy(order)}
            for i in range(count)]}
        logical["input"]["policy"] = {"symbols": {"mode": "declared-order", "declaration": {
            "reference": {"id": "domain.63", "version": "1"}}}}
    elif name.startswith("container_depth_"):
        nested = 0
        for _ in range(30 if "one_beyond" in name else 29):
            nested = [nested]
        logical = request({"category": "container", "value": nested}, operand("finiteNumber", "1"))
    elif not name.startswith("logical_json_"):
        raise ValueError("Unknown boundary generator: " + name)
    fixture = {"request": logical}
    if name.startswith("logical_json_"):
        text = json.dumps(logical, separators=(",", ":"), ensure_ascii=False)
        target = 4194305 if "one_byte_beyond" in name else 4194304
        text += " " * (target - len(text.encode("utf-8")))
        require(len(text.encode("utf-8")) == target, "Incorrect generated request byte count")
        fixture = {"requestText": text}
    if "expectedDiagnostic" in recipe:
        failure = recipe["expectedDiagnostic"]
        expected = diagnostic(failure["reason"], failure["stage"], failure["path"])
    else:
        expected = expected_value(recipe["expectedSymbol"], logical)
    return {"id": name, "fixture": fixture, "expected": expected,
            "policy": {"resourceLimits": recipe.get("harnessLimits", {})}}


class Runner:
    def __init__(self, args):
        self.args = args
        self.manifest_path = args.manifest.resolve()
        self.artifacts = {}
        self.manifest = self.asset(self.manifest_path)
        self.schema_path = args.specs_root / self.manifest["meta"].get(
            "specification_schema_file", "resources/aeonic-operations/v1/comparison-contract.schema.json")
        self.binding_path = self.manifest_path.parent / self.manifest["meta"].get(
            "binding_schema_file", "schemas/cts-binding.schema.json")
        self.schema = self.asset(self.schema_path)
        self.binding = self.asset(self.binding_path)
        for schema in [self.schema, self.binding]:
            Draft202012Validator.check_schema(schema)
        registry = Registry().with_resource(self.schema["$id"], Resource.from_contents(self.schema))
        self.validators = {}
        for name in ["ctsInput", "ctsOutput", "fixture"]:
            self.validators[name] = Draft202012Validator(
                dict(self.binding, **{"$ref": "#/$defs/" + name}), registry=registry)
        self.tests = []
        seen = set()
        for suite in self.manifest["suites"]:
            path = self.manifest_path.parent / suite["file"]
            data = self.asset(path, suite["content_sha256"])
            require(data["id"] == suite["id"], "Suite identity mismatch")
            for test in data["tests"]:
                require(test["id"] not in seen, "Duplicate test ID: " + test["id"])
                seen.add(test["id"])
                requirements = test["requiredCapabilities"]
                require(isinstance(requirements, list) and requirements and
                        all(isinstance(item, str) for item in requirements), "Invalid capability requirements")
                require(len(set(requirements)) == len(requirements) and
                        "comparison-baseline" in requirements and
                        set(requirements) <= CAPABILITIES["baseline-with-declared-order"],
                        "Unknown capability requirement: " + test["id"])
                if set(requirements) <= CAPABILITIES[args.capability_set]:
                    self.tests.append(test)
        require(bool(self.tests), "No cases selected by the capability set")
        schema_ref = self.manifest["meta"]["specification_schema_sha256"]
        require(self.artifacts[self.schema_path.resolve()] == schema_ref,
                "Specification schema digest mismatch")
        require(self.artifacts[self.binding_path.resolve()] ==
                self.manifest["meta"]["binding_schema_sha256"], "CTS binding digest mismatch")
        source = (args.specs_root / self.manifest["meta"].get(
            "specification_source_file", "sources/aes/v1/aeonic-semantic-language-v1.aeon")).resolve()
        self.artifacts[source] = digest(source)
        require(self.artifacts[source] == self.manifest["meta"]["specification_source_sha256"],
                "Specification source digest mismatch")
        self.executions = 0
        self.law_assertions = 0

    def asset(self, path, expected=None):
        path = path.resolve()
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        require(expected is None or actual == expected, "Artifact digest mismatch: " + path.name)
        self.artifacts[path] = actual
        return decode(content.decode("utf-8"))

    def invoke(self, case, invocation="default"):
        command = self.args.without_declared_order_sut if invocation == "without-declared-order" else self.args.sut
        require(command, "Missing command for invocation profile: " + invocation)
        envelope = {"lane": "aeonic-operations", "case_id": case["id"],
                    "fixture": case["fixture"], "policy": case.get("policy", {})}
        self.validators["ctsInput"].validate(envelope)
        completed = subprocess.run(shlex.split(command), cwd=self.args.cwd,
                                   input=json.dumps(envelope, ensure_ascii=True),
                                   text=True, encoding="utf-8", capture_output=True,
                                   timeout=self.args.timeout)
        self.executions += 1
        require(completed.returncode == 0,
                case["id"] + ": SUT harness failure: " + completed.stderr[:500])
        output = decode(completed.stdout)
        self.validators["ctsOutput"].validate(output)
        if output["result"]["outcome"] == "diagnostic":
            require(output["errors"][0]["code"] == output["result"]["reason"],
                    case["id"] + ": transport/operation diagnostic disagreement")
        return output

    def match(self, case, output):
        actual = copy.deepcopy(output["result"])
        expected = copy.deepcopy(case["expected"])
        actual.pop("message", None)
        expected.pop("message", None)
        require(actual == expected, case["id"] + ": normative result/metadata/context mismatch")
        for field in case.get("assertAbsent", []):
            require(field not in output["result"], case["id"] + ": forbidden field " + field)

    def operation_case(self, case):
        self.match(case, self.invoke(case, case.get("invocationProfile", "default")))

    def laws(self, group):
        values = group["values"]
        relations = {}
        equality = {}
        for i, j in itertools.product(range(len(values)), repeat=2):
            for operation in ["compare", "equal"]:
                logical = {"operation": operation, "input": {
                    "left": values[i], "right": values[j], "policy": group.get("policy", {})}}
                case = {"id": "{}/{}/{}/{}".format(group["id"], operation, i, j),
                        "fixture": {"request": logical}}
                output = self.invoke(case)
                result = output["result"]
                require(result["outcome"] == "value", case["id"] + ": ordering-law operand rejected")
                symbol = result["value"]["value"]
                allowed = {"less", "equal", "greater"} if operation == "compare" else {"equal", "notEqual"}
                require(symbol in allowed, case["id"] + ": wrong primitive vocabulary")
                self.match(dict(case, expected=expected_value(symbol, logical)), output)
                (relations if operation == "compare" else equality)[i, j] = symbol
                self.law_assertions += 1
        reverse = {"less": "greater", "greater": "less", "equal": "equal"}
        def assertion(condition, law):
            require(condition, group["id"] + ": " + law)
            self.law_assertions += 1
        for i, j in itertools.product(range(len(values)), repeat=2):
            assertion(relations[i, j] == reverse[relations[j, i]], "reversal")
            assertion((equality[i, j] == "equal") == (relations[i, j] == "equal"), "primitive agreement")
            if i == j:
                assertion(relations[i, i] == equality[i, i] == "equal", "reflexivity")
            for k in range(len(values)):
                if relations[i, j] == relations[j, k] and relations[i, j] in {"less", "greater"}:
                    assertion(relations[i, k] == relations[i, j], "strict transitivity")
                if relations[i, j] == "equal":
                    assertion(relations[i, k] == relations[j, k] and
                              relations[k, i] == relations[k, j], "equivalence substitution")

    def run(self):
        counts = {"operation_cases": 0, "ordering_groups": 0, "resource_boundaries": 0}
        failures = []
        for test in self.tests:
            try:
                if test.get("kind") == "ordering-laws":
                    self.laws(test)
                    counts["ordering_groups"] += 1
                elif test.get("kind") == "resource-boundary":
                    self.operation_case(materialize(test))
                    counts["resource_boundaries"] += 1
                else:
                    self.operation_case(test)
                    counts["operation_cases"] += 1
            except Exception as error:
                # A timeout is a harness failure, never an operation resource_limit.
                failures.append({"id": test["id"], "failure": str(error)[:1000]})
        for path, pinned in self.artifacts.items():
            if not path.exists() or digest(path) != pinned:
                failures.append({"id": "artifact-integrity", "failure": "Artifact changed during execution: " + path.name})
        immutable = (self.manifest["meta"].get("conformance", {}).get("stable") is True and
                     ".snapshot-" in self.manifest_path.name)
        return {
            "status": "passed" if not failures else "failed",
            "target": self.manifest["meta"]["snapshot_id"],
            "target_status": "immutable-local" if immutable else "mutable-working",
            "stable_conformance_claim": immutable and not failures,
            "manifest_sha256": self.artifacts[self.manifest_path],
            "specification_schema_sha256": self.manifest["meta"]["specification_schema_sha256"],
            "specification_source_sha256": self.manifest["meta"]["specification_source_sha256"],
            "capability_set": self.args.capability_set, "sut": self.args.sut,
            "without_declared_order_sut": self.args.without_declared_order_sut,
            "cwd": str(self.args.cwd.resolve()), **counts,
            "sut_executions": self.executions, "ordering_assertions": self.law_assertions,
            "failures": failures,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "cts/aeonic-operations/v1/aeonic-operations-cts.v1.snapshot-0.1.json")
    parser.add_argument("--specs-root", type=Path, default=ROOT.parent / "aeonite-specs")
    parser.add_argument("--sut", required=True, help="SUT command; parsed without a shell")
    parser.add_argument("--without-declared-order-sut", required=True,
                        help="same adapter with declared-order execution unavailable")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=20.0, help="per-invocation harness timeout in seconds")
    parser.add_argument("--capability-set", choices=CAPABILITIES, default="baseline-with-declared-order")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    require(args.timeout > 0, "Timeout must be positive")
    report = Runner(args).run()
    serialized = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("CTS harness failure: " + str(error), file=sys.stderr)
        sys.exit(2)
