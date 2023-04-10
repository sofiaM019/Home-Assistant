"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, MutableMapping
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from typing import Any, cast

from sqlalchemy import Column, CompoundSelect, Select, and_, func, select, union_all
from sqlalchemy.engine.row import Row
from sqlalchemy.orm.properties import MappedColumn
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal

from homeassistant.const import COMPRESSED_STATE_LAST_UPDATED, COMPRESSED_STATE_STATE
from homeassistant.core import HomeAssistant, State, split_entity_id
import homeassistant.util.dt as dt_util

from ... import recorder
from ..db_schema import StateAttributes, States
from ..filters import Filters
from ..models import (
    LazyState,
    extract_metadata_ids,
    process_timestamp,
    row_to_compressed_state,
)
from ..util import execute_stmt_lambda_element, session_scope
from .const import (
    LAST_CHANGED_KEY,
    NEED_ATTRIBUTE_DOMAINS,
    SIGNIFICANT_DOMAINS,
    STATE_KEY,
)

_QUERY_STATE_NO_ATTR = (
    States.metadata_id,
    States.state,
    States.last_changed_ts,
    States.last_updated_ts,
)
_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED = (  # type: ignore[var-annotated]
    States.metadata_id,
    States.state,
    literal(value=None).label("last_changed_ts"),
    States.last_updated_ts,
)
_QUERY_STATES = (
    *_QUERY_STATE_NO_ATTR,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_QUERY_STATES_NO_LAST_CHANGED = (
    *_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED,
    # Remove States.attributes once all attributes are in StateAttributes.shared_attrs
    States.attributes,
    StateAttributes.shared_attrs,
)
_FIELD_MAP = {
    cast(MappedColumn, field).name: idx
    for idx, field in enumerate(_QUERY_STATE_NO_ATTR)
}


def _stmt_and_join_attributes(
    no_attributes: bool, include_last_changed: bool = True
) -> Select:
    """Return the statement and if StateAttributes should be joined."""
    # If no_attributes was requested we do the query
    # without the attributes fields and do not join the
    # state_attributes table
    if no_attributes:
        if include_last_changed:
            return select(*_QUERY_STATE_NO_ATTR)
        return select(*_QUERY_STATE_NO_ATTR_NO_LAST_CHANGED)

    if include_last_changed:
        return select(*_QUERY_STATES)
    return select(*_QUERY_STATES_NO_LAST_CHANGED)


def _select_from_union(union: CompoundSelect, no_attributes: bool) -> Select:
    """Return the statement to select from the union."""
    if no_attributes:
        return select(
            union.c.metadata_id,
            union.c.state,
            union.c.last_changed_ts,
            union.c.last_updated_ts,
        )
    return select(
        union.c.metadata_id,
        union.c.state,
        union.c.last_changed_ts,
        union.c.last_updated_ts,
        union.c.attributes,
        union.c.shared_attrs,
    )


def get_significant_states(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Wrap get_significant_states_with_session with an sql session."""
    with session_scope(hass=hass, read_only=True) as session:
        return get_significant_states_with_session(
            hass,
            session,
            start_time,
            end_time,
            entity_ids,
            filters,
            include_start_time_state,
            significant_changes_only,
            minimal_response,
            no_attributes,
            compressed_state_format,
        )


def _significant_states_stmt(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int],
    metadata_ids_in_significant_domains: list[int],
    significant_changes_only: bool,
    no_attributes: bool,
    include_start_time_state: bool,
) -> Select | CompoundSelect:
    """Query the database for significant state changes."""
    stmt = _stmt_and_join_attributes(
        no_attributes, include_last_changed=not significant_changes_only
    )
    if significant_changes_only:
        # Since we are filtering on entity_id (metadata_id) we can avoid
        # the join of the states_meta table since we already know which
        # metadata_ids are in the significant domains.
        stmt = stmt.filter(
            States.metadata_id.in_(metadata_ids_in_significant_domains)
            | (States.last_changed_ts == States.last_updated_ts)
            | States.last_changed_ts.is_(None)
        )
    stmt = stmt.filter(States.metadata_id.in_(metadata_ids))
    start_time_ts = start_time.timestamp()
    stmt = stmt.filter(States.last_updated_ts > start_time_ts)
    if end_time:
        end_time_ts = end_time.timestamp()
        stmt = stmt.filter(States.last_updated_ts < end_time_ts)
    if not no_attributes:
        stmt = stmt.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    if not include_start_time_state:
        return stmt.order_by(States.metadata_id, States.last_updated_ts)
    union = union_all(
        _get_start_time_state_stmt(hass, start_time, metadata_ids, no_attributes),
        stmt,
    ).subquery()
    outer_stmt = _select_from_union(union, no_attributes)
    outer_stmt.order_by(union.c.metadata_id, union.c.last_updated_ts)
    return outer_stmt


def get_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
    compressed_state_format: bool = False,
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Return states changes during UTC period start_time - end_time.

    entity_ids is an optional iterable of entities to include in the results.

    filters is an optional SQLAlchemy filter which will be applied to the database
    queries unless entity_ids is given, in which case its ignored.

    Significant states are all states where there is a state change,
    as well as all states from certain domains (for instance
    thermostat so that we get current temperature in our graphs).
    """
    if filters is not None:
        raise NotImplementedError("Filters are no longer supported")
    if not entity_ids:
        raise ValueError("entity_ids must be provided")
    metadata_ids: list[int] | None = None
    entity_id_to_metadata_id: dict[str, int | None] | None = None
    metadata_ids_in_significant_domains: list[int] = []
    instance = recorder.get_instance(hass)
    if not (
        entity_id_to_metadata_id := instance.states_meta_manager.get_many(
            entity_ids, session, False
        )
    ) or not (metadata_ids := extract_metadata_ids(entity_id_to_metadata_id)):
        return {}
    if significant_changes_only:
        metadata_ids_in_significant_domains = [
            metadata_id
            for entity_id, metadata_id in entity_id_to_metadata_id.items()
            if metadata_id is not None
            and split_entity_id(entity_id)[0] in SIGNIFICANT_DOMAINS
        ]
    stmt = _significant_states_stmt(
        hass,
        start_time,
        end_time,
        metadata_ids,
        metadata_ids_in_significant_domains,
        significant_changes_only,
        no_attributes,
        include_start_time_state,
    )
    states = execute_stmt_lambda_element(session, stmt, None, end_time)
    return _sorted_states_to_dict(
        states,
        entity_ids,
        entity_id_to_metadata_id,
        minimal_response,
        compressed_state_format,
    )


def get_full_significant_states_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_ids: list[str] | None = None,
    filters: Filters | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    no_attributes: bool = False,
) -> MutableMapping[str, list[State]]:
    """Variant of get_significant_states_with_session.

    Difference with get_significant_states_with_session is that it does not
    return minimal responses.
    """
    return cast(
        MutableMapping[str, list[State]],
        get_significant_states_with_session(
            hass=hass,
            session=session,
            start_time=start_time,
            end_time=end_time,
            entity_ids=entity_ids,
            filters=filters,
            include_start_time_state=include_start_time_state,
            significant_changes_only=significant_changes_only,
            minimal_response=False,
            no_attributes=no_attributes,
        ),
    )


def _state_changed_during_period_stmt(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None,
    metadata_id: int,
    no_attributes: bool,
    descending: bool,
    limit: int | None,
    include_start_time_state: bool | None = None,
) -> Select | CompoundSelect:
    stmt = _stmt_and_join_attributes(no_attributes, include_last_changed=False)
    start_time_ts = start_time.timestamp()
    stmt = stmt.filter(
        (
            (States.last_changed_ts == States.last_updated_ts)
            | States.last_changed_ts.is_(None)
        )
        & (States.last_updated_ts > start_time_ts)
    )
    if end_time:
        end_time_ts = end_time.timestamp()
        stmt = stmt.filter(States.last_updated_ts < end_time_ts)
    stmt = stmt.filter(States.metadata_id == metadata_id)
    if not no_attributes:
        stmt = stmt.outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        )
    if not include_start_time_state:
        if descending:
            stmt = stmt.order_by(States.metadata_id, States.last_updated_ts.desc())
        else:
            stmt = stmt.order_by(States.metadata_id, States.last_updated_ts)
        if limit:
            stmt = stmt.limit(limit)
        return stmt
    union = union_all(
        stmt, _get_start_time_state_stmt(hass, start_time, [metadata_id], no_attributes)
    ).subquery()
    outer_stmt = _select_from_union(union, no_attributes)
    if descending:
        return outer_stmt.order_by(union.c.metadata_id, union.c.last_updated_ts.desc())
    if limit:
        outer_stmt = outer_stmt.limit(limit)
    return outer_stmt.order_by(union.c.metadata_id, union.c.last_updated_ts)


