import json
import math
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from windlathe import (
    ManifestDecodeError,
    ManifestValidationError,
    load_manifest,
    validate_manifest,
)


DATA = Path(__file__).parent / "data"


def valid_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "axes": [
            {
                "name": "parameter_a",
                "units": "1",
                "coordinates": [0, 1],
            },
            {
                "name": "parameter_b",
                "units": "1",
                "coordinates": [10, 20, 30],
            },
        ],
        "fields": [
            {
                "name": "field_1",
                "units": "1",
                "shape": [2, 3],
                "data_reference": "field_1.json",
            }
        ],
        "provenance": ["generated for testing"],
    }


class LoadManifestTests(unittest.TestCase):
    def test_loads_path_into_typed_manifest(self) -> None:
        manifest = load_manifest(DATA / "valid_minimal.json")

        self.assertEqual(manifest.schema_version, 1)
        self.assertEqual(manifest.axes[0].name, "parameter_a")
        self.assertEqual(manifest.axes[1].coordinates, (10, 20, 30))
        self.assertEqual(manifest.fields[0].shape, (2, 3))
        self.assertEqual(manifest.provenance, ("generated for testing",))

    def test_loads_file_like_object(self) -> None:
        stream = StringIO(json.dumps(valid_data()))

        manifest = load_manifest(stream)

        self.assertEqual(manifest.fields[0].data_reference, "field_1.json")

    def test_reports_malformed_json_location(self) -> None:
        with self.assertRaisesRegex(
            ManifestDecodeError,
            r"invalid JSON at line 1, column 20",
        ):
            load_manifest(StringIO('{"schema_version": }'))

    def test_does_not_close_caller_file(self) -> None:
        with tempfile.TemporaryFile(mode="w+") as stream:
            json.dump(valid_data(), stream)
            stream.seek(0)

            load_manifest(stream)

            self.assertFalse(stream.closed)


class ValidateManifestTests(unittest.TestCase):
    def test_reports_missing_schema_version(self) -> None:
        with self.assertRaises(ManifestValidationError) as raised:
            load_manifest(DATA / "invalid_missing_version.json")

        self.assertEqual(raised.exception.path, "$")
        self.assertEqual(
            raised.exception.message,
            "missing required key 'schema_version'",
        )

    def test_rejects_unsupported_schema_version(self) -> None:
        data = valid_data()
        data["schema_version"] = 2

        with self.assertRaisesRegex(
            ManifestValidationError,
            r"^\$\.schema_version: unsupported schema version; expected 1$",
        ):
            validate_manifest(data)

    def test_rejects_shape_that_does_not_match_axes(self) -> None:
        data = valid_data()
        data["fields"][0]["shape"] = [3, 2]  # type: ignore[index]

        with self.assertRaises(ManifestValidationError) as raised:
            validate_manifest(data)

        self.assertEqual(raised.exception.path, "$.fields[0].shape")
        self.assertEqual(raised.exception.message, "expected [2, 3], got [3, 2]")

    def test_rejects_duplicate_axis_names(self) -> None:
        data = valid_data()
        data["axes"][1]["name"] = "parameter_a"  # type: ignore[index]

        with self.assertRaises(ManifestValidationError) as raised:
            validate_manifest(data)

        self.assertEqual(raised.exception.path, "$.axes[1].name")
        self.assertEqual(raised.exception.message, "duplicate name 'parameter_a'")

    def test_rejects_non_finite_coordinate(self) -> None:
        data = valid_data()
        data["axes"][0]["coordinates"] = [math.inf]  # type: ignore[index]

        with self.assertRaises(ManifestValidationError) as raised:
            validate_manifest(data)

        self.assertEqual(raised.exception.path, "$.axes[0].coordinates[0]")
        self.assertEqual(raised.exception.message, "expected a finite number")

    def test_rejects_unknown_keys(self) -> None:
        data = valid_data()
        data["extra"] = True

        with self.assertRaises(ManifestValidationError) as raised:
            validate_manifest(data)

        self.assertEqual(raised.exception.path, "$")
        self.assertEqual(raised.exception.message, "unexpected key 'extra'")

    def test_fingerprint_is_stable_across_key_order(self) -> None:
        first = validate_manifest(valid_data())
        reordered = dict(reversed(list(valid_data().items())))
        second = validate_manifest(reordered)

        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertEqual(
            first.fingerprint(),
            "a67f77e4ec1f0ecdfce9253a20afbb5153ee2752e56ed20801ab491b2d8778cb",
        )


if __name__ == "__main__":
    unittest.main()
