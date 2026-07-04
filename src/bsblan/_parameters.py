"""Low-level parameter lookup and read helpers for BSB-LAN."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .constants import ErrorMsg
from .exceptions import BSBLANError
from .models import EntityInfo

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .constants import APIConfig


class ParameterReader:
    """Resolve and read BSB-LAN parameters by ID or name."""

    def __init__(
        self,
        *,
        request: Callable[..., Awaitable[dict[str, Any]]],
        get_api_data: Callable[[], APIConfig | None],
    ) -> None:
        """Initialize the parameter reader.

        Args:
            request: Callable performing a client request.
            get_api_data: Callable returning the current API config data.

        """
        self._request = request
        self._get_api_data = get_api_data

    async def read_parameters(
        self,
        parameter_ids: list[str],
    ) -> dict[str, EntityInfo]:
        """Read specific parameters by their BSB-LAN parameter IDs.

        Args:
            parameter_ids: List of BSB-LAN parameter IDs to fetch.

        Returns:
            dict[str, EntityInfo]: Dictionary mapping parameter IDs to
                EntityInfo objects.

        Raises:
            BSBLANError: If no parameter IDs are provided or request fails.

        """
        if not parameter_ids:
            raise BSBLANError(ErrorMsg.NO_PARAMETER_IDS)

        # Request the parameters from the device
        params_string = ",".join(parameter_ids)
        response_data = await self._request(params={"Parameter": params_string})

        # Convert response to EntityInfo objects
        result: dict[str, EntityInfo] = {}
        for param_id in parameter_ids:
            if param_id in response_data:
                param_data = response_data[param_id]
                if param_data and isinstance(param_data, dict):
                    result[param_id] = EntityInfo.model_validate(param_data)

        return result

    def get_parameter_id(self, parameter_name: str) -> str | None:
        """Look up the parameter ID for a given parameter name.

        Args:
            parameter_name: The parameter name (e.g., "current_temperature").

        Returns:
            str | None: The parameter ID if found, None otherwise.

        """
        api_data = self._get_api_data()
        if not api_data:
            return None

        # Search through all sections for the parameter name
        for section_params in api_data.values():
            section_dict = cast("dict[str, str]", section_params)
            for param_id, param_name in section_dict.items():
                if param_name == parameter_name:
                    return param_id

        return None

    def get_parameter_ids(self, parameter_names: list[str]) -> dict[str, str]:
        """Look up parameter IDs for multiple parameter names.

        Args:
            parameter_names: List of parameter names to look up.

        Returns:
            dict[str, str]: Dictionary mapping parameter names to their IDs.
                Only includes parameters that were found.

        """
        result: dict[str, str] = {}
        for name in parameter_names:
            param_id = self.get_parameter_id(name)
            if param_id is not None:
                result[name] = param_id
        return result

    async def read_parameters_by_name(
        self,
        parameter_names: list[str],
    ) -> dict[str, EntityInfo]:
        """Read specific parameters by their names.

        Args:
            parameter_names: List of parameter names to fetch.

        Returns:
            dict[str, EntityInfo]: Dictionary mapping parameter names to
                EntityInfo objects. Only includes parameters that were found
                and had valid data.

        Raises:
            BSBLANError: If no parameter names are provided, no IDs could be
                resolved, or the client is not initialized.

        """
        if not parameter_names:
            raise BSBLANError(ErrorMsg.NO_PARAMETER_NAMES)

        if not self._get_api_data():
            raise BSBLANError(ErrorMsg.API_DATA_NOT_INITIALIZED)

        # Resolve names to IDs
        name_to_id = self.get_parameter_ids(parameter_names)

        if not name_to_id:
            unknown_params = ", ".join(parameter_names)
            msg = f"{ErrorMsg.PARAMETER_NAMES_NOT_RESOLVED}: {unknown_params}"
            raise BSBLANError(msg)

        # Fetch parameters by ID
        param_ids = list(name_to_id.values())
        id_results = await self.read_parameters(param_ids)

        # Convert back to name-keyed dictionary
        # id_to_name maps param_id -> param_name for requested params only
        id_to_name = {v: k for k, v in name_to_id.items()}
        return {
            id_to_name[param_id]: entity_info
            for param_id, entity_info in id_results.items()
            if param_id in id_to_name
        }
