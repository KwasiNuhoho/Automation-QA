"""
Setup file to read product information.

This file has been created for use in Bang & Olufsen A/S
"""
from typing import Any
import ipaddress
import re

MAC_ADDRESS_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# Reasonable RSSI (signal strength) range in dBm for a Wi-Fi connection.
# Above 0 is not physically meaningful, and below -100 is effectively
# no usable signal.
MIN_RSSI = -100
MAX_RSSI = 0


def validate_setup(data: dict[str, Any]) -> None:
    required_fields = [
        "device_id",
        "ble_connected",
        "wifi_provisioned",
        "ssid",
        "ip_address",
        "mac_address",
        "status",
    ]

    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    ipaddress.ip_address(data["ip_address"])

    assert data["ble_connected"] is True
    assert data["wifi_provisioned"] is True
    assert data["status"] == "online"


def is_wifi_setup_successful(data: dict[str, Any]) -> bool:
    return (
        data["ble_connected"]
        and data["wifi_provisioned"]
        and data["status"] == "online"
    )


def validate_mac_address(data: dict[str, Any]) -> None:
    """Check that the device's MAC address is present and well-formed."""
    mac = data.get("mac_address", "")
    assert MAC_ADDRESS_RE.match(mac), f"Invalid MAC address format: {mac}"


def validate_signal_strength(data: dict[str, Any]) -> None:
    """Check that the reported Wi-Fi signal strength (RSSI) is present
    and falls within a physically reasonable range. This ties to the
    'weak signal' onboarding risk: a device that reports an
    out-of-range or missing RSSI value cannot be trusted to tell the
    customer when they are too far from the router.
    """
    rssi = data.get("rssi")
    assert rssi is not None, "Missing rssi field"
    assert MIN_RSSI <= rssi <= MAX_RSSI, f"RSSI out of expected range: {rssi}"