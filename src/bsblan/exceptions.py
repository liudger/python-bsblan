"""Exceptions for for BSB-Lan."""
from __future__ import annotations


class BSBLANError(Exception):
    """Generic BSBLAN exception."""

    message: str = "Unexpected response from the BSBLAN device."

    def __init__(self, message: str | None = None) -> None:
        """Initialize a new instance of the BSBLANError class.

        Args:
        ----
            message: Optional error message to include in the exception.

        Returns:
        -------
            None.

        """
        if message is not None:
            self.message = message
        super().__init__(self.message)


class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception.

    Attributes
    ----------
        response: The response received from the BSBLAN device.

    """

    message = "Error occurred while connecting to BSBLAN device."

    def __init__(self, response: str | None = None) -> None:
        """Initialize a new instance of the BSBLANConnectionError class.

        Args:
        ----
            response: Optional error message to include in the exception.

        Returns:
        -------
            None.

        """
        self.response = response
        super().__init__(self.message)


class BSBLANVersionError(BSBLANError):
    """Raised when the BSBLAN device has an unsupported version."""

    message = "The BSBLAN device has an unsupported version."


class BSBLANInvalidParameterError(BSBLANError):
    """Raised when an invalid parameter is provided."""

    def __init__(self, parameter: str) -> None:
        """Initialize a new instance of the BSBLANInvalidParameterError class.

        Args:
        ----
            parameter: The invalid parameter.

        Returns:
        -------
            None.

        """
        self.message = f"Invalid parameter: {parameter}"
        super().__init__(self.message)
