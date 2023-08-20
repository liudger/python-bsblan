"""Exceptions for for BSB-Lan."""


from typing import Optional


class BSBLANError(Exception):
    """Generic BSBLAN exception."""

    message: str = "Unexpected response from the BSBLAN device."

    def __init__(self, message: Optional[str] = None) -> None:
        """
        Initialize a new instance of the BSBLANError class.

        Args:
            message: Optional error message to include in the exception.

        Returns:
            None.
        """
        if message is not None:
            self.message = message
        super().__init__(self.message)

class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""

    message = "Error occurred while connecting to BSBLAN device."

    def __init__(self, response: Optional[str] = None) -> None:
        """
        Initialize a new instance of the BSBLANConnectionError class.

        Args:
            message: Optional error message to include in the exception.

        Returns:
            None.
        """
        self.response = response
        super().__init__(self.message)
