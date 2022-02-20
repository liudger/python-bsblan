"""Exceptions for for BSB-Lan."""


class BSBLANError(Exception):
    """Generic BSBLAN exception."""


class BSBLANConnectionError(BSBLANError):
    """BSBLAN connection exception."""
