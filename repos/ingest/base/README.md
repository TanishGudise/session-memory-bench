# ingest

Loads partner feeds (orders, returns, shipments) into the warehouse.

- `ingest/feeds/`: one module per partner feed, registered in `FEEDS` (`ingest/feeds/base.py`)
- `ingest/schema.py`: the record every feed produces
- `ingest/loader.py`, `ingest/warehouse.py`: loading parsed records
- `python -m ingest.cli <feed> <file>`

Run the tests with `python -m pytest`.
