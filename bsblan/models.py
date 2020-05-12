"""Models for BSB-Lan."""

import attr


@attr.s(auto_attribs=True, frozen=True)
class State:
    """Object holding the BSBlan state."""

    current_hvac_mode: int
    current_temperature: float
    target_temperature: float
    temperature_unit: str

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""

        return State(
            current_hvac_mode=data["700"]["value"],
            current_temperature=data["8740"]["value"],
            target_temperature=data["710"]["value"],
            temperature_unit=data["8740"]["unit"],
        )


@attr.s(auto_attribs=True, frozen=True)
class Info:
    """Object holding the BSBlan device info."""

    controller_family: float
    controller_variant: float
    device_identification: str

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""
        # print(f"device {data}")

        return Info(
            controller_family=data["6225"]["value"],
            controller_variant=data["6226"]["value"],
            device_identification=data["6224"]["value"],
        )
