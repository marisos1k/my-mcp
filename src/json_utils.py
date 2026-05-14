"""Сериализация значений из БД в JSON-совместимые типы."""

from datetime import timedelta
from decimal import Decimal
from typing import Any


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, timedelta):
        return str(value)
    return value
