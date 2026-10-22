"""Importing this package registers every feed in FEEDS."""

from ingest.feeds import acme, acme_returns, pinecrest  # noqa: F401
from ingest.feeds.base import FEEDS, ParseResult, register  # noqa: F401
