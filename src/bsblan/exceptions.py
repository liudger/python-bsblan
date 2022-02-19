"""Exceptions for for BSB-Lan."""


class BSBLANError(Exception):
    """Generic BSBLAN exception."""

    pass


class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""

    pass
