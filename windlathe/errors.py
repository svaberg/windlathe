"""Exceptions raised while loading and validating manifests."""


class ManifestError(Exception):
    """Base class for manifest errors."""


class ManifestDecodeError(ManifestError):
    """Raised when a manifest is not valid JSON."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.column = column

        location = ""
        if line is not None and column is not None:
            location = f" at line {line}, column {column}"
        super().__init__(f"invalid JSON{location}: {message}")


class ManifestValidationError(ManifestError):
    """Raised when decoded JSON does not match the manifest schema."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")
