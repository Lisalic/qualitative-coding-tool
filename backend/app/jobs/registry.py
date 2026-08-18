"""Job-type -> handler registry.

Handlers are registered via the ``@register_handler("job_type")`` decorator
and looked up by ``jobs/service.py::_execute_job`` at run time. Keeping this
as a plain module-level dict (rather than e.g. entry points) matches the
in-process job runner in ``jobs/runner.py`` -- no real broker to route
through yet.
"""

from typing import Any, Awaitable, Callable

Handler = Callable[[int, dict[str, Any]], Awaitable[dict[str, Any]]]

_HANDLERS: dict[str, Handler] = {}


def register_handler(job_type: str) -> Callable[[Handler], Handler]:
    """Decorator: ``@register_handler("my_job_type")`` above an ``async def``
    handler with signature ``async def handler(job_id: int, payload: dict) -> dict``.
    """

    def _decorator(fn: Handler) -> Handler:
        _HANDLERS[job_type] = fn
        return fn

    return _decorator


def get_handler(job_type: str) -> Handler:
    """Look up the handler registered for ``job_type``.

    Raises ``ValueError`` with a helpful message if nothing was registered
    for it (e.g. a typo'd ``job_type`` or a handler module that was never
    imported).
    """
    try:
        return _HANDLERS[job_type]
    except KeyError as exc:
        raise ValueError(
            f"No job handler registered for job_type={job_type!r}. "
            f"Registered types: {sorted(_HANDLERS)!r}"
        ) from exc
