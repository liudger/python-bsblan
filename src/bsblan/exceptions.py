"""Exceptions for for BSB-Lan."""


class BSBLANError(Exception):
    """Generic BSBLAN exception."""
    message = "Unexpected response from the BSBLAN device."


class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""
    message = "Error occurred while connecting to BSBLAN device."

    def __init__(self, response):
        self.response = response
        super().__init__(self.message)
