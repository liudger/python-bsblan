"""Thermostat write preparation for BSB-LAN."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .constants import CircuitConfig, Validation
from .exceptions import BSBLANInvalidParameterError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._temperature import TemperatureManager


class ThermostatWriter:
    """Prepare and validate thermostat write payloads."""

    def __init__(
        self,
        *,
        uses_pps_bus: Callable[[], bool],
        temperature: TemperatureManager,
        set_payload: Callable[[str, str], dict[str, Any]],
    ) -> None:
        """Initialize the thermostat writer.

        Args:
            uses_pps_bus: Returns whether the device uses the PPS bus.
            temperature: Temperature manager for setpoint validation.
            set_payload: Builds a set-parameter payload.

        """
        self._uses_pps_bus = uses_pps_bus
        self._temperature = temperature
        self._set_payload = set_payload

    async def prepare_state(  # pylint: disable=too-many-arguments
        self,
        target_temperature: str | None,
        hvac_mode: int | None,
        circuit: int = 1,
        target_temperature_high: str | float | None = None,
        *,
        cooling_operating_mode: int | None = None,
    ) -> dict[str, Any]:
        """Prepare the thermostat state for setting.

        Args:
            target_temperature (str | None): The target temperature to set.
            hvac_mode (int | None): The HVAC mode to set as raw integer.
            circuit: The heating circuit number (1 or 2).
            target_temperature_high: The cooling comfort setpoint to set.
            cooling_operating_mode: The cooling circuit operating mode to set
                as raw integer.

        Returns:
            dict[str, Any]: The prepared state for the thermostat.

        """
        param_ids = self.thermostat_params(circuit)
        state: dict[str, Any] = {}
        if target_temperature is not None:
            await self._temperature.validate_target_temperature(
                target_temperature,
                circuit,
            )
            state.update(
                self._set_payload(param_ids["target_temperature"], target_temperature),
            )
        if target_temperature_high is not None:
            param_id = param_ids.get("target_temperature_high")
            if param_id is None:
                parameter_name = "target_temperature_high"
                raise BSBLANInvalidParameterError(parameter_name)
            await self._temperature.validate_target_temperature_high(
                target_temperature_high,
                circuit,
            )
            state.update(
                self._set_payload(param_id, str(target_temperature_high)),
            )
        if hvac_mode is not None:
            self.validate_hvac_mode(hvac_mode)
            hvac_value = str(hvac_mode)
            if self._uses_pps_bus():
                hvac_value = Validation.PPS_HVAC_MODE_TO_BSBLAN[hvac_mode]
            state.update(
                self._set_payload(param_ids["hvac_mode"], hvac_value),
            )
        if cooling_operating_mode is not None:
            param_id = param_ids.get("cooling_operating_mode")
            if param_id is None:
                parameter_name = "cooling_operating_mode"
                raise BSBLANInvalidParameterError(parameter_name)
            self.validate_cooling_operating_mode(cooling_operating_mode)
            state.update(
                self._set_payload(param_id, str(cooling_operating_mode)),
            )
        return state

    def thermostat_params(self, circuit: int) -> dict[str, str]:
        """Return thermostat write parameters for the active bus type."""
        if self._uses_pps_bus():
            return {"target_temperature": "15004", "hvac_mode": "15000"}
        return CircuitConfig.THERMOSTAT_PARAMS[circuit]

    def validate_hvac_mode(self, hvac_mode: int) -> None:
        """Validate the HVAC mode.

        Args:
            hvac_mode (int): The HVAC mode to validate. BSB/LPB accepts 0-3;
                PPS accepts 0, 1, and 3.

        Raises:
            BSBLANInvalidParameterError: If the HVAC mode is invalid.

        """
        valid_modes = (
            Validation.PPS_HVAC_MODES if self._uses_pps_bus() else Validation.HVAC_MODES
        )
        if hvac_mode not in valid_modes:
            raise BSBLANInvalidParameterError(str(hvac_mode))

    def validate_cooling_operating_mode(self, cooling_operating_mode: int) -> None:
        """Validate the cooling circuit operating mode.

        Args:
            cooling_operating_mode (int): The mode to validate. Valid values
                are 0=Protection, 1=Automatic, 2=Reduced, 3=Comfort.

        Raises:
            BSBLANInvalidParameterError: If the mode is invalid.

        """
        if cooling_operating_mode not in Validation.COOLING_OPERATING_MODES:
            raise BSBLANInvalidParameterError(str(cooling_operating_mode))
