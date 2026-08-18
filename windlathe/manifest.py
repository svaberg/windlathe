"""Typed model and validation for version 1 grid manifests."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from typing import IO, Any, Iterable, Mapping, TypeAlias

from .errors import ManifestDecodeError, ManifestValidationError

Number: TypeAlias = int | float
ManifestSource: TypeAlias = str | os.PathLike[str] | IO[str] | IO[bytes]

_ROOT_REQUIRED = frozenset({"schema_version", "axes", "fields"})
_ROOT_OPTIONAL = frozenset({"provenance"})
_AXIS_KEYS = frozenset({"name", "units", "coordinates"})
_FIELD_KEYS = frozenset({"name", "units", "shape", "data_reference"})


@dataclass(frozen=True, slots=True)
class Axis:
    """One ordered axis in a model grid."""

    name: str
    units: str
    coordinates: tuple[Number, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "name": self.name,
            "units": self.units,
            "coordinates": list(self.coordinates),
        }


@dataclass(frozen=True, slots=True)
class Field:
    """Metadata for one named field stored on the grid."""

    name: str
    units: str
    shape: tuple[int, ...]
    data_reference: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "name": self.name,
            "units": self.units,
            "shape": list(self.shape),
            "data_reference": self.data_reference,
        }


@dataclass(frozen=True, slots=True)
class Manifest:
    """Validated metadata for a multidimensional model grid."""

    schema_version: int
    axes: tuple[Axis, ...]
    fields: tuple[Field, ...]
    provenance: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible manifest data."""
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "axes": [axis.to_dict() for axis in self.axes],
            "fields": [field.to_dict() for field in self.fields],
        }
        if self.provenance:
            data["provenance"] = list(self.provenance)
        return data

    def fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the manifest."""
        encoded = json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_manifest(source: ManifestSource) -> Manifest:
    """Load and validate a manifest from a path or readable file object."""
    try:
        if isinstance(source, (str, os.PathLike)):
            with open(source, "rb") as stream:
                data = json.load(stream)
        elif hasattr(source, "read"):
            data = json.load(source)
        else:
            raise TypeError("source must be a path or readable file object")
    except json.JSONDecodeError as error:
        raise ManifestDecodeError(
            error.msg,
            line=error.lineno,
            column=error.colno,
        ) from error

    return validate_manifest(data)


def validate_manifest(data: object) -> Manifest:
    """Validate decoded JSON data and return its typed representation."""
    root = _mapping(data, "$")
    _keys(root, required=_ROOT_REQUIRED, optional=_ROOT_OPTIONAL, path="$")

    schema_version = _integer(root["schema_version"], "$.schema_version")
    if schema_version != 1:
        _invalid("$.schema_version", "unsupported schema version; expected 1")

    raw_axes = _list(root["axes"], "$.axes")
    if not raw_axes:
        _invalid("$.axes", "must contain at least one axis")

    axes = tuple(_axis(value, index) for index, value in enumerate(raw_axes))
    _unique_names((axis.name for axis in axes), "$.axes")

    raw_fields = _list(root["fields"], "$.fields")
    if not raw_fields:
        _invalid("$.fields", "must contain at least one field")

    expected_shape = tuple(len(axis.coordinates) for axis in axes)
    fields = tuple(
        _field(value, index, expected_shape)
        for index, value in enumerate(raw_fields)
    )
    _unique_names((field.name for field in fields), "$.fields")

    raw_provenance = root.get("provenance", [])
    provenance_values = _list(raw_provenance, "$.provenance")
    provenance = tuple(
        _nonempty_string(value, f"$.provenance[{index}]")
        for index, value in enumerate(provenance_values)
    )

    return Manifest(
        schema_version=schema_version,
        axes=axes,
        fields=fields,
        provenance=provenance,
    )


def _axis(value: object, index: int) -> Axis:
    path = f"$.axes[{index}]"
    data = _mapping(value, path)
    _keys(data, required=_AXIS_KEYS, optional=frozenset(), path=path)

    coordinates_path = f"{path}.coordinates"
    raw_coordinates = _list(data["coordinates"], coordinates_path)
    if not raw_coordinates:
        _invalid(coordinates_path, "must contain at least one coordinate")
    coordinates = tuple(
        _number(value, f"{coordinates_path}[{position}]")
        for position, value in enumerate(raw_coordinates)
    )

    return Axis(
        name=_nonempty_string(data["name"], f"{path}.name"),
        units=_nonempty_string(data["units"], f"{path}.units"),
        coordinates=coordinates,
    )


def _field(value: object, index: int, expected_shape: tuple[int, ...]) -> Field:
    path = f"$.fields[{index}]"
    data = _mapping(value, path)
    _keys(data, required=_FIELD_KEYS, optional=frozenset(), path=path)

    shape_path = f"{path}.shape"
    raw_shape = _list(data["shape"], shape_path)
    shape = tuple(
        _positive_integer(value, f"{shape_path}[{position}]")
        for position, value in enumerate(raw_shape)
    )
    if shape != expected_shape:
        _invalid(shape_path, f"expected {list(expected_shape)}, got {list(shape)}")

    return Field(
        name=_nonempty_string(data["name"], f"{path}.name"),
        units=_nonempty_string(data["units"], f"{path}.units"),
        shape=shape,
        data_reference=_nonempty_string(
            data["data_reference"], f"{path}.data_reference"
        ),
    )


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _invalid(path, "expected an object")
    if any(not isinstance(key, str) for key in value):
        _invalid(path, "object keys must be strings")
    return value


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _invalid(path, "expected an array")
    return value


def _keys(
    data: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str],
    path: str,
) -> None:
    missing = sorted(required.difference(data))
    if missing:
        _invalid(path, f"missing required key {missing[0]!r}")

    unexpected = sorted(set(data).difference(required | optional))
    if unexpected:
        _invalid(path, f"unexpected key {unexpected[0]!r}")


def _nonempty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(path, "expected a non-empty string")
    return value


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid(path, "expected an integer")
    return value


def _positive_integer(value: object, path: str) -> int:
    result = _integer(value, path)
    if result <= 0:
        _invalid(path, "expected a positive integer")
    return result


def _number(value: object, path: str) -> Number:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(path, "expected a finite number")
    if not math.isfinite(value):
        _invalid(path, "expected a finite number")
    return value


def _unique_names(names: Iterable[str], path: str) -> None:
    seen: set[str] = set()
    for index, name in enumerate(names):
        if name in seen:
            _invalid(f"{path}[{index}].name", f"duplicate name {name!r}")
        seen.add(name)


def _invalid(path: str, message: str) -> None:
    raise ManifestValidationError(path, message)