def state_changes_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    entity_id: str | None = None,
    no_attributes: bool = False,
    descending: bool = False,
    limit: int | None = None,
    include_start_time_state: bool = True,
) -> MutableMapping[str, list[State]]:
    """Return states changes during UTC period start_time - end_time."""
    if not entity_id:
        raise ValueError("entity_id must be provided")
    entity_ids = [entity_id.lower()]

    with session_scope(hass=hass, read_only=True) as session:
        metadata_id: int | None = None
        instance = recorder.get_instance(hass)
        if not (
            metadata_id := instance.states_meta_manager.get(entity_id, session, False)
        ):
            return {}
        entity_id_to_metadata_id: dict[str, int | None] = {entity_id: metadata_id}
        stmt = _state_changed_during_period_stmt(
            hass,
            start_time,
            end_time,
            metadata_id,
            no_attributes,
            descending,
            limit,
            include_start_time_state,
        )
        states = execute_stmt_lambda_element(session, stmt, None, end_time)
        return cast(
            MutableMapping[str, list[State]],
            _sorted_states_to_dict(
                states,
                entity_ids,
                entity_id_to_metadata_id,
            ),
        )


def _get_last_state_changes_stmt(number_of_states: int, metadata_id: int) -> Select:
    stmt = _stmt_and_join_attributes(False, include_last_changed=False)
    if number_of_states == 1:
        stmt = stmt.join(
            (
                lastest_state_for_metadata_id := (
                    select(
                        States.metadata_id.label("max_metadata_id"),
                        # https://github.com/sqlalchemy/sqlalchemy/issues/9189
                        # pylint: disable-next=not-callable
                        func.max(States.last_updated_ts).label("max_last_updated"),
                    )
                    .filter(States.metadata_id == metadata_id)
                    .group_by(States.metadata_id)
                    .subquery()
                )
            ),
            and_(
                States.metadata_id == lastest_state_for_metadata_id.c.max_metadata_id,
                States.last_updated_ts
                == lastest_state_for_metadata_id.c.max_last_updated,
            ),
        )
    else:
        stmt = stmt.where(
            States.state_id
            == (
                select(States.state_id)
                .filter(States.metadata_id == metadata_id)
                .order_by(States.last_updated_ts.desc())
                .limit(number_of_states)
                .subquery()
            ).c.state_id
        )
    stmt = stmt.outerjoin(
        StateAttributes, States.attributes_id == StateAttributes.attributes_id
    ).order_by(States.state_id.desc())
    return stmt


