"""Exceptions for for BSB-Lan."""


class BSBLANError(Exception):
    """Generic BSBLAN exception."""
    message = "Unexpected response from the BSBLAN device."

    def __init__(self, message=None):
        if message is not None:
            self.message = message
        super().__init__(self.message)

class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""
    message = "Error occurred while connecting to BSBLAN device."

    def __init__(self, response):
        self.response = response
        super().__init__(self.message)
