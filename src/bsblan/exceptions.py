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
