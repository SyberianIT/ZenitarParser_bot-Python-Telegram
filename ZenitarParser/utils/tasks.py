import asyncio
from typing import Dict

# Global registry of running task stop-events
active_tasks: Dict[int, asyncio.Event] = {}


def new_task() -> asyncio.Event:
    event = asyncio.Event()
    active_tasks[id(event)] = event
    return event


def stop_task(task_id: int) -> bool:
    event = active_tasks.get(task_id)
    if event:
        event.set()
        return True
    return False


def done_task(event: asyncio.Event):
    active_tasks.pop(id(event), None)
