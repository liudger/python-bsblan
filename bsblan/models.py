"""Models for BSB-Lan."""

import attr


@attr.s(auto_attribs=True, frozen=True)
class State:
    """Object holding the BSBlan state."""

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

    current_havoc_mode: str
    current_heatpump_mode: str
    current_target_temperature: float
    current_temperature: float
    temperature_unit: str

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""
        # print(data)
        return State(
            current_havoc_mode=data["8000"]["desc"],
            current_heatpump_mode=data["8006"]["desc"],
            current_target_temperature=data["710"]["value"],
            current_temperature=data["8740"]["value"],
            temperature_unit=data["8740"]["unit"],
        )


@attr.s(auto_attribs=True, frozen=True)
class Thermostat:
    """Object holding the BSBlan current temperature."""

    # how to know which temp (group1 or group2) to set

    target_temperature: float
    # hvac_modes: int

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""
        print(f"temp{data}")

        return Thermostat(
            target_temperature=data["710"]["status"],
            # hvac_modes=data["700"]["status"]
        )


@attr.s(auto_attribs=True, frozen=True)
class Info:
    """Object holding the BSBlan device info."""

    # try to get info from which device?
    # also to register with HomeAssistant

    pass
