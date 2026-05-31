"""Shared runtime state — stop events for running jobs."""
import asyncio

_stop_events: dict[int, asyncio.Event] = {}


def acquire(uid: int) -> asyncio.Event:
    ev = asyncio.Event()
    _stop_events[uid] = ev
    return ev


def release(uid: int) -> None:
    _stop_events.pop(uid, None)


def trigger(uid: int) -> bool:
    ev = _stop_events.get(uid)
    if ev:
        ev.set()
        return True
    return False


def is_running(uid: int) -> bool:
    return uid in _stop_events
