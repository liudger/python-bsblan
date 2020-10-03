"""Models for BSB-Lan."""

import attr


class State:
    """Object holding the BSBlan state."""

    heating_circuit1 = [
        700,  # current_hvac_mode
        701,  # test, needs to filter this out
        732,  # test, also filter this out for now
        710,  # target_temperature
        711,  # maximum_temperature
        712,  # reduced_temperature
        714,  # frost_protection_temp
        730,  # changeover_temperature
        8000,  # status_heating_circuit1
        8740,  # current_temperature room1
    ]

    heating_circuit2 = [
        1000,
        1010,
        1011,
        1012,
        1014,
        1030,
        8001,  # status_heating_circuit2
        8770,
    ]

    @staticmethod
    def from_dict(data: dict):
        """Return State object from BSBLan API response."""

        KEYS_TO_STATE = {
            "700": "current_hvac_mode",
            "710": "target_temperature",
            "902": "target_temperature_high",
            "711": "max_temp",  # comfort max temp
            "712": "target_temperature_low",
            "714": "min_temp",  # frost_protection_temp
            "730": "changeover_temperature",  # changeover_temperature
            "8000": "status_heating_circuit1",
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

        # print(f"new_dict keys:{new_dict}")
        return RETURN_CIRCUIT1_DICT


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


class Params:
    """Object holding all parameters for BSBLan."""

    # could be just a list
    heatingcircuit1 = {
        "Parameter": {
            700: "value",  # current_hvac_mode
            701: "value",  # test, needs to filter this out
            732: "value",  # test, also filter this out for now
            710: "value",  # target_temperature
            711: "value",  # maximum_temperature
            712: "value",  # reduced_temperature
            714: "value",  # frost_protection_temp
            730: "value",  # changeover_temperature
            8000: ["value", "desc"],  # status_heating_circuit1
            8740: ["value", "unit"],  # current_temperature room1
        }
    }

    heatingcircuit2 = {
        "Parameter": {
            1000: "value",
            1010: "value",
            1011: "value",
            1012: "value",
            1014: "value",
            1030: "value",
            8001: ["value", "desc"],  # status_heating_circuit2
            8770: ["value", "unit"],  # current_temperature room2
        }
    }

    status_params = {
        "Parameter": {
            8002: "value",
            8003: ["value", "desc"],  # status_dhw
            8006: ["value", "desc"],  # status_heatpump
        }
    }

    diagnostic_params = {
        "Parameter": {
            8700: "value",  # Diagnosis consumer - Outside temp sensor local: 14.3 °C
            8701: "value",  # Diagnosis consumer - Außentemperatur Minimum: -7.8 °C
            8702: "value",  # Diagnosis consumer - Außentemperatur Maximum: 42.0 °C
            8703: "value",  # Diagnosis consumer - Outside temp attenuated: 14.8 °C
            8704: "value",  # Diagnosis consumer - Outside temp composite: 13.9 °C
        }
    }

    # 8700 Diagnosis consumer - Outside temp sensor local: 13.7 °C
    # 8705 Diagnosis consumer - Außentemperatur LPB: error 7 (parameter not supported)
    # 8720 Diagnosis consumer - Relative Raumfeuchte: --- %
    # 8721 Diagnosis consumer - Raumtemperatur: --- °C
    # 8722 Diagnosis consumer - Taupunkttemperatur: --- °C
    # 8730 Diagnosis consumer - Heizkreispumpe Q2: 0 - Off
    # 8731 Diagnosis consumer - Heizkreismischer Auf Y1: ---
    # 8732 Diagnosis consumer - Heizkreismischer Zu Y2: ---
    # 8735 Diagnosis consumer - Drehzahl Heizkreispumpe 1: --- %
    # 8740 Diagnosis consumer - Room temp 1 actual value: 18.3 °C
    # 8741 Diagnosis consumer - Room temp setpoint current: 17.5 °C
    # 8742 Diagnosis consumer - Raumtemperatur 1 Modell: 16.0 °C
    # 8743 Diagnosis consumer - Flow temp actual value heat circuit 1: --- °C
    # 8744 Diagnosis consumer - Flow temperature setpoint H1: --- °C
    # 8749 Diagnosis consumer - Raumthermostat 1: 0 - Kein Bedarf
    # 8750 Diagnosis consumer - Pump speed: 0 %
    # 8751 Diagnosis consumer - Kühlkreispumpe Q24: 0100 - unknown type
    # 8752 Diagnosis consumer - Kühlkreismischer Auf Y23: 0100 - unknown type
    # 8753 Diagnosis consumer - Kühlkreismischer Zu Y24: 0100 - unknown type
    # 8754 Diagnosis consumer - Umlenkventil Kühlen Y21: 0100 - unknown type
    # 8756 Diagnosis consumer - Vorlauftemperatur Kühlen 1: --- °C
    # 8757 Diagnosis consumer - Vorlaufsollwert Kühlen1: --- °C
    # 8760 Diagnosis consumer - Heizkreispumpe 2: ---
    # 8761 Diagnosis consumer - Heizkreismischer 2 Auf: ---
    # 8762 Diagnosis consumer - Heizkreismischer 2 Zu: ---
    # 8765 Diagnosis consumer - Drehzahl Heizkreispumpe 2: --- %
    # 8770 Diagnosis consumer - Room temp 2 actual value: --- °C
    # 8771 Diagnosis consumer - Room temp setpoint actual HC2: --- °C
    # 8772 Diagnosis consumer - Raumtemperatur 2 Modell: --- °C
    # 8773 Diagnosis consumer - Flow temp actual value heat circuit 2: --- °C
    # 8774 Diagnosis consumer - Flow temperature setpoint H2: --- °C
    # 8779 Diagnosis consumer - Raumthermostat 2: 0 - Kein Bedarf
    # 8790 Diagnosis consumer - Heizkreispumpe 3/P: ---
    # 8791 Diagnosis consumer - Heizkreismischer 3/P Auf: ---
    # 8792 Diagnosis consumer - Heizkreismischer 3/P Zu: ---
    # 8795 Diagnosis consumer - Drehzahl Heizkreispumpe 3/P: --- %
    # 8800 Diagnosis consumer - Raumtemperatur 3/P: --- °C
    # 8801 Diagnosis consumer - Raumsollwert 3/P: --- °C
    # 8802 Diagnosis consumer - Raumtemperatur 3/P Modell: --- °C
    # 8803 Diagnosis consumer - Vorlauftemperatur 3/P: --- °C
    # 8804 Diagnosis consumer - Vorlaufsollwert 3/P: --- °C
    # 8809 Diagnosis consumer - Raumthermostat 3/P: 0 - Off
    # 8820 Diagnosis consumer - Trinkwasserpumpe Q3: 0 - Off
    # 8821 Diagnosis consumer - Elektroeinsatz TWW K6: 0 - Off
    # 8825 Diagnosis consumer - Drehzahl Trinkwasserpumpe: --- %
    # 8826 Diagnosis consumer - Drehzahl TWW Zw'kreispumpe: --- %
    # 8827 Diagnosis consumer - Drehzahl Dl'erhitzerpumpe: --- %
    # 8830 Diagnosis consumer - DHW temperature actual value top (B3): 42.7 °C
    # 8831 Diagnosis consumer - Dhw temp setpoint current: 10.0 °C
    # 8832 Diagnosis consumer - Trinkwassertemperatur 2: --- °C
    # 8835 Diagnosis consumer - TWW Zirkulationstemperatur: --- °C
    # 8836 Diagnosis consumer - DHW charging temperature: --- °C
    # 8840 Diagnosis consumer - Betr’stunden TWW-Pumpe: 516 h
    # 8841 Diagnosis consumer - Startzähler TWW-Pumpe: 926
    # 8842 Diagnosis consumer - Betr’stunden Elektro TWW: 3735 h
    # 8843 Diagnosis consumer - Startzähler Elektro TWW: 833
    # 8850 Diagnosis consumer - TWW Vorreglertemperatur: --- °C
    # 8851 Diagnosis consumer - TWW Vorreglersollwert: --- °C
    # 8852 Diagnosis consumer - TWW Durchl'erhitzertemp: --- °C
    # 8853 Diagnosis consumer - TWW Durchl'erhitzersollwert: --- °C
    # 8860 Diagnosis consumer - Trinkwasserdurchfluss: error 7 (parameter not supported)
    # 8875 Diagnosis consumer - Vorlaufsollwert VK1: --- °C
    # 8885 Diagnosis consumer - Vorlaufsollwert VK2: --- °C
    # 8900 Diagnosis consumer - Schwimmbadtemperatur: --- °C
    # 8901 Diagnosis consumer - Schwimmbadsollwert: --- °C
    # 8930 Diagnosis consumer - Vorreglertemperatur: --- °C
    # 8931 Diagnosis consumer - Vorreglersollwert: --- °C
    # 8950 Diagnosis consumer - Process signal segment flow: 22.8 °C
    # 8951 Diagnosis consumer - Schienenvorlaufsollwert: --- °C
    # 8952 Diagnosis consumer - Process signal segment return: --- °C
    # 8957 Diagnosis consumer - Schienenvorl'sollwert Kälte: --- °C
    # 8962 Diagnosis consumer - Leistungssollwert Schiene: --- %
    # 8980 Diagnosis consumer - Buffer temp actual value top (B4): --- °C
    # 8981 Diagnosis consumer - Pufferspeichersollwert: --- °C
    # 8982 Diagnosis consumer - Pufferspeichertemperatur 2: --- °C
    # 8983 Diagnosis consumer - Pufferspeichertemperatur 3: --- °C
    # 8984 Diagnosis consumer - Pufferspeichersollwert Reset?: 010000 - unknown type
    # 9000 Diagnosis consumer - Vorlaufsollwert H1: --- °C
    # 9001 Diagnosis consumer - Vorlaufsollwert H2: --- °C
    # 9004 Diagnosis consumer - Vorlaufsollwert H3: --- °C
    # 9005 Diagnosis consumer - Wasserdruck H1: --- bar
    # 9006 Diagnosis consumer - Wasserdruck H2: --- bar
    # 9009 Diagnosis consumer - Wasserdruck H3: --- bar

    # 8002 Status - Status Heizkreis P: 0 - ---
    # 8004 Status - Status Kühlkreis 1: 134 - not found
    # 8005 Status - Status boiler: error 7 (parameter not supported)
    # 8006 Status - Status Wärmepumpe: 51 - Keine Anforderung
    # 8007 Status - Status solar: 0 - ---
    # 8008 Status - Status Feststoffkessel: 0 - ---
    # 8009 Status - Status Brenner: error 7 (parameter not supported)
    # 8010 Status - Status Pufferspeicher: 0 - ---
    # 8011 Status - Status Schwimmbad: 0 - ---
    # 8022 Status - Status Zusatzerzeuger: 0 - ---
    # 8025 Status - Status Kühlkreis 2: 0 - not found

    # "Parameter": "700,710,711,712,714,730,8000,8002,8006,8740"

    # hotwater
    # 8003 Status - Status DHW: 99 - Geladen, Nenntemperatur
    # 1601 DHW - Manueller TWW-Push: 0 - Off
    # 1602 DHW - TWW Status: 01000101
    # 1610 DHW - DHW temperature nominal setpoint: 50.0 °C
    # 1612 DHW - DHW temperature reduced setpoint: 10.0 °C
    # 1614 DHW - TWW Nennsollwert Maximum: 65.0 °C
    # 1620 DHW - DHW release: 2 - Zeitprogramm 4/TWW
    # 1630 DHW - TWW Ladevorrang: 0 - Absolut
    # 1640 DHW - Legionella function: 2 - Fixer Wochentag
    # 1641 DHW - Legionella function periodicity: 7 Tage
    # 1642 DHW - Legionella function day: 6 - Samstag
    # 1644 DHW - Time for legionella function: 12:00
    # 1645 DHW - Legionella function setpoint: 60.0 °C
    # 1646 DHW - Dwelling time at legionella function setpoint: 30 min
    # 1647 DHW - Circul. pump operation during legionella func: 0 - Off
    # 1660 DHW - DHW circulating pump release: 2 - Trinkwasser Freigabe
    # 1661 DHW - DHW circulating pump cycling : 0 - Off
    # 1663 DHW - Zirkulations Sollwert: 45.0 °C
    # 1680 DHW - Trinkwasser Betriebsartumschaltung: 1 - Off

    # We need a lit of params for each device we want to get

    # outside temperature
    # 8700 Diagnosis consumer - Outside temp sensor local: 14.3 °C

    # 8002 Status - Status Heizkreis P: 0 - ---
    # 8006 Status - Status Wärmepumpe: 51 - Keine Anforderung
