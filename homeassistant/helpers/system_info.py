"""Helper to gather system info."""
import os
import platform
from typing import Dict

from homeassistant.const import __version__ as current_version
from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util
from homeassistant.util.package import is_virtual_env
from .typing import HomeAssistantType


@bind_hass
async def async_get_system_info(hass: HomeAssistantType) -> Dict:
    """Return info about the system."""
    info_object = {
        'version': current_version,
        'dev': 'dev' in current_version,
        'hassio': hass.components.hassio.is_hassio(),
        'virtualenv': is_virtual_env(),
        'python_version': platform.python_version(),
        'docker': False,
        'arch': platform.machine(),
        'timezone': hass.config.time_zone,
        'os_name': platform.system(),
    }

    if platform.system() == 'Windows':
        info_object['os_version'] = platform.win32_ver()[0]
    elif platform.system() == 'Darwin':
        info_object['os_version'] = platform.mac_ver()[0]
    elif platform.system() == 'FreeBSD':
        info_object['os_version'] = platform.release()
    elif platform.system() == 'Linux':
        import distro
        linux_dist = await hass.async_add_executor_job(
            distro.linux_distribution, False)
        info_object['distribution'] = linux_dist[0]
        info_object['os_version'] = linux_dist[1]
        info_object['docker'] = os.path.isfile('/.dockerenv')

    return info_object
