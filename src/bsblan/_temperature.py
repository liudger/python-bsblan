"""Temperature range, unit, and bounds management for the BSBLAN client.

Owns the per-circuit temperature range cache, the set of circuits whose range
has been initialized, and the active temperature unit. Ranges are lazily
fetched from the device static values and target temperatures are validated
against the heating and cooling bounds. The owning client keeps thin
delegations that forward here.

The manager reads discovered circuits and fetches static values through
callables supplied by the owning client so it does not hold a back-reference
to the facade.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .exceptions import BSBLANError, BSBLANInvalidParameterError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from .bsblan import SectionLiteral
    from .models import StaticState

logger = logging.getLogger(__name__)


class TemperatureManager:
    """Manage per-circuit temperature ranges, the unit, and bounds checks.

    The manager owns the temperature state (per-circuit range cache, the set of
    circuits whose range has been initialized, and the active unit). Static
    values are read through ``static_values`` and discovered circuits through
    ``get_available_circuits`` so the manager never holds a back-reference to
    the owning client.
    """

    def __init__(
        self,
        *,
        static_values: Callable[..., Awaitable[StaticState]],
        get_available_circuits: Callable[[], set[int] | None],
    ) -> None:
        """Initialize the manager with the client's collaborators.

        Args:
            static_values: Callable returning the static values model for a
                circuit.
            get_available_circuits: Callable returning the set of circuits known
                to be available, or ``None`` when discovery has not run.

        """
        self._static_values = static_values
        self._get_available_circuits = get_available_circuits
        self._temperature_unit: str = "°C"
        # Per-circuit temperature ranges: circuit_number -> range dict.
        self._circuit_temp_ranges: dict[int, dict[str, float | None]] = {}
        self._circuit_temp_initialized: set[int] = set()

    @property
    def unit(self) -> str:
        """Return the active temperature unit (°C or °F)."""
        return self._temperature_unit

    def should_extract_temperature_unit(
        self,
        section: SectionLiteral,
        include: list[str] | None,
        response_data: dict[str, Any],
    ) -> bool:
        """Return whether the validation response should update temperature unit."""
        if section != "heating":
            return False

        if include is None or "target_temperature" in include:
            return True

        return any(param_id in response_data for param_id in ("710", "15004"))

    def extract_temperature_unit_from_response(
        self, response_data: dict[str, Any]
    ) -> None:
        """Extract temperature unit from heating section response data.

        Gets the unit from the target_temperature parameter, which is always
        present in the heating section.

        Args:
            response_data: The response data from heating section validation

        """
        # Look for target_temperature in the response.
        for param_id, param_data in response_data.items():
            if param_id in {"710", "15004"} and isinstance(param_data, dict):
                unit = param_data.get("unit", "")
                if unit in ("&deg;C", "°C"):
                    self._temperature_unit = "°C"
                elif unit == "°F":
                    self._temperature_unit = "°F"
                else:
                    # Keep default if unit is empty or unknown
                    logger.debug(
                        "Unknown or empty temperature unit from heating target: "
                        "'%s'. Using default (°C)",
                        unit,
                    )
                logger.debug("Temperature unit set to: %s", self._temperature_unit)
                return

        logger.warning(
            "Could not find target temperature in heating section response. "
            "Using default temperature unit (°C)"
        )

    async def _fetch_temperature_range(
        self,
        circuit: int,
    ) -> dict[str, float | None]:
        """Fetch min/max temperature range for a circuit from the device.

        Args:
            circuit: The heating circuit number (1 or 2).

        Returns:
            dict with heating and cooling min/max keys. Values may be None if
            unavailable.

        """
        temp_range: dict[str, float | None] = {
            "min": None,
            "max": None,
            "cooling_min": None,
            "cooling_max": None,
        }
        available_circuits = self._get_available_circuits()
        if available_circuits is not None and circuit not in available_circuits:
            logger.debug(
                "Skipping temperature range fetch for unavailable circuit %d",
                circuit,
            )
            return temp_range

        try:
            static_values = await self._static_values(circuit=circuit)
        except BSBLANError as err:
            logger.warning(
                "Failed to get static values for circuit %d: %s. "
                "Temperature range will be None",
                circuit,
                str(err),
            )
            return temp_range

        # Prefer heating_protective_setpoint (714/1014) as the true lower bound
        # for standard circuits. Fall back to min_temp for PPS circuits (15006)
        # which have no separate protective setpoint. Skip sources whose value is
        # inactive (BSB-LAN may return "---" which becomes value=None).
        min_source = next(
            (
                source
                for source in (
                    static_values.heating_protective_setpoint,
                    static_values.min_temp,
                )
                if source is not None and source.value is not None
            ),
            None,
        )
        if min_source is not None:
            temp_range["min"] = min_source.value
            logger.debug(
                "Circuit %d min temp initialized: %s",
                circuit,
                temp_range["min"],
            )

        # Prefer comfort_setpoint_max (716/1016) as the upper bound for standard
        # circuits. Fall back to max_temp for PPS circuits (15007) which expose
        # only a generic max. Skip sources whose value is inactive.
        max_source = next(
            (
                source
                for source in (
                    static_values.comfort_setpoint_max,
                    static_values.max_temp,
                )
                if source is not None and source.value is not None
            ),
            None,
        )
        if max_source is not None:
            temp_range["max"] = max_source.value
            logger.debug(
                "Circuit %d max temp initialized: %s",
                circuit,
                temp_range["max"],
            )

        if static_values.cooling_comfort_setpoint_min is not None:
            temp_range["cooling_min"] = static_values.cooling_comfort_setpoint_min.value
            logger.debug(
                "Circuit %d cooling min temp initialized: %s",
                circuit,
                temp_range["cooling_min"],
            )

        if static_values.cooling_reduced_setpoint is not None:
            temp_range["cooling_max"] = static_values.cooling_reduced_setpoint.value
            logger.debug(
                "Circuit %d cooling max temp initialized: %s",
                circuit,
                temp_range["cooling_max"],
            )

        return temp_range

    async def initialize_temperature_range(
        self,
        circuit: int = 1,
    ) -> None:
        """Initialize the temperature range from static values (lazy loaded).

        This method is called on-demand when temperature range is needed.
        It uses lazy loading through static_values() which will validate
        the staticValues section if not already done.

        Args:
            circuit: The heating circuit number (1 or 2).

        Note: Temperature unit is extracted during heating section validation,
        so no extra API call is needed here.

        """
        if circuit in self._circuit_temp_initialized:
            return

        temp_range = await self._fetch_temperature_range(circuit)
        self._circuit_temp_ranges[circuit] = temp_range
        self._circuit_temp_initialized.add(circuit)

    async def _validate_in_range(
        self,
        value: str | float,
        circuit: int,
        *,
        min_key: str,
        max_key: str,
    ) -> None:
        """Validate a temperature value against a circuit's configured bounds.

        Lazy-loads the circuit temperature range when needed. If the device
        does not expose the relevant bounds, only the float conversion is
        validated.

        Args:
            value (str | float): The temperature value to validate.
            circuit (int): The heating circuit number (1 or 2).
            min_key (str): Range key holding the lower bound.
            max_key (str): Range key holding the upper bound.

        Raises:
            BSBLANInvalidParameterError: If the value is not a valid float or
                falls outside the configured bounds.

        """
        try:
            temp = float(value)
        except ValueError as err:
            raise BSBLANInvalidParameterError(str(value)) from err

        if circuit not in self._circuit_temp_initialized:
            await self.initialize_temperature_range(circuit)

        temp_range = self._circuit_temp_ranges.get(circuit, {})
        min_temp = temp_range.get(min_key)
        max_temp = temp_range.get(max_key)

        if min_temp is None or max_temp is None:
            return

        if not (min_temp <= temp <= max_temp):
            raise BSBLANInvalidParameterError(str(value))

    async def validate_target_temperature_high(
        self,
        target_temperature_high: str | float,
        circuit: int = 1,
    ) -> None:
        """Validate the cooling target temperature value."""
        await self._validate_in_range(
            target_temperature_high,
            circuit,
            min_key="cooling_min",
            max_key="cooling_max",
        )

    async def validate_target_temperature(
        self,
        target_temperature: str,
        circuit: int = 1,
    ) -> None:
        """Validate the target temperature.

        This method lazy-loads the temperature range if not already initialized.
        If the device does not provide min/max temperature parameters,
        only validates that the value is a valid float.

        Args:
            target_temperature (str): The target temperature to validate.
            circuit: The heating circuit number (1 or 2).

        Raises:
            BSBLANInvalidParameterError: If the target temperature is invalid.

        """
        await self._validate_in_range(
            target_temperature,
            circuit,
            min_key="min",
            max_key="max",
        )
