from pathlib import Path
from typing import Any
import json
import pytest

from mdns_discovery import (
    filter_devices_by_service,
    find_duplicate_hostnames,
    validate_device,
    validate_txt_records,
)


@pytest.fixture
def devices() -> list[dict[str, Any]]:
    return json.loads(Path('discovery_results.json').read_text())


def test_device_is_discoverable(devices: list[dict[str, Any]]) -> None:
    assert len(devices) > 0


def test_ip_addresses_are_valid(devices: list[dict[str, Any]]) -> None:
    for device in devices:
        validate_device(device)


def test_correct_service_advertised(devices: list[dict[str, Any]]) -> None:
    results = filter_devices_by_service(devices, '_speaker._tcp.local')
    assert len(results) > 0


# --- Additional tests ---

def test_txt_records_are_valid(devices: list[dict[str, Any]]) -> None:
    """Each device's TXT records must include a serial number, MAC
    address, firmware version and friendly name, and the MAC/firmware
    fields must be well-formed. Apps commonly key off these fields, so
    a malformed value here can be as damaging as a missing device."""
    for device in devices:
        validate_txt_records(device)


def test_port_in_valid_range(devices: list[dict[str, Any]]) -> None:
    """Port must be a valid TCP port number, not just any positive int."""
    for device in devices:
        assert 0 < device["port"] <= 65535


def test_no_duplicate_hostnames_in_mocked_results(
    devices: list[dict[str, Any]]
) -> None:
    """The current mocked discovery results should contain no hostname
    conflicts. If a fixture is ever updated to include multiple devices, 
    this test starts actually exercising the duplicate-detection logic."""
    duplicates = find_duplicate_hostnames(devices)
    assert not duplicates, f"Duplicate hostnames found: {duplicates}"


def test_duplicate_hostname_conflict_is_detected() -> None:
    """Simulates the 'duplicate hostnames or service conflicts' edge case
    from Part 1: two devices (e.g. cloned from the same factory image)
    advertising the same hostname. find_duplicate_hostnames() should
    flag this so the app/test suite can catch it rather than silently
    dropping one device."""
    conflicting_devices = [
        {
            "name": "Beosound Balance",
            "hostname": "Beosound-Balance-12345678.local",
            "ip_address": "192.168.1.123",
            "service": "_speaker._tcp.local",
            "port": 80,
        },
        {
            "name": "Beosound Balance (clone)",
            "hostname": "Beosound-Balance-12345678.local",
            "ip_address": "192.168.1.200",
            "service": "_speaker._tcp.local",
            "port": 80,
        },
    ]

    duplicates = find_duplicate_hostnames(conflicting_devices)
    assert duplicates == {"Beosound-Balance-12345678.local"}


def test_invalid_mac_address_is_rejected() -> None:
    """A malformed 'wa' (Wi-Fi MAC address) TXT field should fail
    validation rather than being silently accepted."""
    device = {
        "name": "Beosound Balance",
        "hostname": "Beosound-Balance-12345678.local",
        "ip_address": "192.168.1.123",
        "service": "_speaker._tcp.local",
        "port": 80,
        "txt_records": {
            "wa": "not-a-mac-address",
            "sn": "12345678",
            "pt": "2026-08-26T00:02:13Z",
            "fv": "6.3.0.31",
            "fn": "Beosound Balance",
        },
    }

    with pytest.raises(AssertionError):
        validate_txt_records(device)

