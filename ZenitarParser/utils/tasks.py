import asyncio
import itertools
from typing import Dict

# Monotonic task ids — never reused, unlike id(obj)
_counter = itertools.count(1)
active_tasks: Dict[int, asyncio.Event] = {}


def new_task() -> tuple[int, asyncio.Event]:
    task_id = next(_counter)
    event = asyncio.Event()
    active_tasks[task_id] = event
    return task_id, event


def stop_task(task_id: int) -> bool:
    event = active_tasks.get(task_id)
    if event:
        event.set()
        return True
    return False


def done_task(task_id: int):
    active_tasks.pop(task_id, None)
