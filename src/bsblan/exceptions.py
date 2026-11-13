"""Exceptions for BSB-Lan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .schedules import Weekday


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
    """A feature is unavailable in the current context; permanence is not implied."""


class BSBLANMalformedResponseError(BSBLANError):
    """A response cannot be decoded or parsed; its retryability is unknown."""


class BSBLANScheduleMappingError(BSBLANError):
    """A configured mapping is missing or invalid for a schedule operation."""

    def __init__(self, kind: str, circuit: int | None, reason: str) -> None:
        """Retain the schedule group, circuit, and local failure reason."""
        self.kind = kind
        self.circuit = circuit
        self.reason = reason
        super().__init__(f"{kind} circuit {circuit}: {reason}")


class BSBLANScheduleWriteError(BSBLANError):
    """A sequential write stopped; the failed day may have an uncertain outcome."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        kind: str,
        circuit: int | None,
        acknowledged_days: tuple[Weekday, ...],
        failed_day: Weekday,
        parameter_id: str,
        unattempted_days: tuple[Weekday, ...],
        outcome: Literal["rejected", "unknown"],
    ) -> None:
        """Keep partial progress separate from acknowledgement or readback proof."""
        self.kind = kind
        self.circuit = circuit
        self.acknowledged_days = acknowledged_days
        self.failed_day = failed_day
        self.parameter_id = parameter_id
        self.unattempted_days = unattempted_days
        self.outcome = outcome
        super().__init__(
            f"{kind} schedule circuit {circuit}: {failed_day} parameter "
            f"{parameter_id} outcome {outcome}; acknowledged {acknowledged_days}; "
            f"unattempted {unattempted_days}"
        )
