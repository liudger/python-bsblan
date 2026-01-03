"""Test BSBLAN constants module."""

import pytest

import bsblan
import bsblan.constants
from bsblan.constants import (
    API_V1,
    API_V3,
    BASE_HOT_WATER_PARAMS,
    HOT_WATER_CONFIG_PARAMS,
    HOT_WATER_ESSENTIAL_PARAMS,
    HOT_WATER_SCHEDULE_PARAMS,
    HeatingCircuitStatus,
    HVACActionCategory,
    build_api_config,
    get_hvac_action_category,
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
# HVAC Action Enum Tests
# ============================================================================


class TestHVACActionCategory:
    """Tests for HVACActionCategory enum."""

    def test_hvac_action_category_values(self) -> None:
        """Test that HVACActionCategory has all expected values."""
        expected_categories = {
            "IDLE",
            "HEATING",
            "COOLING",
            "PREHEATING",
            "DRYING",
            "FAN",
            "OFF",
            "DEFROSTING",
        }
        actual_categories = {c.name for c in HVACActionCategory}
        assert actual_categories == expected_categories

    def test_hvac_action_category_idle_is_zero(self) -> None:
        """Test that IDLE is the default category (value 0)."""
        assert HVACActionCategory.IDLE == 0


class TestHeatingCircuitStatus:
    """Tests for HeatingCircuitStatus enum."""

    def test_heating_circuit_status_is_intenum(self) -> None:
        """Test that HeatingCircuitStatus is an IntEnum."""
        assert issubclass(HeatingCircuitStatus, int)

    @pytest.mark.parametrize(
        ("status", "expected_category"),
        [
            (HeatingCircuitStatus.HEATING_COMFORT, HVACActionCategory.HEATING),
            (HeatingCircuitStatus.HEATING_REDUCED, HVACActionCategory.HEATING),
            (HeatingCircuitStatus.MANUAL_CONTROL, HVACActionCategory.HEATING),
            (HeatingCircuitStatus.COOLING_ACTIVE, HVACActionCategory.COOLING),
            (HeatingCircuitStatus.COOLING_PASSIVE, HVACActionCategory.COOLING),
            (HeatingCircuitStatus.QUICK_HEATUP, HVACActionCategory.PREHEATING),
            (HeatingCircuitStatus.SWITCHON_OPTIMIZATION, HVACActionCategory.PREHEATING),
            (HeatingCircuitStatus.SCREED_FUNCTION, HVACActionCategory.DRYING),
            (HeatingCircuitStatus.FORCED_CONSUMPTION, HVACActionCategory.FAN),
            (HeatingCircuitStatus.OFF, HVACActionCategory.OFF),
            (HeatingCircuitStatus.HEATING_OFF, HVACActionCategory.OFF),
            (HeatingCircuitStatus.DEFROST, HVACActionCategory.DEFROSTING),
            (HeatingCircuitStatus.DRIP_OFF, HVACActionCategory.DEFROSTING),
        ],
    )
    def test_status_category_property(
        self, status: HeatingCircuitStatus, expected_category: HVACActionCategory
    ) -> None:
        """Test that status codes return correct category via property."""
        assert status.category == expected_category

    def test_from_value_known_code(self) -> None:
        """Test from_value returns correct enum for known codes."""
        status = HeatingCircuitStatus.from_value(0x72)
        assert status == HeatingCircuitStatus.HEATING_COMFORT

    def test_from_value_unknown_code(self) -> None:
        """Test from_value returns None for unknown codes."""
        status = HeatingCircuitStatus.from_value(0xFFFF)
        assert status is None

    def test_status_value_matches_hex(self) -> None:
        """Test that enum values match expected hex values."""
        assert HeatingCircuitStatus.HEATING_COMFORT.value == 0x72
        assert HeatingCircuitStatus.OFF.value == 0x76
        assert HeatingCircuitStatus.COOLING_ACTIVE.value == 0x7F
        assert HeatingCircuitStatus.DEFROST.value == 0x7D


class TestGetHvacActionCategory:
    """Tests for get_hvac_action_category function."""

    @pytest.mark.parametrize(
        ("status_code", "expected_category"),
        [
            (0x72, HVACActionCategory.HEATING),
            (0x7F, HVACActionCategory.COOLING),
            (0x71, HVACActionCategory.PREHEATING),
            (0x66, HVACActionCategory.DRYING),
            (0x6E, HVACActionCategory.FAN),
            (0x76, HVACActionCategory.OFF),
            (0x7D, HVACActionCategory.DEFROSTING),
        ],
    )
    def test_known_status_codes(
        self, status_code: int, expected_category: HVACActionCategory
    ) -> None:
        """Test that known status codes return correct category."""
        assert get_hvac_action_category(status_code) == expected_category

    def test_unknown_status_code_returns_idle(self) -> None:
        """Test that unknown status codes return IDLE."""
        assert get_hvac_action_category(0xFFFF) == HVACActionCategory.IDLE
        assert get_hvac_action_category(9999) == HVACActionCategory.IDLE

    def test_enums_are_exported_from_package(self) -> None:
        """Test that enum classes are exported from bsblan package."""
        assert bsblan.HeatingCircuitStatus is HeatingCircuitStatus
        assert bsblan.HVACActionCategory is HVACActionCategory
        assert bsblan.get_hvac_action_category is get_hvac_action_category
