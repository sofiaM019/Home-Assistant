"""Event parser and human readable log generator."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from sqlalchemy.engine.row import Row

from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import (
    bytes_to_ulid_or_none,
    bytes_to_uuid_hex_or_none,
    ulid_to_bytes_or_none,
    uuid_hex_to_bytes_or_none,
)
from homeassistant.const import ATTR_ICON, EVENT_STATE_CHANGED
from homeassistant.core import Context, Event, State, callback
from homeassistant.util.event_type import EventType
from homeassistant.util.json import json_loads
from homeassistant.util.ulid import ulid_to_bytes


@dataclass(slots=True)
class LogbookConfig:
    """Configuration for the logbook integration."""

    external_events: dict[
        EventType[Any] | str,
        tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]],
    ]
    sqlalchemy_filter: Filters | None = None
    entity_filter: Callable[[str], bool] | None = None


class LazyEventPartialState:
    """A lazy version of core Event with limited State joined in."""

    def __init__(
        self,
        row: Row | EventAsRow,
        event_data_cache: dict[str, dict[str, Any]],
    ) -> None:
        """Init the lazy event."""
        self.row = row
        self._event_data: dict[str, Any] | None = None
        self._event_data_cache = event_data_cache
        # We need to explicitly check for the row is EventAsRow as the unhappy path
        # to fetch row[DATA_POS] for Row is very expensive
        if type(row) is EventAsRow:
            # If its an EventAsRow we can avoid the whole
            # json decode process as we already have the data
            self.data = row[DATA_POS]
            return
        if TYPE_CHECKING:
            source = cast(str, row[EVENT_DATA_POS])
        else:
            source = row[EVENT_DATA_POS]
        if not source:
            self.data = {}
        elif event_data := self._event_data_cache.get(source):
            self.data = event_data
        else:
            self.data = self._event_data_cache[source] = cast(
                dict[str, Any], json_loads(source)
            )

    @cached_property
    def event_type(self) -> EventType[Any] | str | None:
        """Return the event type."""
        return self.row[EVENT_TYPE_POS]

    @cached_property
    def entity_id(self) -> str | None:
        """Return the entity id."""
        return self.row[ENTITY_ID_POS]

    @cached_property
    def state(self) -> str | None:
        """Return the state."""
        return self.row[STATE_POS]

    @cached_property
    def context_id(self) -> str | None:
        """Return the context id."""
        return bytes_to_ulid_or_none(self.row[CONTEXT_ID_BIN_POS])

    @cached_property
    def context_user_id(self) -> str | None:
        """Return the context user id."""
        return bytes_to_uuid_hex_or_none(self.row[CONTEXT_USER_ID_BIN_POS])

    @cached_property
    def context_parent_id(self) -> str | None:
        """Return the context parent id."""
        return bytes_to_ulid_or_none(self.row[CONTEXT_PARENT_ID_BIN_POS])


# Row order must match the query order in queries/common.py
# ---------------------------------------------------------
# row_id - 0
ROW_ID_POS = 0
# event_type - 1
EVENT_TYPE_POS = 1
# event_data - 2
EVENT_DATA_POS = 2
# time_fired_ts - 3
TIME_FIRED_TS_POS = 3
# context_id_bin - 4
CONTEXT_ID_BIN_POS = 4
# context_user_id_bin - 5
CONTEXT_USER_ID_BIN_POS = 5
# context_parent_id_bin - 6
CONTEXT_PARENT_ID_BIN_POS = 6
# state - 7
STATE_POS = 7
# entity_id - 8
ENTITY_ID_POS = 8
# icon - 9
ICON_POS = 9
# context_only - 10
CONTEXT_ONLY_POS = 10
# - For EventAsRow, additional fields are:
# data - 11
DATA_POS = 11
# context - 12
CONTEXT_POS = 12


class EventAsRow(NamedTuple):
    """Convert an event to a row.

    This much always match the order of the columns in queries/common.py
    """

    row_id: int
    event_type: EventType[Any] | str | None
    event_data: str | None
    time_fired_ts: float
    context_id_bin: bytes
    context_user_id_bin: bytes | None
    context_parent_id_bin: bytes | None
    state: str | None
    entity_id: str | None
    icon: str | None
    context_only: bool | None

    # Additional fields for EventAsRow
    data: Mapping[str, Any]
    context: Context


@callback
def async_event_to_row(event: Event) -> EventAsRow:
    """Convert an event to a row."""
    if event.event_type != EVENT_STATE_CHANGED:
        context = event.context
        return EventAsRow(
            row_id=hash(event),
            event_type=event.event_type,
            event_data=None,
            time_fired_ts=event.time_fired_timestamp,
            context_id_bin=ulid_to_bytes(context.id),
            context_user_id_bin=uuid_hex_to_bytes_or_none(context.user_id),
            context_parent_id_bin=ulid_to_bytes_or_none(context.parent_id),
            state=None,
            entity_id=None,
            icon=None,
            context_only=None,
            data=event.data,
            context=event.context,
        )
    # States are prefiltered so we never get states
    # that are missing new_state or old_state
    # since the logbook does not show these
    new_state: State = event.data["new_state"]
    context = new_state.context
    return EventAsRow(
        row_id=hash(event),
        event_type=None,
        event_data=None,
        time_fired_ts=new_state.last_updated_timestamp,
        context_id_bin=ulid_to_bytes(context.id),
        context_user_id_bin=uuid_hex_to_bytes_or_none(context.user_id),
        context_parent_id_bin=ulid_to_bytes_or_none(context.parent_id),
        state=new_state.state,
        entity_id=new_state.entity_id,
        icon=new_state.attributes.get(ATTR_ICON),
        context_only=None,
        data=event.data,
        context=event.context,
    )
