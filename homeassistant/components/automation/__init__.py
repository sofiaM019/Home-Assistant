"""
homeassistant.components.automation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to setup simple automation rules via the config file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/automation/
"""
from datetime import datetime
import functools
import inspect
import logging
import yaml

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.const import CONF_PLATFORM
from homeassistant.components import logbook
from homeassistant.helpers.service import call_from_config

DOMAIN = 'automation'

DEPENDENCIES = ['group']

CONF_ALIAS = 'alias'
CONF_SERVICE = 'service'

CONF_CONDITION = 'condition'
CONF_ACTION = 'action'
CONF_TRIGGER = 'trigger'
CONF_CONDITION_TYPE = 'condition_type'

CONDITION_USE_TRIGGER_VALUES = 'use_trigger_values'
CONDITION_TYPE_AND = 'and'
CONDITION_TYPE_OR = 'or'

DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND

CUSTOM_AUTOMATIONS = []

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Sets up automation. """
    config_key = DOMAIN
    found = 1

    while config_key in config:
        # check for one block syntax
        if isinstance(config[config_key], dict):
            config_block = _migrate_old_config(config[config_key])
            name = config_block.get(CONF_ALIAS, config_key)
            _setup_automation(hass, config_block, name, config)

        # check for multiple block syntax
        elif isinstance(config[config_key], list):
            for list_no, config_block in enumerate(config[config_key]):
                name = config_block.get(CONF_ALIAS,
                                        "{}, {}".format(config_key, list_no))
                _setup_automation(hass, config_block, name, config)

        # any scalar value is incorrect
        else:
            _LOGGER.error('Error in config in section %s.', config_key)

        found += 1
        config_key = "{} {}".format(DOMAIN, found)

    return True


def activate(hass, config, domain):
    """ Activate the automations for specified domain """
    for auto_rule in CUSTOM_AUTOMATIONS:
        if auto_rule.domain == domain:
            try:
                success = auto_rule.activate(hass, config)
            except Exception:
                _LOGGER.exception('Error activating automation %s',
                                  auto_rule.alias)
                success = True

            if not success:
                _LOGGER.error('Error activating automation %s',
                              auto_rule.alias)


class Automation(object):
    """ Decorator for automation functions """

    hass = None

    def __init__(self, action):
        # store action and config
        self.action = action
        self.config = yaml.load(inspect.getdoc(action))
        self._activated = False
        self._last_run = None
        self._running = 0

        # register the automation
        module = inspect.getmodule(action)
        self._domain = module.DOMAIN
        CUSTOM_AUTOMATIONS.append(self)

        functools.update_wrapper(self, action)

    def __call__(self):
        """ Call the action """
        if not self.activated:
            return

        self._running += 1

        _LOGGER.info('Executing %s', self.alias)
        logbook.log_entry(self.hass, self.alias, 'has been triggered', DOMAIN)

        try:
            self.action(self)
        except Exception:
            _LOGGER.exception('Error running Python automation: %s',
                              self.alias)
        else:
            self._last_run = datetime.now()

        self._running -= 1

    @property
    def alias(self):
        """ The alias for the function """
        if CONF_ALIAS in self.config:
            return self.config[CONF_ALIAS]
        return None

    @property
    def domain(self):
        """ The domain to which this automation belongs """
        return self._domain

    @property
    def is_running(self):
        """ Boolean if the automation is running """
        return self._running > 0

    @property
    def num_running(self):
        """ Integer of how many instances of the automation are running """
        return self._running

    @property
    def activated(self):
        """ Boolean indicating if the automation has been activated """
        return self._activated

    @property
    def last_run(self):
        """ Datetime object of the last automation completion """
        return self._last_run

    def activate(self, hass, config):
        """ Activates the automation with HASS """
        self.hass = hass

        if self.activated:
            return True

        if CONF_CONDITION in self.config or CONF_CONDITION_TYPE in self.config:
            action = _process_if(hass, config, self.config, self.action)

            if action is None:
                return False
            self.action = action

        _process_trigger(hass, config, self.config.get(CONF_TRIGGER, []),
                         self.alias, self)

        self._activated = True
        return True


def _setup_automation(hass, config_block, name, config):
    """ Setup one instance of automation """

    action = _get_action(hass, config_block.get(CONF_ACTION, {}), name)

    if action is None:
        return False

    if CONF_CONDITION in config_block or CONF_CONDITION_TYPE in config_block:
        action = _process_if(hass, config, config_block, action)

        if action is None:
            return False

    _process_trigger(hass, config, config_block.get(CONF_TRIGGER, []), name,
                     action)
    return True


def _get_action(hass, config, name):
    """ Return an action based on a config. """

    if CONF_SERVICE not in config:
        _LOGGER.error('Error setting up %s, no action specified.', name)
        return None

    def action():
        """ Action to be executed. """
        _LOGGER.info('Executing %s', name)
        logbook.log_entry(hass, name, 'has been triggered', DOMAIN)

        call_from_config(hass, config)

    return action


def _migrate_old_config(config):
    """ Migrate old config to new. """
    if CONF_PLATFORM not in config:
        return config

    _LOGGER.warning(
        'You are using an old configuration format. Please upgrade: '
        'https://home-assistant.io/components/automation/')

    new_conf = {
        CONF_TRIGGER: dict(config),
        CONF_CONDITION: config.get('if', []),
        CONF_ACTION: dict(config),
    }

    for cat, key, new_key in (('trigger', 'mqtt_topic', 'topic'),
                              ('trigger', 'mqtt_payload', 'payload'),
                              ('trigger', 'state_entity_id', 'entity_id'),
                              ('trigger', 'state_before', 'before'),
                              ('trigger', 'state_after', 'after'),
                              ('trigger', 'state_to', 'to'),
                              ('trigger', 'state_from', 'from'),
                              ('trigger', 'state_hours', 'hours'),
                              ('trigger', 'state_minutes', 'minutes'),
                              ('trigger', 'state_seconds', 'seconds'),
                              ('action', 'execute_service', 'service'),
                              ('action', 'service_entity_id', 'entity_id'),
                              ('action', 'service_data', 'data')):
        if key in new_conf[cat]:
            new_conf[cat][new_key] = new_conf[cat].pop(key)

    return new_conf


def _process_if(hass, config, p_config, action):
    """ Processes if checks. """

    cond_type = p_config.get(CONF_CONDITION_TYPE,
                             DEFAULT_CONDITION_TYPE).lower()

    if_configs = p_config.get(CONF_CONDITION)
    use_trigger = if_configs == CONDITION_USE_TRIGGER_VALUES

    if use_trigger:
        if_configs = p_config[CONF_TRIGGER]

    if isinstance(if_configs, dict):
        if_configs = [if_configs]

    checks = []
    for if_config in if_configs:
        platform = _resolve_platform('if_action', hass, config,
                                     if_config.get(CONF_PLATFORM))
        if platform is None:
            continue

        check = platform.if_action(hass, if_config)

        # Invalid conditions are allowed if we base it on trigger
        if check is None and not use_trigger:
            return None

        checks.append(check)

    if cond_type == CONDITION_TYPE_AND:
        def if_action():
            """ AND all conditions. """
            if all(check() for check in checks):
                action()
    else:
        def if_action():
            """ OR all conditions. """
            if any(check() for check in checks):
                action()

    return if_action


def _process_trigger(hass, config, trigger_configs, name, action):
    """ Setup triggers. """
    if isinstance(trigger_configs, dict):
        trigger_configs = [trigger_configs]

    for conf in trigger_configs:
        platform = _resolve_platform('trigger', hass, config,
                                     conf.get(CONF_PLATFORM))
        if platform is None:
            continue

        if platform.trigger(hass, conf, action):
            _LOGGER.info("Initialized rule %s", name)
        else:
            _LOGGER.error("Error setting up rule %s", name)


def _resolve_platform(method, hass, config, platform):
    """ Find automation platform. """
    if platform is None:
        return None
    platform = prepare_setup_platform(hass, config, DOMAIN, platform)

    if platform is None or not hasattr(platform, method):
        _LOGGER.error("Unknown automation platform specified for %s: %s",
                      method, platform)
        return None

    return platform
