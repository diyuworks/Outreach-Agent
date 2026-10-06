"""
Follow-up state machine (spec Section 7).

For today's demo this is a plain Python state machine so it's fast to build
and easy to run live. The production version (Phase 3 of the full spec)
should implement this same logic as a LangGraph cyclic graph, since LangGraph
gives you built-in persistence and cleaner handling of "wait N days, then
re-enter the graph" as a real graph state rather than an if/else chain.
The node logic below maps 1:1 onto LangGraph nodes, so porting it later is
mostly mechanical: Initial Send -> Wait -> FollowUp1 -> Wait -> FollowUp2 ...
"""
from datetime import date
from enum import Enum
from core.state_store import StateStore


class FollowUpAction(str, Enum):
    SEND_INITIAL = "SEND_INITIAL"
    SEND_FOLLOW_UP = "SEND_FOLLOW_UP"
    WAIT = "WAIT"
    MOVE_TO_NURTURE = "MOVE_TO_NURTURE"
    STOPPED_REPLIED = "STOPPED_REPLIED"


MAX_FOLLOW_UPS = 3


def next_action(store: StateStore, lead_id: str, channel: str,
                as_of_date: date | None = None) -> FollowUpAction:
    """Determine what follow-up action is due for a lead+channel.

    Args:
        as_of_date: Override "today" for simulation / time-travel testing.
                    Defaults to date.today() so existing callers are unaffected.
    """
    today = as_of_date or date.today()
    state = store.get_follow_up_state(lead_id, channel)

    if state is None:
        return FollowUpAction.SEND_INITIAL

    if state["reply_received_at"]:
        return FollowUpAction.STOPPED_REPLIED

    if state["follow_up_count"] >= MAX_FOLLOW_UPS:
        return FollowUpAction.MOVE_TO_NURTURE

    if state["next_follow_up_date"] and date.fromisoformat(state["next_follow_up_date"]) <= today:
        return FollowUpAction.SEND_FOLLOW_UP

    return FollowUpAction.WAIT

