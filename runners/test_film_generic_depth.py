"""Fixture oracle for the small single-number Film vectors, not a Film codec.

Uses only the wire grammar and the clarified AES counter; no implementation
checkout is imported. Full optional-field replacement bytes are checked against
their historical fixture separately. Runtime/incremental checks belong to the
implementation's CTS harness, not this repository-integrity test.
"""
import json
import unittest

import validate_cts_repo as validator


ROOT = validator.ROOT / "cts/film/v1"
SUITE = json.loads((ROOT / "suites/06-next-logical-generic-depth.json").read_text())
REVISION = "242daa4214237cdc70d512b593c126615ab0556b"
OLD_ID = "film-type-generics-limit-014-generic-depth-one-over"


class FixtureError(Exception):
    def __init__(self, code, diagnostic=None):
        self.code = code
        self.diagnostic = diagnostic


def uleb(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def field(value):
    return uleb(len(value)) + value


def text(value):
    return field(value.encode("utf-8"))


def descriptor_bytes(descriptor):
    generics = descriptor["generics"]
    clarifiers = descriptor["clarifiers"]
    return field(text(descriptor["datatype"]) + uleb(len(generics))
                 + b"".join(b"\x00" + descriptor_bytes(item) for item in generics)
                 + uleb(len(clarifiers))
                 + b"".join(bytes([2 if item["kind"] == "NumberLiteral" else 1])
                            + text(item["value"]) for item in clarifiers))


def film_bytes(record):
    payload = b"\x02\x02" + text(record["path"]) + descriptor_bytes(record) + text(record["value"])
    return b"O__\xff\x01\x00" + field(payload)


def logical_depth(descriptor, level=0):
    return max([level if descriptor["generics"] else 0]
               + [logical_depth(item, level + 1) for item in descriptor["generics"]])


def logical_components(descriptor):
    return (1 + len(descriptor["clarifiers"])
            + sum(logical_components(item) for item in descriptor["generics"]))


def spelling(descriptor):
    result = descriptor["datatype"]
    if descriptor["generics"]:
        result += "<" + ",".join(map(spelling, descriptor["generics"])) + ">"
    if descriptor["clarifiers"]:
        result += "[" + ",".join(json.dumps(item["value"]) if item["kind"] == "StringLiteral"
                                 else item["value"] for item in descriptor["clarifiers"]) + "]"
    return result


class Reader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def take(self, length):
        if self.position + length > len(self.data):
            raise FixtureError("FILM_TRUNCATED")
        result = self.data[self.position:self.position + length]
        self.position += length
        return result

    def integer(self):
        value = shift = 0
        while True:
            byte = self.take(1)[0]
            value |= (byte & 127) << shift
            if byte < 128:
                return value
            shift += 7
            if shift > 63:
                raise AssertionError("fixture ULEB is not bounded")

    def field(self, limits):
        length = self.integer()
        if length > limits.get("max_field_bytes", 4_194_304):
            raise FixtureError("FILM_LIMIT_EXCEEDED")
        return self.take(length)

    def text(self, limits):
        return self.field(limits).decode("utf-8")

    def exhausted(self):
        if self.position != len(self.data):
            raise FixtureError("FILM_NONCANONICAL")


def read_descriptor(reader, limits, state, level=0):
    def claim():
        state[0] += 1
        check(state[0], "max_datatype_components", 1_000_000)

    def check(value, name, default):
        if value > limits.get(name, default):
            raise FixtureError("FILM_AES_INVALID", "AES_LIMIT_EXCEEDED")

    claim()
    body = Reader(reader.field(limits))
    name = body.text(limits)
    count = body.integer()
    check(count, "max_generic_arguments", 1)
    if count:
        check(level, "max_generic_depth", 1)
    generics = []
    for _ in range(count):
        tag = body.take(1)[0]
        if tag == 0:
            generics.append(read_descriptor(body, limits, state, level + 1))
        else:
            # The only non-descriptor generic vector uses historical tag 02.
            assert tag == 2
            claim()
            body.text(limits)
            state[1] = True
    clarifiers = []
    count = body.integer()
    check(count, "max_clarifier_values", 1)
    for _ in range(count):
        claim()
        tag = body.take(1)[0]
        assert tag in (1, 2)
        clarifiers.append({"kind": "NumberLiteral" if tag == 2 else "StringLiteral",
                           "value": body.text(limits)})
    body.exhausted()
    return {"datatype": name, "generics": generics, "clarifiers": clarifiers}


def decode_fixture(source, limits):
    reader = Reader(bytes.fromhex(source))
    assert reader.take(6) == b"O__\xff\x01\x00"
    payload = Reader(reader.take(reader.integer()))
    reader.exhausted()
    assert payload.take(2) == b"\x02\x02"
    path = payload.text(limits)
    state = [0, False]
    descriptor = read_descriptor(payload, limits, state)
    value = payload.text(limits)
    payload.exhausted()
    if state[1]:
        raise FixtureError("FILM_AES_INVALID", "AES_INVALID_DATATYPE")
    return {"path": path, "kind": "NumberLiteral", **descriptor, "value": value}


class FilmGenericDepthTests(unittest.TestCase):
    def test_decode_bytes_boundaries_and_error_expectations(self):
        for test in SUITE["tests"]:
            if test["operation"] != "decode" or "replacement" in test["tags"]:
                continue
            with self.subTest(id=test["id"]):
                expected = test["expected"]
                try:
                    record = decode_fixture(test["input"]["film_hex"], test["input"]["limits"])
                except FixtureError as error:
                    self.assertFalse(expected["ok"])
                    self.assertEqual(expected["error"]["code"], error.code)
                    if "diagnostic_codes" in expected["error"]:
                        self.assertEqual(expected["error"]["diagnostic_codes"], [error.diagnostic])
                else:
                    self.assertTrue(expected["ok"])
                    self.assertEqual(expected["stream"]["records"], [record])
                    self.assertEqual(expected["canonical_hex"], film_bytes(record).hex())

    def test_encoders_and_transcodes_share_the_same_logical_boundaries(self):
        for test in SUITE["tests"]:
            with self.subTest(id=test["id"]):
                if test["operation"] == "encode":
                    record = test["input"]["stream"]["records"][0]
                    limit = test["input"]["limits"]["max_generic_depth"]
                    if test["expected"]["ok"]:
                        self.assertLessEqual(logical_depth(record), limit)
                        self.assertEqual(test["expected"]["film_hex"], film_bytes(record).hex())
                    elif "components-over" in test["id"]:
                        self.assertGreater(logical_components(record), test["input"]["limits"]["max_datatype_components"])
                        self.assertEqual(["AES_DATATYPE_LIMIT"], test["expected"]["error"]["diagnostic_codes"])
                    else:
                        self.assertGreater(logical_depth(record), limit)
                        self.assertEqual(["AES_DATATYPE_DEPTH"], test["expected"]["error"]["diagnostic_codes"])
                elif test["operation"] == "transcode":
                    self.assertNotIn("limits", test["input"], "existing transcode API uses defaults")
                    record = decode_fixture(test["expected"]["film_hex"], {})
                    self.assertEqual(1, logical_depth(record))
                    telex = ("telex.aes=1\n\npath=$.a\nkind=NumberLiteral\ndatatype="
                             + spelling(record) + "\nvalue=0\n")
                    self.assertEqual(telex, test["input"]["telex"])
                    self.assertEqual(telex, test["expected"]["telex"])
                    self.assertEqual(test["expected"]["film_hex"], film_bytes(record).hex())

    def test_development_only_replacement_and_exact_revision(self):
        next_manifest = json.loads((ROOT / "film-cts.v1.next.json").read_text())
        stable = json.loads((ROOT / "film-cts.v1.snapshot-0.3.json").read_text())
        old_suite = json.loads((ROOT / "suites/05-next-type-only-generics.json").read_text())
        old = next(test for test in old_suite["tests"] if test["id"] == OLD_ID)
        replacement = next(test for test in SUITE["tests"] if "replacement" in test["tags"])
        self.assertEqual(REVISION, next_manifest["meta"]["specification_revision"])
        self.assertEqual(REVISION, SUITE["meta"]["specification_revision"])
        self.assertEqual(old["input"], replacement["input"])
        self.assertFalse(old["expected"]["ok"])
        self.assertTrue(replacement["expected"]["ok"])
        self.assertEqual(old["input"]["film_hex"], replacement["expected"]["canonical_hex"])
        old_next_ref = next(ref for ref in next_manifest["suites"] if ref["file"].endswith("05-next-type-only-generics.json"))
        self.assertEqual([OLD_ID], old_next_ref["exclude_tests"])
        stable_ref = next(ref for ref in stable["suites"] if ref["file"].endswith("05-next-type-only-generics.json"))
        self.assertNotIn(OLD_ID, stable_ref.get("exclude_tests", []))
        self.assertFalse(any(ref["id"] == SUITE["id"] for ref in stable["suites"]))
        selected = sum(len(json.loads((ROOT / ref["file"]).read_text())["tests"])
                       - len(ref.get("exclude_tests", [])) for ref in next_manifest["suites"])
        self.assertEqual(37, len(SUITE["tests"]))
        self.assertEqual(128, selected)


if __name__ == "__main__":
    unittest.main()
