"""
Tests to validate WiFi and BLE connectivity.

This file has been created for use in Bang & Olufsen A/S
"""
from pathlib import Path
from typing import Any

import json
import pytest

from wifi_setup import (
    is_wifi_setup_successful,
    validate_mac_address,
    validate_setup,
    validate_signal_strength,
)


@pytest.fixture
def setup_data() -> dict[str, Any]:
    return json.loads(Path("connectivity_status.json").read_text())


def test_ble_connection_established(setup_data: dict[str, Any]) -> None:
    assert setup_data["ble_connected"] is True


def test_wifi_provisioning_successful(setup_data: dict[str, Any]) -> None:
    assert setup_data["wifi_provisioned"] is True


def test_valid_ip_address(setup_data: dict[str, Any]) -> None:
    validate_setup(setup_data)


def test_device_online(setup_data: dict[str, Any]) -> None:
    assert setup_data["status"] == "online"


def test_wifi_setup_complete(setup_data: dict[str, Any]) -> None:
    assert is_wifi_setup_successful(setup_data)


def test_ssid_is_not_empty(setup_data: dict[str, Any]) -> None:
    assert len(setup_data["ssid"]) > 0


# --- Additional tests ---

def test_device_id_is_not_empty(setup_data: dict[str, Any]) -> None:
    """A device with a missing or empty device_id cannot be told apart
    from other devices during onboarding, which matters most when
    several devices are being set up at the same time."""
    assert len(setup_data["device_id"]) > 0


def test_mac_address_is_valid(setup_data: dict[str, Any]) -> None:
    """The MAC address must be present and in the correct format,
    since it is often used to uniquely identify the device."""
    validate_mac_address(setup_data)


def test_signal_strength_is_within_range(setup_data: dict[str, Any]) -> None:
    """The reported RSSI (signal strength) must be present and within
    a physically reasonable range. This is a simple, cheap check that
    the device can actually warn a customer about a weak signal
    during onboarding."""
    validate_signal_strength(setup_data)


def test_setup_fails_without_wifi_provisioning() -> None:
    """Simulates the failure pattern from the device logs: BLE
    connected and credentials were sent, but Wi-Fi provisioning did
    not complete (e.g. a DHCP timeout). is_wifi_setup_successful()
    should correctly report this as not successful, even though BLE
    connected fine."""
    incomplete_setup = {
        "device_id": "KitchenSpeaker",
        "ble_connected": True,
        "wifi_provisioned": False,
        "ssid": "HomeWiFi",
        "ip_address": "0.0.0.0",
        "mac_address": "00:09:A7:12:34:42",
        "rssi": -55,
        "status": "setup_failed",
    }

    assert is_wifi_setup_successful(incomplete_setup) is False


def test_invalid_mac_address_is_rejected() -> None:
    """A malformed MAC address should fail validation instead of
    being silently accepted."""
    setup_data = {
        "device_id": "KitchenSpeaker",
        "ble_connected": True,
        "wifi_provisioned": True,
        "ssid": "HomeWiFi",
        "ip_address": "192.168.1.50",
        "mac_address": "not-a-mac-address",
        "rssi": -55,
        "status": "online",
    }

    with pytest.raises(AssertionError):
        validate_mac_address(setup_data)