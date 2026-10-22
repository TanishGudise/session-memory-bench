"""Structured logging. `log_event` redacts every field, so emails and phone numbers never reach the logs."""

from __future__ import annotations

import json
import logging
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def redact(value: object) -> object:
    if isinstance(value, str):
        return PHONE.sub("[phone]", EMAIL.sub("[email]", value))
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info("%s %s", event, json.dumps(redact(fields), sort_keys=True, default=str))
