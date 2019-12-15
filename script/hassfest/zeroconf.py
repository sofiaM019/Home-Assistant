"""Generate zeroconf file."""
from collections import OrderedDict, defaultdict
import json
from typing import Dict

from .model import Config, Integration

BASE = """
\"\"\"Automatically generated by hassfest.

To update, run python3 -m script.hassfest
\"\"\"

# fmt: off

ZEROCONF = {}

HOMEKIT = {}
""".strip()


def generate_and_validate(integrations: Dict[str, Integration]):
    """Validate and generate zeroconf data."""
    service_type_dict = defaultdict(list)
    homekit_dict = {}

    for domain in sorted(integrations):
        integration = integrations[domain]

        if not integration.manifest:
            continue

        service_types = integration.manifest.get("zeroconf", [])
        homekit = integration.manifest.get("homekit", {})
        homekit_models = homekit.get("models", [])

        if not service_types and not homekit_models:
            continue

        try:
            with open(str(integration.path / "config_flow.py")) as fp:
                content = fp.read()
                uses_discovery_flow = "register_discovery_flow" in content

                if (
                    service_types
                    and not uses_discovery_flow
                    and " async_step_zeroconf" not in content
                ):
                    integration.add_error(
                        "zeroconf", "Config flow has no async_step_zeroconf"
                    )
                    continue

                if (
                    homekit_models
                    and not uses_discovery_flow
                    and " async_step_homekit" not in content
                ):
                    integration.add_error(
                        "zeroconf", "Config flow has no async_step_homekit"
                    )
                    continue

        except FileNotFoundError:
            integration.add_error(
                "zeroconf",
                "Zeroconf info in a manifest requires a config flow to exist",
            )
            continue

        for service_type in service_types:
            service_type_dict[service_type].append(domain)

        for model in homekit_models:
            if model in homekit_dict:
                integration.add_error(
                    "zeroconf",
                    "Integrations {} and {} have overlapping HomeKit "
                    "models".format(domain, homekit_dict[model]),
                )
                break

            homekit_dict[model] = domain

    # HomeKit models are matched on starting string, make sure none overlap.
    warned = set()
    for key in homekit_dict:
        if key in warned:
            continue

        # n^2 yoooo
        for key_2 in homekit_dict:
            if key == key_2 or key_2 in warned:
                continue

            if key.startswith(key_2) or key_2.startswith(key):
                integration.add_error(
                    "zeroconf",
                    "Integrations {} and {} have overlapping HomeKit "
                    "models".format(homekit_dict[key], homekit_dict[key_2]),
                )
                warned.add(key)
                warned.add(key_2)
                break

    zeroconf = OrderedDict(
        (key, service_type_dict[key]) for key in sorted(service_type_dict)
    )
    homekit = OrderedDict((key, homekit_dict[key]) for key in sorted(homekit_dict))

    return BASE.format(json.dumps(zeroconf, indent=4), json.dumps(homekit, indent=4))


def validate(integrations: Dict[str, Integration], config: Config):
    """Validate zeroconf file."""
    zeroconf_path = config.root / "homeassistant/generated/zeroconf.py"
    config.cache["zeroconf"] = content = generate_and_validate(integrations)

    with open(str(zeroconf_path), "r") as fp:
        current = fp.read().strip()
        if current != content:
            config.add_error(
                "zeroconf",
                "File zeroconf.py is not up to date. " "Run python3 -m script.hassfest",
                fixable=True,
            )
        return


def generate(integrations: Dict[str, Integration], config: Config):
    """Generate zeroconf file."""
    zeroconf_path = config.root / "homeassistant/generated/zeroconf.py"
    with open(str(zeroconf_path), "w") as fp:
        fp.write(config.cache["zeroconf"] + "\n")
