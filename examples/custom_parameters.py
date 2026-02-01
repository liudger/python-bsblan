"""Example demonstrating custom sensor/parameter reading.

This example shows how to use the new read_parameter() and
read_parameter_by_name() methods to fetch individual custom parameters.
"""

import asyncio
import os

from bsblan import BSBLAN, BSBLANConfig


async def main() -> None:
    """Demonstrate custom parameter reading."""
    # Initialize the client from environment variables or defaults
    config = BSBLANConfig(
        host=os.getenv("BSBLAN_HOST", "192.168.1.100"),
        username=os.getenv("BSBLAN_USER"),
        password=os.getenv("BSBLAN_PASS"),
    )

    async with BSBLAN(config) as client:
        # Initialize the API
        await client.initialize()

        print("=" * 60)
        print("Reading Custom Parameters")
        print("=" * 60)

        # Example 1: Read a single parameter by ID
        print("\n1. Reading parameter by ID (8740 - current temperature)")
        temp = await client.read_parameter("8740")
        if temp:
            print(f"   Value: {temp.value} {temp.unit}")
            print(f"   Name: {temp.name}")
            print(f"   Description: {temp.desc}")
        else:
            print("   Parameter not found or not supported")

        # Example 2: Read a single parameter by name
        print("\n2. Reading parameter by name (current_temperature)")
        temp = await client.read_parameter_by_name("current_temperature")
        if temp:
            print(f"   Value: {temp.value} {temp.unit}")
            print(f"   Data Type: {temp.data_type}")
        else:
            print("   Parameter not found or not supported")

        # Example 3: Read HVAC mode (ENUM type)
        print("\n3. Reading HVAC mode (700 - operating mode)")
        hvac_mode = await client.read_parameter("700")
        if hvac_mode:
            print(f"   Value: {hvac_mode.value}")
            print(f"   Description: {hvac_mode.desc}")
            print(f"   Unit: {hvac_mode.unit}")
        else:
            print("   Parameter not found or not supported")

        # Example 4: Read multiple custom parameters
        print("\n4. Reading multiple custom parameters")
        param_ids = ["8740", "8700", "700"]  # temperature, outside temp, mode
        for param_id in param_ids:
            param = await client.read_parameter(param_id)
            if param:
                print(f"   {param_id}: {param.value} {param.unit} ({param.name})")

        # Example 5: Check if parameter exists before using it
        print("\n5. Safe parameter reading with existence check")
        outside_temp = await client.read_parameter_by_name("outside_temperature")
        if outside_temp and outside_temp.value != "---":
            print(f"   Outside temperature: {outside_temp.value} {outside_temp.unit}")
        else:
            print("   Outside temperature sensor not available")

        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
