"""Test BSBLAN constants module."""

import pytest

import bsblan
import bsblan.constants
from bsblan.constants import (
    API_V1,
    API_V3,
    BASE_HOT_WATER_PARAMS,
    BSBLAN_HVAC_ACTION_COOLING,
    BSBLAN_HVAC_ACTION_DEFROSTING,
    BSBLAN_HVAC_ACTION_DRYING,
    BSBLAN_HVAC_ACTION_FAN,
    BSBLAN_HVAC_ACTION_HEATING,
    BSBLAN_HVAC_ACTION_OFF,
    BSBLAN_HVAC_ACTION_PREHEATING,
    HOT_WATER_CONFIG_PARAMS,
    HOT_WATER_ESSENTIAL_PARAMS,
    HOT_WATER_SCHEDULE_PARAMS,
    build_api_config,
)


@pytest.mark.parametrize(
    ("version", "expected_includes", "expected_excludes"),
    [
        (
            "v1",
            {"700", "710", "714", "730"},  # hvac_mode, target_temp, min_temp, v1_max
            {"770", "716"},  # v3_boost, v3_max_temp
        ),
        (
            "v3",
            {"700", "710", "714", "770", "716"},  # base + v3 extensions
            {"730"},  # v1_max_temp
        ),
        (
            "v5",  # Unknown version
            {"700", "710", "714"},  # only base parameters
            {"770", "730", "716"},  # no extensions
        ),
    ],
)
def test_build_api_config_versions(
    version: str,
    expected_includes: set[str],
    expected_excludes: set[str],
) -> None:
    """Test building API config for different versions."""
    config = build_api_config(version)

    # Check expected parameters are included
    for param_id in expected_includes:
        assert param_id in (
            config["heating"]
            | config["staticValues"]
            | config["device"]
            | config["sensor"]
            | config["hot_water"]
        ), f"Parameter {param_id} missing in {version} config"

    # Check excluded parameters are not included
    for param_id in expected_excludes:
        assert param_id not in (config["heating"] | config["staticValues"]), (
            f"Parameter {param_id} should not be in {version} config"
        )


@pytest.mark.parametrize(
    ("api_config", "should_have", "should_not_have"),
    [
        (API_V1, {"730"}, {"770", "716"}),  # V1 has 730, not 770/716
        (API_V3, {"770", "716"}, {"730"}),  # V3 has 770/716, not 730
    ],
)
def test_pre_built_api_configurations(
    api_config: dict[str, dict[str, str]],
    should_have: set[str],
    should_not_have: set[str],
) -> None:
    """Test that pre-built API configurations are correct."""
    all_params = set(api_config["heating"].keys()) | set(
        api_config["staticValues"].keys()
    )

    for param_id in should_have:
        assert param_id in all_params

    for param_id in should_not_have:
        assert param_id not in all_params


def test_hot_water_parameter_groups_completeness() -> None:
    """Test that hot water parameter groups cover all parameters."""
    all_grouped_params = (
        HOT_WATER_ESSENTIAL_PARAMS | HOT_WATER_CONFIG_PARAMS | HOT_WATER_SCHEDULE_PARAMS
    )

    # All BASE_HOT_WATER_PARAMS should be categorized into one of the groups
    all_base_param_ids = set(BASE_HOT_WATER_PARAMS.keys())
    assert all_grouped_params == all_base_param_ids


@pytest.mark.parametrize(
    ("group1", "group2"),
    [
        (HOT_WATER_ESSENTIAL_PARAMS, HOT_WATER_CONFIG_PARAMS),
        (HOT_WATER_ESSENTIAL_PARAMS, HOT_WATER_SCHEDULE_PARAMS),
        (HOT_WATER_CONFIG_PARAMS, HOT_WATER_SCHEDULE_PARAMS),
    ],
)
def test_hot_water_parameter_groups_no_overlap(
    group1: set[str],
    group2: set[str],
) -> None:
    """Test that hot water parameter groups don't overlap."""
    assert not (group1 & group2), f"Groups should not overlap: {group1 & group2}"


