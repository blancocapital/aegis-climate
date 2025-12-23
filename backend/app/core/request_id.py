import contextvars
import uuid
from typing import Optional

_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def generate_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(request_id: Optional[str]) -> contextvars.Token:
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id_var.reset(token)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()
