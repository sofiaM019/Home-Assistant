"""Support for rasc."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
import json
import re
import threading
from typing import Any

from homeassistant.components.script import BaseScriptEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.rascalscheduler import (
    ActionEntity,
    Queue,
    QueueEntity,
    RoutineEntity,
)

from .const import (
    DOMAIN,
    LOGGER,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_START,
    SCRIPT_DOMAIN,
)

CONFIG_ENTITY_ID = "entity_id"
CONFIG_ROUTINE_ID = "routine_id"
CONFIG_STEP = "step"
CONFIG_HASS = "hass"
CONFIG_ENTITY_REGISTRY = "entity_registry"

PARALLEL_ITEM = "parallel"
SEQUENCE_ITEM = "sequence"
SERVICE_ITEM = "service"

EVENT_TYPE = "type"
EVENT_ENTITY_ID = "entity_id"

TIMEOUT = 3000  # millisecond


def setup_rascal_scheduler_entity(hass: HomeAssistant) -> None:
    """Set up RASC scheduler entity."""
    LOGGER.info("Setup rascal entity")
    hass.data[DOMAIN] = RascalSchedulerEntity(hass)
    hass.bus.async_listen(RASC_RESPONSE, hass.data[DOMAIN].event_listener)


def create_x_ready_queue(hass: HomeAssistant, entity_id: str) -> None:
    """Create queue for x entity."""
    LOGGER.info("Create ready queue: %s", entity_id)
    scheduler = hass.data[DOMAIN]
    scheduler.ready_queues[entity_id] = QueueEntity(None)
    scheduler.active_routines[entity_id] = None
    scheduler.loops[entity_id] = scheduler.create_bg_loop()


# def delete_x_active_queue(hass: HomeAssistant, entity_id: str) -> None:
#     """Delete x entity queue."""
#     try:
#         rascal_scheduler = hass.data[DOMAIN]
#         active_routines = rascal_scheduler.get_active_routines()
#         del active_routines[entity_id]
#     except (KeyError, ValueError):
#         LOGGER.warning("Unable to delete unknown queue %s", entity_id)


def get_rascal_scheduler(hass: HomeAssistant) -> RascalSchedulerEntity:
    """Get rascal scheduler."""
    return hass.data[DOMAIN]


def dag_operator(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
) -> RoutineEntity:
    """Convert the script to the DAG."""
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # configuration for each node
    config[CONFIG_STEP] = -1
    config[CONFIG_ROUTINE_ID] = routine_id
    config[CONFIG_HASS] = hass

    for _, script in enumerate(action_script):
        if (
            PARALLEL_ITEM not in script
            and SEQUENCE_ITEM not in script
            and SEQUENCE_ITEM not in script
        ):
            config[CONFIG_STEP] = config[CONFIG_STEP] + 1
            action_id = config[CONFIG_ROUTINE_ID] + str(config[CONFIG_STEP])

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                action_state=None,
                routine_id=config[CONFIG_ROUTINE_ID],
            )

            for entity in next_parents:
                entities[action_id].parents.append(entity)

            for entity in next_parents:
                entity.children.append(entities[action_id])

            next_parents.clear()
            next_parents.append(entities[action_id])

        else:
            leaf_nodes = dfs(script, config, next_parents, entities)
            next_parents.clear()
            next_parents = leaf_nodes

    return RoutineEntity(name, routine_id, entities, TIMEOUT, LOGGER)


def dfs(
    script: dict[str, Any],
    config: dict[str, Any],
    parents: list[ActionEntity],
    entities: dict[str, Any],
) -> list[ActionEntity]:
    """Convert the script to the dag using dsf."""

    next_parents = []
    # print("script:", script)
    if PARALLEL_ITEM in script:
        for item in list(script.values())[0]:
            leaf_entities = dfs(item, config, parents, entities)
            for entity in leaf_entities:
                next_parents.append(entity)

    elif SEQUENCE_ITEM in script:
        next_parents = parents
        for item in list(script.values())[0]:
            leaf_entities = dfs(item, config, next_parents, entities)
            next_parents = leaf_entities

    elif SERVICE_ITEM in script:
        script_component: EntityComponent[BaseScriptEntity] = config[CONFIG_HASS].data[
            SCRIPT_DOMAIN
        ]

        if script_component is not None:
            baseScript = script_component.get_entity(list(script.values())[0])
            if baseScript is not None and baseScript.raw_config is not None:
                next_parents = parents
                for item in baseScript.raw_config[SEQUENCE_ITEM]:
                    leaf_entities = dfs(item, config, next_parents, entities)
                    next_parents = leaf_entities

    else:
        config[CONFIG_STEP] = config[CONFIG_STEP] + 1
        action_id = config[CONFIG_ROUTINE_ID] + str(config[CONFIG_STEP])

        entities[action_id] = ActionEntity(
            hass=config[CONFIG_HASS],
            action=script,
            action_id=action_id,
            action_state=None,
            routine_id=config[CONFIG_ROUTINE_ID],
        )

        for entity in parents:
            entities[action_id].parents.append(entity)

        for entity in parents:
            entity.children.append(entities[action_id])

        next_parents.append(entities[action_id])

    return next_parents


class BaseActiveRoutines:
    """Base class for active routines."""

    _active_routines: dict[str, ActionEntity]
    _loops: dict[str, asyncio.AbstractEventLoop]

    @property
    def active_routines(self) -> dict[str, ActionEntity]:
        """Get active routines."""
        return self._active_routines

    def get_active_routine(self, entity_id: str) -> ActionEntity:
        """Get active routine of entity_id."""
        return self._active_routines[entity_id]

    @property
    def loops(self) -> dict[str, asyncio.AbstractEventLoop]:
        """Get loops."""
        return self._loops

    def get_loop(self, entity_id: str) -> asyncio.AbstractEventLoop:
        """Get loop of entity_id."""
        return self._loops[entity_id]

    def create_bg_loop(self) -> asyncio.AbstractEventLoop:
        """Create event loop in background."""

        def to_bg(loop):
            """Create event loop in background."""
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            except asyncio.CancelledError as e:
                self.logger.error("Error cancelling loop %s", e)
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.stop()
                loop.close()

        new_loop = asyncio.new_event_loop()
        t = threading.Thread(target=to_bg, args=(new_loop,))
        t.start()
        return new_loop

    def output_active_routines(self) -> None:
        """Output the content of active routines."""
        active_routines = []
        for entity_id in self._active_routines:
            if self._active_routines[entity_id] is None:
                entity_json = {
                    "entity_id": entity_id,
                    "action_id": None,
                    "action_state": None,
                }
            else:
                entity_json = {
                    "entity_id": entity_id,
                    "action_id": self._active_routines[entity_id].action_id,
                    "action_state": self._active_routines[entity_id].action_state,
                }

            active_routines.append(entity_json)

        out = {"Type": "Active Routines", "Routines": active_routines}
        print(json.dumps(out, indent=2))  # noqa: T201


class BaseReadyQueues:
    """Base class for ready queue."""

    _ready_queues: dict[str, QueueEntity]

    @property
    def ready_queues(self) -> dict[str, QueueEntity]:
        """Get ready routines."""
        return self._ready_queues

    def output_ready_queues(self) -> None:
        """Output the content of ready routines."""
        ready_routines = []
        for entity_id, actions in self._ready_queues.items():
            action_list = []
            for action in actions:
                sub_entity_json = {
                    "action_id": action.action_id,
                    "action_state": action.action_state,
                }

                action_list.append(sub_entity_json)

            entity_json = {"entity_id": entity_id, "actions": action_list}

            ready_routines.append(entity_json)

        out = {"Type": "Ready Routines", "Routines": ready_routines}
        print(json.dumps(out, indent=2))  # noqa: T201


class RascalSchedulerEntity(BaseActiveRoutines, BaseReadyQueues):
    """Representation of a rascal scehduler entity."""

    def __init__(self, hass):
        """Initialize rascal scheduler entity."""
        self.hass = hass
        self._ready_queues: Queue() = {}
        self._active_routines: dict[str, ActionEntity | None] = {}
        self._loops: dict[
            str, asyncio.AbstractEventLoop
        ] = {}  # loops for active_rountines
        self.event_listener = self.handle_event

    def start_routine(self, routine_entity: RoutineEntity) -> None:
        """Start routine entity."""
        for _, action_entity in routine_entity.actions.items():
            # convert number to entity id
            pattern = re.compile("^[^.]+[.][^.]+$")
            if not pattern.match(action_entity.action[CONFIG_ENTITY_ID]):
                registry = self.hass.data[CONFIG_ENTITY_REGISTRY]
                action_entity.action[CONFIG_ENTITY_ID] = registry.async_get(
                    action_entity.action[CONFIG_ENTITY_ID]
                ).as_partial_dict[CONFIG_ENTITY_ID]

            # if the entity doesn't have parents, set it to ready queues
            if not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action_entity: ActionEntity) -> None:
        """Set the action entity into ready routines.

        a. if active routine is None, set the action_entity as active routine
        b. else, add the action_entity to ready queues.

        """

        entity_id = action_entity.action[CONFIG_ENTITY_ID]

        if self._active_routines[entity_id] is None:  # set as active routine
            self._set_active_routine(entity_id, action_entity)
        else:  # set to ready queue
            self._ready_queues[entity_id].append(action_entity)

    def _set_active_routine(
        self, entity_id: str, action_entity: ActionEntity | None
    ) -> None:
        """Set the action_entity as active routine."""
        self._active_routines[entity_id] = action_entity

        if action_entity is not None:
            self._active_routines[entity_id] = action_entity

            # run loop in background
            bg_loop = self.get_loop(entity_id)
            asyncio.run_coroutine_threadsafe(
                self.attach_trigger(action_entity), bg_loop
            )
            # bg_loop.call_soon_threadsafe(bg_loop.stop)
            # thread = threading.Thread(target=t.run, args=[action_entity])
            # thread.start()

    # Why cannot pass async function to thread?
    # RuntimeError: Task <Task pending name='Task-738' coro=<ActionEntity.attach_triggered()
    # running at /workspaces/home-assistant-core/homeassistant/helpers/rascalscheduler.py:189>
    # cb=[_run_until_complete_cb() at /usr/local/lib/python3.11/asyncio/base_events.py:180]>
    # got Future <Task pending name='Task-739' coro=<async_refresh_after.<locals>._async_wrap()
    # running at /workspaces/home-assistant-core/homeassistant/components/tplink/entity.py:25>
    # cb=[set.remove()]> attached to a different loop

    # def run(self, action_entity: ActionEntity) -> None:
    #     """Run action entity."""
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(self.loop)
    #     loop.run_until_complete(action_entity.attach_triggered(log_exceptions=False))
    #     loop.close()

    async def attach_trigger(self, action_entity: ActionEntity) -> None:
        """Trigger action_entity."""
        await action_entity.attach_triggered(log_exceptions=False)

    # Listener to handle fired events
    def handle_event(self, event):
        """Handle event.

        a. When the event type is complete
        - change the state to RASC_COMPLETE
        - schedule the next action
        b. When the event type is start
        - change the state to RASC_START

        """

        eventType = event.data.get(EVENT_TYPE)
        entityID = event.data.get(EVENT_ENTITY_ID)
        action_entity = self.get_active_routine(entityID)

        if eventType == RASC_COMPLETE:
            self.update_action_state(action_entity, RASC_COMPLETE)
            # self.output_active_routines()
            self.schedule_next(action_entity)

        elif eventType == RASC_START:
            self.update_action_state(action_entity, RASC_START)
            # self.output_active_routines()

    def schedule_next(self, action_entity: ActionEntity) -> None:
        """After action_entity completed, schedule the next subroutines."""
        entity_id = action_entity.action[CONFIG_ENTITY_ID]

        self._add_subroutines_to_ready_queues(action_entity)

        self._set_active_routine(
            entity_id, None
        )  # remove the current action_entity from action_entity

        self._schedule_next(entity_id)

    # continue to do, need to check condition variable
    def condition_check(self, action_entity: ActionEntity) -> bool:
        """Condition check."""
        for parent in action_entity.parents:
            if parent.action_state != RASC_COMPLETE:
                return False

        return True

    def _add_subroutines_to_ready_queues(self, action_entity: ActionEntity) -> None:
        """After action_entity completed, schedule the next subroutines."""
        if not action_entity.children:
            return
        next_subroutine = action_entity.children

        for action in next_subroutine:
            if self.condition_check(action):
                self._start_action(action)

        # self.output_ready_queues()

    def _schedule_next(self, entity_id: str) -> None:
        """Schedule the next action using FIFO strategy."""
        if self._ready_queues[entity_id]:
            next_action_entity = self._ready_queues[entity_id].pop(0)
            self._set_active_routine(entity_id, next_action_entity)

    def update_action_state(self, action_entity: ActionEntity, new_state: str) -> None:
        """Update action state to new state."""
        action_entity.action_state = new_state
