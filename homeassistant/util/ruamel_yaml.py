"""ruamel.yaml utility functions."""
import logging
import os
from os import O_CREAT, O_TRUNC, O_WRONLY
from stat import ST_MODE, ST_UID, ST_GID
from ruamel.yaml import YAML
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import YAMLError
from collections import OrderedDict
from typing import Union, List, Dict

from homeassistant.util.yaml import _secret_yaml
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name


class UnsupportedYamlError(HomeAssistantError):
    """Unsupported YAML."""


class WriteError(HomeAssistantError):
    """Error writing the data."""


def _include_yaml(constructor, node) -> JSON_TYPE:
    """Load another YAML file and embeds it using the !include tag.

    Example:
        device_tracker: !include device_tracker.yaml
    """
    fname = os.path.join(os.path.dirname(constructor.name), node.value)
    return load_yaml(fname, False)


def _yaml_unsupported(constructor, node):
    raise UnsupportedYamlError(
        'Unsupported YAML, you can not use {} in {}'
        .format(node.tag, os.path.basename(constructor.name)))


def object_to_yaml(data: JSON_TYPE) -> str:
    """Create yaml string from object."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    from ruamel.yaml.compat import StringIO
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    stream = StringIO()
    try:
        yaml.dump(data, stream)
        return stream.getvalue()
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def yaml_to_object(data: str) -> JSON_TYPE:
    """Create object from yaml string."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    try:
        return yaml.load(data)
    except YAMLError as exc:
        _LOGGER.error("YAML error: %s", exc)
        raise HomeAssistantError(exc)


def load_yaml(fname: str, rt: bool) -> JSON_TYPE:
    """Load a YAML file."""
    if rt:
        yaml = YAML(typ='rt')
        yaml.preserve_quotes = True
    else:
        SafeConstructor.name = fname
        yaml = YAML(typ='safe')

    try:
        with open(fname, encoding='utf-8') as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        _LOGGER.error("YAML error in %s: %s", fname, exc)
        raise HomeAssistantError(exc)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise HomeAssistantError(exc)


def save_yaml(fname: str, data: JSON_TYPE):
    """Save a YAML file."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    yaml = YAML(typ='rt')
    yaml.indent(sequence=4, offset=2)
    tmp_fname = fname + "__TEMP__"
    try:
        file_stat = os.stat(fname)
        with open(os.open(tmp_fname, O_WRONLY | O_CREAT | O_TRUNC,
                  file_stat[ST_MODE]), 'w', encoding='utf-8') as temp_file:
            yaml.dump(data, temp_file)
        os.replace(tmp_fname, fname)
        try:
            os.chown(fname, file_stat[ST_UID], file_stat[ST_GID])
        except OSError:
            pass
    except YAMLError as exc:
        _LOGGER.error(str(exc))
        raise HomeAssistantError(exc)
    except OSError as exc:
        _LOGGER.exception('Saving YAML file %s failed: %s', fname, exc)
        raise WriteError(exc)
    finally:
        if os.path.exists(tmp_fname):
            try:
                os.remove(tmp_fname)
            except OSError as exc:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error("YAML replacement cleanup failed: %s", exc)


SafeConstructor.add_constructor(u'!secret', _secret_yaml)
SafeConstructor.add_constructor(u'!include', _include_yaml)
SafeConstructor.add_constructor(None, _yaml_unsupported)
