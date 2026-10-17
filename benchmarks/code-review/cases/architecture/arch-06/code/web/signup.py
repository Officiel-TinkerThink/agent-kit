"""Signup web form handler."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class SignupError(ValueError):
    """Raised when a signup form is rejected."""


class AccountStore(Protocol):
    def create(self, email: str, display_name: str) -> str: ...


@dataclass(frozen=True)
class SignupForm:
    email: str
    display_name: str


def handle_signup(form: SignupForm, store: AccountStore) -> str:
    """Validate the posted form and create the account; return the account id."""
    if not form.display_name.strip():
        raise SignupError("display name is required")
    if "@" not in form.email:
        raise SignupError("email address is invalid")
    account_id = store.create(form.email, form.display_name.strip())
    logger.info("signup accepted account_id=%s", account_id)
    return account_id
