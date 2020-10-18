"""Models for BSB-Lan."""

import json
from types import SimpleNamespace as Namespace

import attr


class State:
    """Convert Data to valid keys and convert to object attributes."""

    # list of parameter needed for climate device
    heating_circuit1 = [
        700,  # hvac_mode
        710,  # target_temperature
        711,  # target_temperature_high
        712,  # target_temperature_low
        714,  # min_temp
        730,  # max_temp
        900,  # hvac_action?
        8000,  # status_heating_circuit1
        8740,  # current_temperature room1
        8749,  # Raumthermostat1
    ]

    heating_circuit2 = [
        1000,
        1010,
        1011,
        1012,
        1014,
        1030,
        1200,
        8001,  # status_heating_circuit2
        8770,
    ]

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""

        # need the states fom homeassistant
        KEYS_TO_STATE = {
            "700": "hvac_mode",
            "710": "target_temperature",
            # "902": "target_temperature_high",
            "711": "target_temperature_high",  # comfort max temp
            "712": "target_temperature_low",
            "714": "min_temp",  # frost_protection_temp
            "730": "max_temp",  # changeover_temperature
            "900": "hvac_action",
            "8000": "status_heatingcircuit1",
            "8740": "current_temperature",
        }
        RETURN_CIRCUIT1_DICT = {}
        # only retrieve keys with valid values
        for k in KEYS_TO_STATE.keys() & data.keys():
            RETURN_CIRCUIT1_DICT[k] = data[k]
        # print(f"new_dict: {new_dict}")
        RETURN_CIRCUIT1_DICT = {
            KEYS_TO_STATE.get(k, k): v for k, v in RETURN_CIRCUIT1_DICT.items()
        }

        return json.loads(
            json.dumps(RETURN_CIRCUIT1_DICT), object_hook=lambda d: Namespace(**d)
        )


@attr.s(auto_attribs=True, frozen=True)
class Info:
    """Object holding the heatingsystem info."""

    controller_family: float
    controller_variant: float
    device_identification: str

    @staticmethod
    def from_dict(data: dict):
        """Return Info object from BSBLan API response."""
        # print(f"device {data}")

        return Info(
            controller_family=data["6225"]["value"],
            controller_variant=data["6226"]["value"],
            device_identification=data["6224"]["value"],
        )
