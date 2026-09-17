from typing import Any
import ipaddress
import re

MAC_ADDRESS_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
FIRMWARE_VERSION_RE = re.compile(r"^\d+(\.\d+){2,3}$")

REQUIRED_TXT_FIELDS = ["sn", "wa", "fv", "fn"]


def validate_device(device: dict[str, Any]) -> None:
    required_fields = [
        "name",
        "hostname",
        "ip_address",
        "service",
        "port",
    ]

    for field in required_fields:
        assert field in device, f"Missing field: {field}"

    ipaddress.ip_address(device["ip_address"])

    assert device["hostname"].endswith(".local")
    assert device["service"] == "_speaker._tcp.local"
    assert 0 < device["port"] <= 65535, f"Port out of valid range: {device['port']}"


def validate_txt_records(device: dict[str, Any]) -> None:
    """Validate the TXT record payload advertised alongside the mDNS service.

    Checks that the required fields are present and non-empty, and that
    the MAC address (`wa`) and firmware version (`fv`) fields are
    well-formed, since these are frequently used by client apps for
    device identification and compatibility checks.
    """
    txt = device.get("txt_records", {})

    for field in REQUIRED_TXT_FIELDS:
        assert field in txt and txt[field], f"Missing or empty TXT field: {field}"

    assert MAC_ADDRESS_RE.match(txt["wa"]), f"Invalid MAC address format: {txt['wa']}"
    assert FIRMWARE_VERSION_RE.match(
        txt["fv"]
    ), f"Invalid firmware version format: {txt['fv']}"


def find_duplicate_hostnames(devices: list[dict[str, Any]]) -> set[str]:
    """Return the set of hostnames that appear more than once in `devices`.

    Useful for detecting hostname/service conflicts, e.g. two devices
    that were cloned from the same factory image and never re-keyed.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()

    for device in devices:
        hostname = device["hostname"]
        if hostname in seen:
            duplicates.add(hostname)
        seen.add(hostname)

    return duplicates


def filter_devices_by_service(
    devices: list[dict[str, Any]],
    service: str,
) -> list[dict[str, Any]]:
    return [d for d in devices if d["service"] == service]
