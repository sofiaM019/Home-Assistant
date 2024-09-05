"""Const file with mocked response."""

from fing_agent_api.models import DeviceResponse


def mocked_dev_resp_old_API():
    """Mock DeviceResponse from OLD API."""
    return DeviceResponse(
        {
            "devices": [
                {
                    "mac": "00:00:00:00:00:01",
                    "ip": ["192.168.50.1"],
                    "state": "UP",
                    "name": "FreeBSD router",
                    "type": "FIREWALL",
                    "make": "OPNsense",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
                {
                    "mac": "00:00:00:00:00:02",
                    "ip": ["192.168.50.2"],
                    "state": "UP",
                    "name": "Samsung The Frame 55",
                    "type": "TELEVISION",
                    "make": "Samsung",
                    "model": "The Frame 55",
                    "first_seen": "2024-08-26T14:03:31.497Z",
                    "last_changed": "2024-08-26T14:52:08.559Z",
                },
                {
                    "mac": "00:00:00:00:00:03",
                    "ip": ["192.168.50.3"],
                    "state": "UP",
                    "name": "PC_HOME",
                    "type": "COMPUTER",
                    "make": "Dell",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                    "last_changed": "2024-09-02T11:15:15.456Z",
                },
            ],
        }
    )


def mocked_dev_resp_new_API():
    """Mock DeviceResponse from NEW API."""
    return DeviceResponse(
        {
            "networkId": "TEST",
            "devices": [
                {
                    "mac": "00:00:00:00:00:01",
                    "ip": ["192.168.50.1"],
                    "state": "UP",
                    "name": "FreeBSD router",
                    "type": "FIREWALL",
                    "make": "OPNsense",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
                {
                    "mac": "00:00:00:00:00:02",
                    "ip": ["192.168.50.2"],
                    "state": "UP",
                    "name": "Samsung The Frame 55",
                    "type": "TELEVISION",
                    "make": "Samsung",
                    "model": "The Frame 55",
                    "first_seen": "2024-08-26T14:03:31.497Z",
                    "last_changed": "2024-08-26T14:52:08.559Z",
                },
                {
                    "mac": "00:00:00:00:00:03",
                    "ip": ["192.168.50.3"],
                    "state": "UP",
                    "name": "PC_HOME",
                    "type": "COMPUTER",
                    "make": "Dell",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                    "last_changed": "2024-09-02T11:15:15.456Z",
                },
            ],
        }
    )


def mocked_dev_resp_new_dev():
    """Mock DeviceResponse with one new device (followup of new_API)."""
    return DeviceResponse(
        {
            "networkId": "TEST",
            "devices": [
                {
                    "mac": "00:00:00:00:00:01",
                    "ip": ["192.168.50.1"],
                    "state": "UP",
                    "name": "FreeBSD router",
                    "type": "FIREWALL",
                    "make": "OPNsense",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
                {
                    "mac": "00:00:00:00:00:02",
                    "ip": ["192.168.50.2"],
                    "state": "UP",
                    "name": "Samsung The Frame 55",
                    "type": "TELEVISION",
                    "make": "Samsung",
                    "model": "The Frame 55",
                    "first_seen": "2024-08-26T14:03:31.497Z",
                    "last_changed": "2024-08-26T14:52:08.559Z",
                },
                {
                    "mac": "00:00:00:00:00:03",
                    "ip": ["192.168.50.3"],
                    "state": "UP",
                    "name": "PC_HOME",
                    "type": "COMPUTER",
                    "make": "Dell",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                    "last_changed": "2024-09-02T11:15:15.456Z",
                },
                {
                    "mac": "54:44:A3:5F:D0:38",
                    "ip": ["192.168.50.10"],
                    "state": "UP",
                    "name": "Samsung",
                    "type": "LOUDSPEAKER",
                    "make": "Samsung",
                    "model": "HW-S800B",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
            ],
        }
    )


def mocked_dev_resp_del_dev():
    """Mock DeviceResponse with 2 devices removed (followup of new_dev)."""
    return DeviceResponse(
        {
            "networkId": "TEST",
            "devices": [
                {
                    "mac": "00:00:00:00:00:01",
                    "ip": ["192.168.50.1"],
                    "state": "UP",
                    "name": "FreeBSD router",
                    "type": "FIREWALL",
                    "make": "OPNsense",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
                {
                    "mac": "54:44:A3:5F:D0:38",
                    "ip": ["192.168.50.10"],
                    "state": "UP",
                    "name": "Samsung",
                    "type": "LOUDSPEAKER",
                    "make": "Samsung",
                    "model": "HW-S800B",
                    "first_seen": "2024-08-26T13:28:57.927Z",
                },
            ],
        }
    )
