# windlathe

`windlathe` provides experimental, pre-alpha utilities for defining and
validating metadata for multidimensional scientific model grids.

The current release validates versioned JSON manifests and provides structured
validation errors. The API and file format may change before version 1.0.

## Manifest format

Schema version 1 describes ordered grid axes and fields stored on the complete
grid. A minimal two-dimensional manifest looks like this:

```json
{
  "schema_version": 1,
  "axes": [
    {
      "name": "parameter_a",
      "units": "1",
      "coordinates": [0, 1]
    },
    {
      "name": "parameter_b",
      "units": "1",
      "coordinates": [10, 20, 30]
    }
  ],
  "fields": [
    {
      "name": "field_1",
      "units": "1",
      "shape": [2, 3],
      "data_reference": "field_1.json"
    }
  ],
  "provenance": ["generated example"]
}
```

Axis and field names must be unique within their lists. Coordinates must be
finite numbers, and each field shape must match the coordinate counts in axis
order. The optional `provenance` value is an array of non-empty strings.
Unknown keys are rejected so misspellings do not silently pass validation.

Load a manifest from a path or an open text or binary file:

```python
from windlathe import load_manifest

manifest = load_manifest("manifest.json")
print(manifest.axes[0].coordinates)
print(manifest.fingerprint())
```

`load_manifest` returns an immutable `Manifest` containing typed `Axis` and
`Field` objects. Invalid JSON raises `ManifestDecodeError`; valid JSON that
does not match the schema raises `ManifestValidationError`. A validation error
provides `path` and `message` attributes in addition to its readable string.

## Development environment

Create the Conda environment and activate it:

```console
conda env create -f environment.yml
conda activate windlathe
```

Run the tests with:

```console
python -m unittest discover -s test -v
```
