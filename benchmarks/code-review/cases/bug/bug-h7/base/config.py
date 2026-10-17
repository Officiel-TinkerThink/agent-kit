"""Configuration constants for the session token store."""
from datetime import timedelta

IDLE_TIMEOUT = timedelta(minutes=30)
MAX_TOKENS_PER_SUBJECT = 5
