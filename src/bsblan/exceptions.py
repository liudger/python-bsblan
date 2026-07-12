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
    """Raised when the device does not support a requested feature.

    This signals a permanent condition: the device does not expose the
    requested parameters (for example a heating or hot water schedule), so
    retrying the same request will never succeed.
    """


class BSBLANMalformedResponseError(BSBLANError):
    """Raised when a device response cannot be decoded or parsed.

    This signals a transient condition: the response body could not be decoded
    or parsed as valid JSON, so a retry may succeed.
    """
