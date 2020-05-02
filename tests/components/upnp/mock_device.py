"""Mock device for testing purposes."""

from homeassistant.components.upnp.device import Device


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn):
        """Initialize mock device."""
        igd_device = object()
        super().__init__(igd_device)
        self._udn = udn
        self.added_port_mappings = []
        self.removed_port_mappings = []

    @classmethod
    async def async_create_device(cls, hass, ssdp_location):
        """Return self."""
        return cls("UDN")

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._udn

    @property
    def manufacturer(self) -> str:
        """Get manufacturer."""
        return "mock-manufacturer"

    @property
    def name(self) -> str:
        """Get name."""
        return "mock-name"

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return "mock-model-name"

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

    async def _async_add_port_mapping(
        self, external_port: int, local_ip: str, internal_port: int
    ) -> None:
        """Add a port mapping."""
        entry = [external_port, local_ip, internal_port]
        self.added_port_mappings.append(entry)

    async def _async_delete_port_mapping(self, external_port: int) -> None:
        """Remove a port mapping."""
        entry = external_port
        self.removed_port_mappings.append(entry)


