"""Exceptions for BSB-Lan."""

from __future__ import annotations


class BSBLANError(Exception):
    """Generic BSBLAN exception."""

    message: str = "Unexpected response from the BSBLAN device."

    def __init__(self, message: str | None = None) -> None:
        """Initialize a new instance of the BSBLANError class.

        Args:
            message: Optional custom error message.

        """
        if message is not None:
            self.message = message
        super().__init__(self.message)


class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""

    message_timeout: str = "Timeout occurred while connecting to BSBLAN device."
    message_error: str = "Error occurred while connecting to BSBLAN device."

    def __init__(self, message: str | None = None) -> None:
        """Initialize a new instance of the BSBLANConnectionError class.

        Args:
            message: Optional error message.

        """
        super().__init__(message)


class BSBLANVersionError(BSBLANError):
    """Raised when the BSBLAN device has an unsupported version."""

    message: str = "The BSBLAN device has an unsupported version."
    version: str | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        version: str | None = None,
    ) -> None:
        """Initialize a new instance of the BSBLANVersionError class.

        Args:
            message: Optional custom error message.
            version: The unsupported firmware version, if known.

        """
        self.version = version
        super().__init__(message)


class BSBLANInvalidParameterError(BSBLANError):
    """Raised when an invalid parameter is provided."""

    def __init__(self, parameter: str) -> None:
        """Initialize a new instance of the BSBLANInvalidParameterError class.

        Args:
            parameter: The invalid parameter that caused the error.

        """
        self.message = f"Invalid values provided: {parameter}"
        super().__init__(self.message)


class BSBLANAuthError(BSBLANError):
    """Raised when authentication fails."""

    message: str = "Authentication failed. Please check your username and password."


class BSBLANUnsupportedFeatureError(BSBLANError):
    """A feature is unavailable in the current context; permanence is not implied."""


class BSBLANMalformedResponseError(BSBLANError):
    """A response cannot be decoded or parsed; its retryability is unknown."""


class BSBLANScheduleMappingError(BSBLANError):
    """An explicit caller mapping is missing or invalid for a schedule read."""

    def __init__(self, kind: str, circuit: int | None, reason: str) -> None:
        """Retain the schedule group, circuit, and local failure reason."""
        self.kind = kind
        self.circuit = circuit
        self.reason = reason
        super().__init__(f"{kind} circuit {circuit}: {reason}")
