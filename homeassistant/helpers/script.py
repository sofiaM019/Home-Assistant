"""Helpers to execute scripts."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import partial
import itertools
import logging
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import async_timeout
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import device_automation, scene
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_ALIAS,
    CONF_CHOOSE,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_CONTINUE_ON_TIMEOUT,
    CONF_COUNT,
    CONF_DEFAULT,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_EVENT_DATA_TEMPLATE,
    CONF_MODE,
    CONF_REPEAT,
    CONF_SCENE,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_TARGET,
    CONF_TIMEOUT,
    CONF_UNTIL,
    CONF_VARIABLES,
    CONF_WAIT_FOR_TRIGGER,
    CONF_WAIT_TEMPLATE,
    CONF_WHILE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_ON,
)
from homeassistant.core import (
    SERVICE_CALL_LIMIT,
    Context,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import condition, config_validation as cv, service, template
from homeassistant.helpers.condition import (
    TraceElement,
    condition_path,
    condition_trace_clear,
    condition_trace_get,
    trace_append_element,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
)
from homeassistant.helpers.event import async_call_later, async_track_template
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

SCRIPT_MODE_PARALLEL = "parallel"
SCRIPT_MODE_QUEUED = "queued"
SCRIPT_MODE_RESTART = "restart"
SCRIPT_MODE_SINGLE = "single"
SCRIPT_MODE_CHOICES = [
    SCRIPT_MODE_PARALLEL,
    SCRIPT_MODE_QUEUED,
    SCRIPT_MODE_RESTART,
    SCRIPT_MODE_SINGLE,
]
DEFAULT_SCRIPT_MODE = SCRIPT_MODE_SINGLE

CONF_MAX = "max"
DEFAULT_MAX = 10

CONF_MAX_EXCEEDED = "max_exceeded"
_MAX_EXCEEDED_CHOICES = list(LOGSEVERITY) + ["SILENT"]
DEFAULT_MAX_EXCEEDED = "WARNING"

ATTR_CUR = "current"
ATTR_MAX = "max"
ATTR_MODE = "mode"

DATA_SCRIPTS = "helpers.script"

_LOGGER = logging.getLogger(__name__)

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."

_SHUTDOWN_MAX_WAIT = 60


action_config = ContextVar("action_config", default=None)
action_trace = ContextVar("action_trace", default=None)
action_trace_stack = ContextVar("action_trace_stack", default=None)
action_path_stack = ContextVar("action_path_stack", default=None)


def action_trace_stack_push(node):
    """Push a TraceElement to the top of the trace stack."""
    trace_stack_push(action_trace_stack, node)


def action_trace_stack_pop():
    """Remove the top element from the trace stack."""
    trace_stack_pop(action_trace_stack)


def action_trace_stack_top():
    """Return the element at the top of the trace stack."""
    return trace_stack_top(action_trace_stack)


def action_path_push(suffix):
    """Go deeper in the config tree."""
    if isinstance(suffix, str):
        suffix = [suffix]
    for node in suffix:
        trace_stack_push(action_path_stack, node)
    return len(suffix)


def action_path_pop(n):
    """Go n levels up in the config tree."""
    for _ in range(n):
        trace_stack_pop(action_path_stack)


def action_path_get():
    """Return a string representing the current location in the config tree."""
    path = action_path_stack.get()
    if not path:
        return ""
    return "/".join(path)


def action_config_get():
    """Return the config of the script that was executed."""
    return action_config.get()


def action_trace_get():
    """Return the trace of the script that was executed."""
    return action_trace.get()


def action_trace_clear():
    """Clear the action trace."""
    action_config.set(None)
    action_trace.set({})
    action_trace_stack.set(None)
    action_path_stack.set(None)


def action_trace_append(variables, path):
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables)
    trace_append_element(action_trace, trace_element, path)
    return trace_element


def action_trace_set_result(**kwargs):
    """Set the result of TraceElement at the top of the stack."""
    node = action_trace_stack_top()
    node.set_result(**kwargs)


def action_trace_add_conditions():
    """Add the result of condition evaluation to the action trace."""
    condition_trace = condition_trace_get()
    condition_trace_clear()

    if condition_trace is None:
        return

    action_path = action_path_get()
    for cond_path, conditions in condition_trace.items():
        path = action_path + "/" + cond_path if cond_path else action_path
        for cond in conditions:
            trace_append_element(action_trace, cond, path)


@contextmanager
def trace_action(config, variables):
    """Trace action execution."""
    if action_config.get() is None:
        action_config.set(dict(config))

    trace_element = action_trace_append(variables, action_path_get())
    action_trace_stack_push(trace_element)
    try:
        yield trace_element
    except Exception as ex:  # pylint: disable=broad-except
        trace_element.set_error(ex)
        raise ex
    finally:
        action_trace_stack_pop()


@contextmanager
def action_path(suffix):
    """Go deeper in the config tree."""
    n = action_path_push(suffix)
    try:
        yield
    finally:
        action_path_pop(n)


def make_script_schema(schema, default_script_mode, extra=vol.PREVENT_EXTRA):
    """Make a schema for a component that uses the script helper."""
    return vol.Schema(
        {
            **schema,
            vol.Optional(CONF_MODE, default=default_script_mode): vol.In(
                SCRIPT_MODE_CHOICES
            ),
            vol.Optional(CONF_MAX, default=DEFAULT_MAX): vol.All(
                vol.Coerce(int), vol.Range(min=2)
            ),
            vol.Optional(CONF_MAX_EXCEEDED, default=DEFAULT_MAX_EXCEEDED): vol.All(
                vol.Upper, vol.In(_MAX_EXCEEDED_CHOICES)
            ),
        },
        extra=extra,
    )


STATIC_VALIDATION_ACTION_TYPES = (
    cv.SCRIPT_ACTION_CALL_SERVICE,
    cv.SCRIPT_ACTION_DELAY,
    cv.SCRIPT_ACTION_WAIT_TEMPLATE,
    cv.SCRIPT_ACTION_FIRE_EVENT,
    cv.SCRIPT_ACTION_ACTIVATE_SCENE,
    cv.SCRIPT_ACTION_VARIABLES,
)


async def async_validate_actions_config(
    hass: HomeAssistant, actions: List[ConfigType]
) -> List[ConfigType]:
    """Validate a list of actions."""
    return await asyncio.gather(
        *[async_validate_action_config(hass, action) for action in actions]
    )


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    action_type = cv.determine_script_action(config)

    if action_type in STATIC_VALIDATION_ACTION_TYPES:
        pass

    elif action_type == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
        platform = await device_automation.async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "action"
        )
        config = platform.ACTION_SCHEMA(config)  # type: ignore

    elif action_type == cv.SCRIPT_ACTION_CHECK_CONDITION:
        if config[CONF_CONDITION] == "device":
            platform = await device_automation.async_get_device_automation_platform(
                hass, config[CONF_DOMAIN], "condition"
            )
            config = platform.CONDITION_SCHEMA(config)  # type: ignore

    elif action_type == cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER:
        config[CONF_WAIT_FOR_TRIGGER] = await async_validate_trigger_config(
            hass, config[CONF_WAIT_FOR_TRIGGER]
        )

    elif action_type == cv.SCRIPT_ACTION_REPEAT:
        config[CONF_SEQUENCE] = await async_validate_actions_config(
            hass, config[CONF_REPEAT][CONF_SEQUENCE]
        )

    elif action_type == cv.SCRIPT_ACTION_CHOOSE:
        if CONF_DEFAULT in config:
            config[CONF_DEFAULT] = await async_validate_actions_config(
                hass, config[CONF_DEFAULT]
            )

        for choose_conf in config[CONF_CHOOSE]:
            choose_conf[CONF_SEQUENCE] = await async_validate_actions_config(
                hass, choose_conf[CONF_SEQUENCE]
            )

    else:
        raise ValueError(f"No validation for {action_type}")

    return config


class _StopScript(Exception):
    """Throw if script needs to stop."""


class _ScriptRun:
    """Manage Script sequence run."""

    def __init__(
        self,
        hass: HomeAssistant,
        script: "Script",
        variables: Dict[str, Any],
        context: Optional[Context],
        log_exceptions: bool,
    ) -> None:
        self._hass = hass
        self._script = script
        self._variables = variables
        self._context = context
        self._log_exceptions = log_exceptions
        self._step = -1
        self._action: Optional[Dict[str, Any]] = None
        self._stop = asyncio.Event()
        self._stopped = asyncio.Event()

    def _changed(self) -> None:
        if not self._stop.is_set():
            self._script._changed()  # pylint: disable=protected-access

    async def _async_get_condition(self, config):
        # pylint: disable=protected-access
        return await self._script._async_get_condition(config)

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        self._script._log(  # pylint: disable=protected-access
            msg, *args, level=level, **kwargs
        )

    def _step_log(self, default_message, timeout=None):
        self._script.last_action = self._action.get(CONF_ALIAS, default_message)
        _timeout = (
            "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
        )
        self._log("Executing step %s%s", self._script.last_action, _timeout)

    async def async_run(self) -> None:
        """Run script."""
        try:
            if self._stop.is_set():
                return
            self._log("Running %s", self._script.running_description)
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
                    break
                await self._async_step(log_exceptions=False)
        except _StopScript:
            pass
        finally:
            self._finish()

    async def _async_step(self, log_exceptions):
        with action_path(str(self._step)):
            with trace_action(self._action, None):
                try:
                    handler = f"_async_{cv.determine_script_action(self._action)}_step"
                    await getattr(self, handler)()
                except Exception as ex:
                    if not isinstance(ex, (_StopScript, asyncio.CancelledError)) and (
                        self._log_exceptions or log_exceptions
                    ):
                        self._log_exception(ex)
                    raise

    def _finish(self) -> None:
        self._script._runs.remove(self)  # pylint: disable=protected-access
        if not self._script.is_running:
            self._script.last_action = None
        self._changed()
        self._stopped.set()

    async def async_stop(self) -> None:
        """Stop script run."""
        self._stop.set()
        await self._stopped.wait()

    def _log_exception(self, exception):
        action_type = cv.determine_script_action(self._action)

        error = str(exception)
        level = logging.ERROR

        if isinstance(exception, vol.Invalid):
            error_desc = "Invalid data"

        elif isinstance(exception, exceptions.TemplateError):
            error_desc = "Error rendering template"

        elif isinstance(exception, exceptions.Unauthorized):
            error_desc = "Unauthorized"

        elif isinstance(exception, exceptions.ServiceNotFound):
            error_desc = "Service not found"

        elif isinstance(exception, exceptions.HomeAssistantError):
            error_desc = "Error"

        else:
            error_desc = "Unexpected error"
            level = _LOG_EXCEPTION

        self._log(
            "Error executing script. %s for %s at pos %s: %s",
            error_desc,
            action_type,
            self._step + 1,
            error,
            level=level,
        )

    def _get_pos_time_period_template(self, key):
        try:
            return cv.positive_time_period(
                template.render_complex(self._action[key], self._variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            self._log(
                "Error rendering %s %s template: %s",
                self._script.name,
                key,
                ex,
                level=logging.ERROR,
            )
            raise _StopScript from ex

    async def _async_delay_step(self):
        """Handle delay."""
        delay = self._get_pos_time_period_template(CONF_DELAY)

        self._step_log(f"delay {delay}")

        delay = delay.total_seconds()
        self._changed()
        try:
            async with async_timeout.timeout(delay):
                await self._stop.wait()
        except asyncio.TimeoutError:
            pass

    async def _async_wait_template_step(self):
        """Handle a wait template."""
        if CONF_TIMEOUT in self._action:
            timeout = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            timeout = None

        self._step_log("wait template", timeout)

        self._variables["wait"] = {"remaining": timeout, "completed": False}

        wait_template = self._action[CONF_WAIT_TEMPLATE]
        wait_template.hass = self._hass

        # check if condition already okay
        if condition.async_template(self._hass, wait_template, self._variables):
            self._variables["wait"]["completed"] = True
            return

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            self._variables["wait"] = {
                "remaining": to_context.remaining if to_context else timeout,
                "completed": True,
            }
            done.set()

        to_context = None
        unsub = async_track_template(
            self._hass, wait_template, async_script_wait, self._variables
        )

        self._changed()
        done = asyncio.Event()
        tasks = [
            self._hass.async_create_task(flag.wait()) for flag in (self._stop, done)
        ]
        try:
            async with async_timeout.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript from ex
            self._variables["wait"]["remaining"] = 0.0
        finally:
            for task in tasks:
                task.cancel()
            unsub()

    async def _async_run_long_action(self, long_task):
        """Run a long task while monitoring for stop request."""

        async def async_cancel_long_task() -> None:
            # Stop long task and wait for it to finish.
            long_task.cancel()
            try:
                await long_task
            except Exception:  # pylint: disable=broad-except
                pass

        # Wait for long task while monitoring for a stop request.
        stop_task = self._hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {long_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        # If our task is cancelled, then cancel long task, too. Note that if long task
        # is cancelled otherwise the CancelledError exception will not be raised to
        # here due to the call to asyncio.wait(). Rather we'll check for that below.
        except asyncio.CancelledError:
            await async_cancel_long_task()
            raise
        finally:
            stop_task.cancel()

        if long_task.cancelled():
            raise asyncio.CancelledError
        if long_task.done():
            # Propagate any exceptions that occurred.
            long_task.result()
        else:
            # Stopped before long task completed, so cancel it.
            await async_cancel_long_task()

    async def _async_call_service_step(self):
        """Call the service specified in the action."""
        self._step_log("call service")

        params = service.async_prepare_call_from_config(
            self._hass, self._action, self._variables
        )

        running_script = (
            params[CONF_DOMAIN] == "automation"
            and params[CONF_SERVICE] == "trigger"
            or params[CONF_DOMAIN] in ("python_script", "script")
        )
        # If this might start a script then disable the call timeout.
        # Otherwise use the normal service call limit.
        if running_script:
            limit = None
        else:
            limit = SERVICE_CALL_LIMIT

        service_task = self._hass.async_create_task(
            self._hass.services.async_call(
                **params,
                blocking=True,
                context=self._context,
                limit=limit,
            )
        )
        if limit is not None:
            # There is a call limit, so just wait for it to finish.
            await service_task
            return

        await self._async_run_long_action(service_task)

    async def _async_device_step(self):
        """Perform the device automation specified in the action."""
        self._step_log("device automation")
        platform = await device_automation.async_get_device_automation_platform(
            self._hass, self._action[CONF_DOMAIN], "action"
        )
        await platform.async_call_action_from_config(
            self._hass, self._action, self._variables, self._context
        )

    async def _async_scene_step(self):
        """Activate the scene specified in the action."""
        self._step_log("activate scene")
        await self._hass.services.async_call(
            scene.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._action[CONF_SCENE]},
            blocking=True,
            context=self._context,
        )

    async def _async_event_step(self):
        """Fire an event."""
        self._step_log(self._action.get(CONF_ALIAS, self._action[CONF_EVENT]))
        event_data = {}
        for conf in [CONF_EVENT_DATA, CONF_EVENT_DATA_TEMPLATE]:
            if conf not in self._action:
                continue

            try:
                event_data.update(
                    template.render_complex(self._action[conf], self._variables)
                )
            except exceptions.TemplateError as ex:
                self._log(
                    "Error rendering event data template: %s", ex, level=logging.ERROR
                )

        self._hass.bus.async_fire(
            self._action[CONF_EVENT], event_data, context=self._context
        )

    async def _async_condition_step(self):
        """Test if condition is matching."""
        self._script.last_action = self._action.get(
            CONF_ALIAS, self._action[CONF_CONDITION]
        )
        cond = await self._async_get_condition(self._action)
        try:
            with condition_path("condition"):
                check = cond(self._hass, self._variables)
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in 'condition' evaluation:\n%s", ex)
            check = False

        self._log("Test condition %s: %s", self._script.last_action, check)
        action_trace_set_result(result=check)
        action_trace_add_conditions()
        if not check:
            raise _StopScript

    def _test_conditions(self, conditions, name):
        result = True
        try:
            with condition_path("conditions"):
                for idx, cond in enumerate(conditions):
                    with condition_path(str(idx)):
                        if not cond(self._hass, self._variables):
                            result = False
                            break
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in '%s' evaluation: %s", name, ex)
            result = None

        action_trace_add_conditions()
        return result

    async def _async_repeat_step(self):
        """Repeat a sequence."""
        description = self._action.get(CONF_ALIAS, "sequence")
        repeat = self._action[CONF_REPEAT]

        saved_repeat_vars = self._variables.get("repeat")

        def set_repeat_var(iteration, count=None):
            repeat_vars = {"first": iteration == 1, "index": iteration}
            if count:
                repeat_vars["last"] = iteration == count
            self._variables["repeat"] = repeat_vars

        # pylint: disable=protected-access
        script = self._script._get_repeat_script(self._step)

        async def async_run_sequence(iteration, extra_msg=""):
            self._log("Repeating %s: Iteration %i%s", description, iteration, extra_msg)
            with action_path(str(self._step)):
                await self._async_run_script(script)

        if CONF_COUNT in repeat:
            count = repeat[CONF_COUNT]
            if isinstance(count, template.Template):
                try:
                    count = int(count.async_render(self._variables))
                except (exceptions.TemplateError, ValueError) as ex:
                    self._log(
                        "Error rendering %s repeat count template: %s",
                        self._script.name,
                        ex,
                        level=logging.ERROR,
                    )
                    raise _StopScript from ex
            extra_msg = f" of {count}"
            for iteration in range(1, count + 1):
                set_repeat_var(iteration, count)
                await async_run_sequence(iteration, extra_msg)
                if self._stop.is_set():
                    break

        elif CONF_WHILE in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_WHILE]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                try:
                    if self._stop.is_set():
                        break
                    if not self._test_conditions(conditions, "while"):
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'while' evaluation:\n%s", ex)
                    break

                await async_run_sequence(iteration)

        elif CONF_UNTIL in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_UNTIL]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                await async_run_sequence(iteration)
                try:
                    if self._stop.is_set():
                        break
                    if self._test_conditions(conditions, "until") in [True, None]:
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'until' evaluation:\n%s", ex)
                    break

        if saved_repeat_vars:
            self._variables["repeat"] = saved_repeat_vars
        else:
            del self._variables["repeat"]

    async def _async_choose_step(self) -> None:
        """Choose a sequence."""
        # pylint: disable=protected-access
        choose_data = await self._script._async_get_choose_data(self._step)

        for idx, (conditions, script) in enumerate(choose_data["choices"]):
            with action_path(str(idx)):
                try:
                    if self._test_conditions(conditions, "choose"):
                        action_trace_set_result(choice=idx)
                        await self._async_run_script(script)
                        return
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'choose' evaluation:\n%s", ex)

        if choose_data["default"]:
            action_trace_set_result(choice="default")
            with action_path("default"):
                await self._async_run_script(choose_data["default"])

    async def _async_wait_for_trigger_step(self):
        """Wait for a trigger event."""
        if CONF_TIMEOUT in self._action:
            timeout = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            timeout = None

        self._step_log("wait for trigger", timeout)

        variables = {**self._variables}
        self._variables["wait"] = {"remaining": timeout, "trigger": None}

        done = asyncio.Event()

        async def async_done(variables, context=None):
            self._variables["wait"] = {
                "remaining": to_context.remaining if to_context else timeout,
                "trigger": variables["trigger"],
            }
            done.set()

        def log_cb(level, msg, **kwargs):
            self._log(msg, level=level, **kwargs)

        to_context = None
        remove_triggers = await async_initialize_triggers(
            self._hass,
            self._action[CONF_WAIT_FOR_TRIGGER],
            async_done,
            self._script.domain,
            self._script.name,
            log_cb,
            variables=variables,
        )
        if not remove_triggers:
            return

        self._changed()
        tasks = [
            self._hass.async_create_task(flag.wait()) for flag in (self._stop, done)
        ]
        try:
            async with async_timeout.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript from ex
            self._variables["wait"]["remaining"] = 0.0
        finally:
            for task in tasks:
                task.cancel()
            remove_triggers()

    async def _async_variables_step(self):
        """Set a variable value."""
        self._step_log("setting variables")
        self._variables = self._action[CONF_VARIABLES].async_render(
            self._hass, self._variables, render_as_defaults=False
        )

    async def _async_run_script(self, script):
        """Execute a script."""
        await self._async_run_long_action(
            self._hass.async_create_task(
                script.async_run(self._variables, self._context)
            )
        )


class _QueuedScriptRun(_ScriptRun):
    """Manage queued Script sequence run."""

    lock_acquired = False

    async def async_run(self) -> None:
        """Run script."""
        # Wait for previous run, if any, to finish by attempting to acquire the script's
        # shared lock. At the same time monitor if we've been told to stop.
        lock_task = self._hass.async_create_task(
            self._script._queue_lck.acquire()  # pylint: disable=protected-access
        )
        stop_task = self._hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {lock_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            lock_task.cancel()
            self._finish()
            raise
        finally:
            stop_task.cancel()
        self.lock_acquired = lock_task.done() and not lock_task.cancelled()

        # If we've been told to stop, then just finish up. Otherwise, we've acquired the
        # lock so we can go ahead and start the run.
        if self._stop.is_set():
            self._finish()
        else:
            await super().async_run()

    def _finish(self) -> None:
        # pylint: disable=protected-access
        if self.lock_acquired:
            self._script._queue_lck.release()
            self.lock_acquired = False
        super()._finish()


async def _async_stop_scripts_after_shutdown(hass, point_in_time):
    """Stop running Script objects started after shutdown."""
    running_scripts = [
        script for script in hass.data[DATA_SCRIPTS] if script["instance"].is_running
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.warning("Stopping scripts running too long after shutdown: %s", names)
        await asyncio.gather(
            *[
                script["instance"].async_stop(update_state=False)
                for script in running_scripts
            ]
        )


async def _async_stop_scripts_at_shutdown(hass, event):
    """Stop running Script objects started before shutdown."""
    async_call_later(
        hass, _SHUTDOWN_MAX_WAIT, partial(_async_stop_scripts_after_shutdown, hass)
    )

    running_scripts = [
        script
        for script in hass.data[DATA_SCRIPTS]
        if script["instance"].is_running and script["started_before_shutdown"]
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.debug("Stopping scripts running at shutdown: %s", names)
        await asyncio.gather(
            *[script["instance"].async_stop() for script in running_scripts]
        )


_VarsType = Union[Dict[str, Any], MappingProxyType]


def _referenced_extract_ids(data: Dict[str, Any], key: str, found: Set[str]) -> None:
    """Extract referenced IDs."""
    if not data:
        return

    item_ids = data.get(key)

    if item_ids is None or isinstance(item_ids, template.Template):
        return

    if isinstance(item_ids, str):
        item_ids = [item_ids]

    for item_id in item_ids:
        found.add(item_id)


class Script:
    """Representation of a script."""

    def __init__(
        self,
        hass: HomeAssistant,
        sequence: Sequence[Dict[str, Any]],
        name: str,
        domain: str,
        *,
        # Used in "Running <running_description>" log message
        running_description: Optional[str] = None,
        change_listener: Optional[Callable[..., Any]] = None,
        script_mode: str = DEFAULT_SCRIPT_MODE,
        max_runs: int = DEFAULT_MAX,
        max_exceeded: str = DEFAULT_MAX_EXCEEDED,
        logger: Optional[logging.Logger] = None,
        log_exceptions: bool = True,
        top_level: bool = True,
        variables: Optional[ScriptVariables] = None,
    ) -> None:
        """Initialize the script."""
        all_scripts = hass.data.get(DATA_SCRIPTS)
        if not all_scripts:
            all_scripts = hass.data[DATA_SCRIPTS] = []
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, partial(_async_stop_scripts_at_shutdown, hass)
            )
        self._top_level = top_level
        if top_level:
            all_scripts.append(
                {"instance": self, "started_before_shutdown": not hass.is_stopping}
            )

        self._hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self.domain = domain
        self.running_description = running_description or f"{domain} script"
        self._change_listener = change_listener
        self._change_listener_job = (
            None if change_listener is None else HassJob(change_listener)
        )

        self.script_mode = script_mode
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

        self.last_action = None
        self.last_triggered: Optional[datetime] = None

        self._runs: List[_ScriptRun] = []
        self.max_runs = max_runs
        self._max_exceeded = max_exceeded
        if script_mode == SCRIPT_MODE_QUEUED:
            self._queue_lck = asyncio.Lock()
        self._config_cache: Dict[Set[Tuple], Callable[..., bool]] = {}
        self._repeat_script: Dict[int, Script] = {}
        self._choose_data: Dict[int, Dict[str, Any]] = {}
        self._referenced_entities: Optional[Set[str]] = None
        self._referenced_devices: Optional[Set[str]] = None
        self.variables = variables
        self._variables_dynamic = template.is_complex(variables)
        if self._variables_dynamic:
            template.attach(hass, variables)

    @property
    def change_listener(self) -> Optional[Callable[..., Any]]:
        """Return the change_listener."""
        return self._change_listener

    @change_listener.setter
    def change_listener(self, change_listener: Callable[..., Any]) -> None:
        """Update the change_listener."""
        self._change_listener = change_listener
        if (
            self._change_listener_job is None
            or change_listener != self._change_listener_job.target
        ):
            self._change_listener_job = HassJob(change_listener)

    def _set_logger(self, logger: Optional[logging.Logger] = None) -> None:
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

    def update_logger(self, logger: Optional[logging.Logger] = None) -> None:
        """Update logger."""
        self._set_logger(logger)
        for script in self._repeat_script.values():
            script.update_logger(self._logger)
        for choose_data in self._choose_data.values():
            for _, script in choose_data["choices"]:
                script.update_logger(self._logger)
            if choose_data["default"]:
                choose_data["default"].update_logger(self._logger)

    def _changed(self) -> None:
        if self._change_listener_job:
            self._hass.async_run_hass_job(self._change_listener_job)

    def _chain_change_listener(self, sub_script):
        if sub_script.is_running:
            self.last_action = sub_script.last_action
            self._changed()

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return len(self._runs) > 0

    @property
    def runs(self) -> int:
        """Return the number of current runs."""
        return len(self._runs)

    @property
    def supports_max(self) -> bool:
        """Return true if the current mode support max."""
        return self.script_mode in (SCRIPT_MODE_PARALLEL, SCRIPT_MODE_QUEUED)

    @property
    def referenced_devices(self):
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        referenced: Set[str] = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step,
                    step.get(CONF_TARGET),
                    step.get(service.CONF_SERVICE_DATA),
                    step.get(service.CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_DEVICE_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_devices(step)

            elif action == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
                referenced.add(step[CONF_DEVICE_ID])

        self._referenced_devices = referenced
        return referenced

    @property
    def referenced_entities(self):
        """Return a set of referenced entities."""
        if self._referenced_entities is not None:
            return self._referenced_entities

        referenced: Set[str] = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step,
                    step.get(CONF_TARGET),
                    step.get(service.CONF_SERVICE_DATA),
                    step.get(service.CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_ENTITY_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_entities(step)

            elif action == cv.SCRIPT_ACTION_ACTIVATE_SCENE:
                referenced.add(step[CONF_SCENE])

        self._referenced_entities = referenced
        return referenced

    def run(
        self, variables: Optional[_VarsType] = None, context: Optional[Context] = None
    ) -> None:
        """Run script."""
        asyncio.run_coroutine_threadsafe(
            self.async_run(variables, context), self._hass.loop
        ).result()

    async def async_run(
        self,
        run_variables: Optional[_VarsType] = None,
        context: Optional[Context] = None,
        started_action: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Run script."""
        if context is None:
            self._log(
                "Running script requires passing in a context", level=logging.WARNING
            )
            context = Context()

        if self.is_running:
            if self.script_mode == SCRIPT_MODE_SINGLE:
                if self._max_exceeded != "SILENT":
                    self._log("Already running", level=LOGSEVERITY[self._max_exceeded])
                return
            if self.script_mode == SCRIPT_MODE_RESTART:
                self._log("Restarting")
                await self.async_stop(update_state=False)
            elif len(self._runs) == self.max_runs:
                if self._max_exceeded != "SILENT":
                    self._log(
                        "Maximum number of runs exceeded",
                        level=LOGSEVERITY[self._max_exceeded],
                    )
                return

        # If this is a top level Script then make a copy of the variables in case they
        # are read-only, but more importantly, so as not to leak any variables created
        # during the run back to the caller.
        if self._top_level:
            if self.variables:
                try:
                    variables = self.variables.async_render(
                        self._hass,
                        run_variables,
                    )
                except template.TemplateError as err:
                    self._log("Error rendering variables: %s", err, level=logging.ERROR)
                    raise
            elif run_variables:
                variables = dict(run_variables)
            else:
                variables = {}

            variables["context"] = context
        else:
            variables = cast(dict, run_variables)

        if self.script_mode != SCRIPT_MODE_QUEUED:
            cls = _ScriptRun
        else:
            cls = _QueuedScriptRun
        run = cls(
            self._hass, self, cast(dict, variables), context, self._log_exceptions
        )
        self._runs.append(run)
        if started_action:
            self._hass.async_run_job(started_action)
        self.last_triggered = utcnow()
        self._changed()

        try:
            await asyncio.shield(run.async_run())
        except asyncio.CancelledError:
            await run.async_stop()
            self._changed()
            raise

    async def _async_stop(self, update_state):
        aws = [asyncio.create_task(run.async_stop()) for run in self._runs]
        if not aws:
            return
        await asyncio.wait(aws)
        if update_state:
            self._changed()

    async def async_stop(self, update_state: bool = True) -> None:
        """Stop running script."""
        await asyncio.shield(self._async_stop(update_state))

    async def _async_get_condition(self, config):
        if isinstance(config, template.Template):
            config_cache_key = config.template
        else:
            config_cache_key = frozenset((k, str(v)) for k, v in config.items())
        cond = self._config_cache.get(config_cache_key)
        if not cond:
            cond = await condition.async_from_config(self._hass, config, False)
            self._config_cache[config_cache_key] = cond
        return cond

    def _prep_repeat_script(self, step):
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Repeat at step {step+1}")
        sub_script = Script(
            self._hass,
            action[CONF_REPEAT][CONF_SEQUENCE],
            f"{self.name}: {step_name}",
            self.domain,
            running_description=self.running_description,
            script_mode=SCRIPT_MODE_PARALLEL,
            max_runs=self.max_runs,
            logger=self._logger,
            top_level=False,
        )
        sub_script.change_listener = partial(self._chain_change_listener, sub_script)
        return sub_script

    def _get_repeat_script(self, step):
        sub_script = self._repeat_script.get(step)
        if not sub_script:
            sub_script = self._prep_repeat_script(step)
            self._repeat_script[step] = sub_script
        return sub_script

    async def _async_prep_choose_data(self, step):
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Choose at step {step+1}")
        choices = []
        for idx, choice in enumerate(action[CONF_CHOOSE], start=1):
            conditions = [
                await self._async_get_condition(config)
                for config in choice.get(CONF_CONDITIONS, [])
            ]
            choice_name = choice.get(CONF_ALIAS, f"choice {idx}")
            sub_script = Script(
                self._hass,
                choice[CONF_SEQUENCE],
                f"{self.name}: {step_name}: {choice_name}",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
            )
            sub_script.change_listener = partial(
                self._chain_change_listener, sub_script
            )
            choices.append((conditions, sub_script))

        if CONF_DEFAULT in action:
            default_script = Script(
                self._hass,
                action[CONF_DEFAULT],
                f"{self.name}: {step_name}: default",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
            )
            default_script.change_listener = partial(
                self._chain_change_listener, default_script
            )
        else:
            default_script = None

        return {"choices": choices, "default": default_script}

    async def _async_get_choose_data(self, step):
        choose_data = self._choose_data.get(step)
        if not choose_data:
            choose_data = await self._async_prep_choose_data(step)
            self._choose_data[step] = choose_data
        return choose_data

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        msg = f"%s: {msg}"
        args = (self.name, *args)

        if level == _LOG_EXCEPTION:
            self._logger.exception(msg, *args, **kwargs)
        else:
            self._logger.log(level, msg, *args, **kwargs)
