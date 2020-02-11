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

    away_mode: int
    cooling_setpoint: float
    current_heatpump_mode: str
    current_hvac_mode: int
    current_hvac_operation: str
    current_temperature: float
    target_temperature: float
    temperature_unit: str
    switching_mode: bool

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""

        # no desc if it needs automatic translation
        return State(
            away_mode=data["703"]["value"],  # 256=home , 257=away
            cooling_setpoint=data["912"]["value"],
            current_heatpump_mode=data["8006"]["desc"],
            current_hvac_mode=data["700"]["value"],
            current_hvac_operation=data["8000"]["desc"],  # this can also stay
            current_temperature=data["8740"]["value"],
            target_temperature=data["710"]["value"],
            temperature_unit=data["8740"]["unit"],
            switching_mode=data["969"]["value"],
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