@pytest.mark.parametrize(
    ("group", "expected_count"),
    [
        (HOT_WATER_ESSENTIAL_PARAMS, 5),  # Current optimized count
        (HOT_WATER_CONFIG_PARAMS, 16),  # Configuration parameters
        (HOT_WATER_SCHEDULE_PARAMS, 8),  # Time program parameters
    ],
)
def test_hot_water_parameter_groups_expected_counts(
    group: set[str],
    expected_count: int,
) -> None:
    """Test that hot water parameter groups have expected counts."""
    assert len(group) == expected_count


def test_hot_water_parameter_groups_total_count() -> None:
    """Test that total grouped parameters match base parameters."""
    total_grouped = (
        len(HOT_WATER_ESSENTIAL_PARAMS)
        + len(HOT_WATER_CONFIG_PARAMS)
        + len(HOT_WATER_SCHEDULE_PARAMS)
    )
    assert total_grouped == len(BASE_HOT_WATER_PARAMS)


@pytest.mark.parametrize("version", ["v1", "v3"])
def test_api_config_structure(version: str) -> None:
    """Test that API config has required structure."""
    config = build_api_config(version)

    # Check all required sections exist
    required_sections = {"heating", "staticValues", "device", "sensor", "hot_water"}
    assert set(config.keys()) == required_sections

    # Check that each section is a dict with string keys and values
    for section_name, section in config.items():
        assert isinstance(section, dict)
        for key, value in section.items():
            assert isinstance(key, str), f"Key {key} in {section_name} not string"
            assert isinstance(value, str), f"Value {value} in {section_name} not string"


# ============================================================================
# HVAC Action Constants Tests (Parameter 8000)
# ============================================================================


