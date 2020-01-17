"""Models for BSB-Lan."""

import attr

# info to know what datatypes to expect for "value"
# "DataType" (
# 0 = Zahl,
# 1 = ENUM,
# 2 = Bit-Wert (Dezimalwert gefolgt von Bitmaske gefolgt von ausgewählter Option),
# 3 = Wochentag,
# 4 = Stunde/Minute,
# 5 = Datum/Uhrzeit,
# 6 = Tag/Monat,
# 7 = String,
# 8 = PPS-Uhrzeit (Wochentag, Stunde:Minute))
#
# &deg;C is the return of the unit


@attr.s(auto_attribs=True, frozen=True)
class State:
    """Object holding the BSBlan state."""

    current_havoc_mode: str
    current_heatpump_mode: str
    current_target_temperature: float
    current_temperature: float
    hvac_modes: str
    target_temperature: float
    temperature_unit: str

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""

        return State(
            current_havoc_mode=data["8000"]["desc"],
            current_heatpump_mode=data["8006"]["desc"],
            current_target_temperature=data["710"]["value"],
            current_temperature=data["8740"]["value"],
            hvac_modes=data["700"]["desc"],
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