def get_last_state_changes(
    hass: HomeAssistant, number_of_states: int, entity_id: str
) -> MutableMapping[str, list[State]]:
    """Return the last number_of_states."""
    entity_id_lower = entity_id.lower()
    entity_ids = [entity_id_lower]

    # Calling this function with number_of_states > 1 can cause instability
    # because it has to scan the table to find the last number_of_states states
    # because the metadata_id_last_updated_ts index is in ascending order.

    with session_scope(hass=hass, read_only=True) as session:
        instance = recorder.get_instance(hass)
        if not (
            metadata_id := instance.states_meta_manager.get(entity_id, session, False)
        ):
            return {}
        entity_id_to_metadata_id: dict[str, int | None] = {entity_id_lower: metadata_id}
        stmt = _get_last_state_changes_stmt(number_of_states, metadata_id)
        states = list(execute_stmt_lambda_element(session, stmt))
        return cast(
            MutableMapping[str, list[State]],
            _sorted_states_to_dict(
                reversed(states),
                entity_ids,
                entity_id_to_metadata_id,
            ),
        )


def _get_states_for_entities_stmt(
    run_start: datetime,
    utc_point_in_time: datetime,
    metadata_ids: list[int],
    no_attributes: bool,
) -> Select:
    """Baked query to get states for specific entities."""
    stmt = _stmt_and_join_attributes(no_attributes, include_last_changed=True)
    # We got an include-list of entities, accelerate the query by filtering already
    # in the inner query.
    run_start_ts = process_timestamp(run_start).timestamp()
    utc_point_in_time_ts = dt_util.utc_to_timestamp(utc_point_in_time)
    stmt = stmt.join(
        (
            most_recent_states_for_entities_by_date := (
                select(
                    States.metadata_id.label("max_metadata_id"),
                    # https://github.com/sqlalchemy/sqlalchemy/issues/9189
                    # pylint: disable-next=not-callable
                    func.max(States.last_updated_ts).label("max_last_updated"),
                )
                .filter(
                    (States.last_updated_ts >= run_start_ts)
                    & (States.last_updated_ts < utc_point_in_time_ts)
                )
                .filter(States.metadata_id.in_(metadata_ids))
                .group_by(States.metadata_id)
                .subquery()
            )
        ),
        and_(
            States.metadata_id
            == most_recent_states_for_entities_by_date.c.max_metadata_id,
            States.last_updated_ts
            == most_recent_states_for_entities_by_date.c.max_last_updated,
        ),
    )
    if not no_attributes:
        stmt = stmt.outerjoin(
            StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
        )
    return stmt


