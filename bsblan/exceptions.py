"""Exceptions for for BSB-Lan."""


class BSBLanError(Exception):
    """Generic BSBLan exception."""

    pass


class BSBLanConnectionError(BSBLanError):
    """BSBLan connection exception."""

    pass
