"""Test the Met Éireann integration init."""
from homeassistant.components.met_eireann.const import DOMAIN
from homeassistant.config_entries import EntryState

from . import init_integration


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is EntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is EntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