class TestHVACActionConstants:
    """Tests for HVAC action status code constants."""

    def test_hvac_action_heating_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_HEATING is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_HEATING, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_HEATING)

    def test_hvac_action_cooling_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_COOLING is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_COOLING, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_COOLING)

    def test_hvac_action_preheating_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_PREHEATING is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_PREHEATING, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_PREHEATING)

    def test_hvac_action_drying_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_DRYING is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_DRYING, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_DRYING)

    def test_hvac_action_fan_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_FAN is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_FAN, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_FAN)

    def test_hvac_action_off_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_OFF is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_OFF, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_OFF)

    def test_hvac_action_defrosting_is_set_of_ints(self) -> None:
        """Test that BSBLAN_HVAC_ACTION_DEFROSTING is a set of integers."""
        assert isinstance(BSBLAN_HVAC_ACTION_DEFROSTING, set)
        assert all(isinstance(code, int) for code in BSBLAN_HVAC_ACTION_DEFROSTING)

    @pytest.mark.parametrize(
        ("action_set", "expected_count"),
        [
            (BSBLAN_HVAC_ACTION_HEATING, 19),
            (BSBLAN_HVAC_ACTION_PREHEATING, 3),
            (BSBLAN_HVAC_ACTION_DRYING, 1),
            (BSBLAN_HVAC_ACTION_FAN, 4),
            (BSBLAN_HVAC_ACTION_COOLING, 22),
            (BSBLAN_HVAC_ACTION_OFF, 11),
            (BSBLAN_HVAC_ACTION_DEFROSTING, 10),
        ],
    )
    def test_hvac_action_set_sizes(
        self, action_set: set[int], expected_count: int
    ) -> None:
        """Test that HVAC action sets have expected number of status codes."""
        assert len(action_set) == expected_count

    def test_hvac_action_sets_no_overlap(self) -> None:
        """Test that HVAC action sets don't have overlapping status codes."""
        all_sets = [
            BSBLAN_HVAC_ACTION_HEATING,
            BSBLAN_HVAC_ACTION_PREHEATING,
            BSBLAN_HVAC_ACTION_DRYING,
            BSBLAN_HVAC_ACTION_FAN,
            BSBLAN_HVAC_ACTION_COOLING,
            BSBLAN_HVAC_ACTION_OFF,
            BSBLAN_HVAC_ACTION_DEFROSTING,
        ]

        # Check each pair for overlap
        for i, set1 in enumerate(all_sets):
            for set2 in all_sets[i + 1 :]:
                overlap = set1 & set2
                assert not overlap, f"Sets overlap with codes: {overlap}"

    @pytest.mark.parametrize(
        ("status_code", "expected_set_name"),
        [
            # Heating codes
            (0x04, "HEATING"),  # Manual control active
            (0x72, "HEATING"),  # Heating operation comfort
            (0x74, "HEATING"),  # Heating operation reduced
            # Preheating codes
            (0x70, "PREHEATING"),  # Switch-on optimization
            (0x71, "PREHEATING"),  # Quick heat-up
            # Drying codes
            (0x66, "DRYING"),  # Screed function active
            # Fan codes
            (0x6E, "FAN"),  # Forced consumption
            # Cooling codes
            (0x7F, "COOLING"),  # Active cooling mode
            (0x80, "COOLING"),  # Passive cooling mode
            (0x88, "COOLING"),  # Cooling mode
            # Off codes
            (0x76, "OFF"),  # Off
            (0xA2, "OFF"),  # Heating operation off
            # Defrosting codes
            (0x7D, "DEFROSTING"),  # Defrost active
            (0x7E, "DEFROSTING"),  # Drip-off
        ],
    )
    def test_specific_status_codes_in_correct_set(
        self, status_code: int, expected_set_name: str
    ) -> None:
        """Test that specific well-known status codes are in the correct set."""
        set_mapping = {
            "HEATING": BSBLAN_HVAC_ACTION_HEATING,
            "PREHEATING": BSBLAN_HVAC_ACTION_PREHEATING,
            "DRYING": BSBLAN_HVAC_ACTION_DRYING,
            "FAN": BSBLAN_HVAC_ACTION_FAN,
            "COOLING": BSBLAN_HVAC_ACTION_COOLING,
            "OFF": BSBLAN_HVAC_ACTION_OFF,
            "DEFROSTING": BSBLAN_HVAC_ACTION_DEFROSTING,
        }
        expected_set = set_mapping[expected_set_name]
        assert status_code in expected_set, (
            f"Status code 0x{status_code:02X} should be in {expected_set_name}"
        )

    def test_hvac_action_constants_are_exported(self) -> None:
        """Test that HVAC action constants are exported from bsblan package."""
        # Verify they are exported and are the same objects
        assert (
            bsblan.BSBLAN_HVAC_ACTION_HEATING
            is bsblan.constants.BSBLAN_HVAC_ACTION_HEATING
        )
        assert (
            bsblan.BSBLAN_HVAC_ACTION_COOLING
            is bsblan.constants.BSBLAN_HVAC_ACTION_COOLING
        )
        assert (
            bsblan.BSBLAN_HVAC_ACTION_PREHEATING
            is bsblan.constants.BSBLAN_HVAC_ACTION_PREHEATING
        )
        assert (
            bsblan.BSBLAN_HVAC_ACTION_DRYING
            is bsblan.constants.BSBLAN_HVAC_ACTION_DRYING
        )
        assert bsblan.BSBLAN_HVAC_ACTION_FAN is bsblan.constants.BSBLAN_HVAC_ACTION_FAN
        assert bsblan.BSBLAN_HVAC_ACTION_OFF is bsblan.constants.BSBLAN_HVAC_ACTION_OFF
        assert (
            bsblan.BSBLAN_HVAC_ACTION_DEFROSTING
            is bsblan.constants.BSBLAN_HVAC_ACTION_DEFROSTING
        )
