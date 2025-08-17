"""Test BSBLAN constants module."""

import pytest

from bsblan.constants import (
    API_V1,
    API_V3,
    BASE_HOT_WATER_PARAMS,
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