def _get_start_time_state_stmt(
    hass: HomeAssistant,
    utc_point_in_time: datetime,
    metadata_ids: list[int],
    no_attributes: bool = False,
) -> Select:
    """Return the states at a specific point in time."""
    run = recorder.get_instance(hass).recorder_runs_manager.get(utc_point_in_time)
    start_time: datetime | None = None
    if run is None or (start_time := process_timestamp(run.start)) > utc_point_in_time:
        # History did not run before utc_point_in_time but we still
        # need to generate the query so the cache key is correct.
        metadata_ids = [-1]
    if start_time is None:
        start_time = dt_util.utcnow()
    # We have more than one entity to look at so we need to do a query on states
    # since the last recorder run started.
    return _get_states_for_entities_stmt(
        start_time, utc_point_in_time, metadata_ids, no_attributes
    )


def _sorted_states_to_dict(
    states: Iterable[Row],
    entity_ids: list[str],
    entity_id_to_metadata_id: dict[str, int | None],
    minimal_response: bool = False,
    compressed_state_format: bool = False,
) -> MutableMapping[str, list[State | dict[str, Any]]]:
    """Convert SQL results into JSON friendly data structure.

    This takes our state list and turns it into a JSON friendly data
    structure {'entity_id': [list of states], 'entity_id2': [list of states]}

    States must be sorted by entity_id and last_updated

    We also need to go back and create a synthetic zero data point for
    each list of states, otherwise our graphs won't start on the Y
    axis correctly.
    """
    field_map = _FIELD_MAP
    state_class: Callable[
        [Row, dict[str, dict[str, Any]], datetime | None], State | dict[str, Any]
    ]
    if compressed_state_format:
        state_class = row_to_compressed_state
        attr_time = COMPRESSED_STATE_LAST_UPDATED
        attr_state = COMPRESSED_STATE_STATE
    else:
        state_class = LazyState
        attr_time = LAST_CHANGED_KEY
        attr_state = STATE_KEY

    result: dict[str, list[State | dict[str, Any]]] = defaultdict(list)
    metadata_id_to_entity_id: dict[int, str] = {}
    metadata_id_idx = field_map["metadata_id"]

    # Set all entity IDs to empty lists in result set to maintain the order
    for ent_id in entity_ids:
        result[ent_id] = []

    metadata_id_to_entity_id = {
        v: k for k, v in entity_id_to_metadata_id.items() if v is not None
    }
    # Get the states at the start time
    if len(entity_ids) == 1:
        metadata_id = entity_id_to_metadata_id[entity_ids[0]]
        assert metadata_id is not None  # should not be possible if we got here
        states_iter: Iterable[tuple[int, Iterator[Row]]] = (
            (metadata_id, iter(states)),
        )
    else:
        key_func = itemgetter(metadata_id_idx)
        states_iter = groupby(states, key_func)

    # Append all changes to it
    for metadata_id, group in states_iter:
        attr_cache: dict[str, dict[str, Any]] = {}
        prev_state: Column | str | None = None
        if not (entity_id := metadata_id_to_entity_id.get(metadata_id)):
            continue
        ent_results = result[entity_id]
        if (
            not minimal_response
            or split_entity_id(entity_id)[0] in NEED_ATTRIBUTE_DOMAINS
        ):
            ent_results.extend(
                state_class(db_state, attr_cache, None, entity_id=entity_id)  # type: ignore[call-arg]
                for db_state in group
            )
            continue

        # With minimal response we only provide a native
        # State for the first and last response. All the states
        # in-between only provide the "state" and the
        # "last_changed".
        if not ent_results:
            if (first_state := next(group, None)) is None:
                continue
            prev_state = first_state.state
            ent_results.append(
                state_class(first_state, attr_cache, None, entity_id=entity_id)  # type: ignore[call-arg]
            )

        state_idx = field_map["state"]
        last_updated_ts_idx = field_map["last_updated_ts"]

        #
        # minimal_response only makes sense with last_updated == last_updated
        #
        # We use last_updated for for last_changed since its the same
        #
        # With minimal response we do not care about attribute
        # changes so we can filter out duplicate states
        if compressed_state_format:
            # Compressed state format uses the timestamp directly
            ent_results.extend(
                {
                    attr_state: (prev_state := state),
                    attr_time: row[last_updated_ts_idx],
                }
                for row in group
                if (state := row[state_idx]) != prev_state
            )
            continue

        # Non-compressed state format returns an ISO formatted string
        _utc_from_timestamp = dt_util.utc_from_timestamp
        ent_results.extend(
            {
                attr_state: (prev_state := state),  # noqa: F841
                attr_time: _utc_from_timestamp(row[last_updated_ts_idx]).isoformat(),
            }
            for row in group
            if (state := row[state_idx]) != prev_state
        )

    # Filter out the empty lists if some states had 0 results.
    return {key: val for key, val in result.items() if val}
