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

    def __init__(self, response: str | None = None) -> None:
        """Initialize a new instance of the BSBLANConnectionError class.

        Args:
            response: Optional response message.

        """
        self.response = response
        super().__init__(self.message)


class BSBLANVersionError(BSBLANError):
    """Raised when the BSBLAN device has an unsupported version."""

    message: str = "The BSBLAN device has an unsupported version."


class BSBLANInvalidParameterError(BSBLANError):
    """Raised when an invalid parameter is provided."""

    def __init__(self, parameter: str) -> None:
        """Initialize a new instance of the BSBLANInvalidParameterError class.

        Args:
            parameter: The invalid parameter that caused the error.

        """
        self.message = f"Invalid values provided: {parameter}"
        super().__init__(self.message)
