# Taxi Availability

Report the top areas with the most available taxis in Singapore, using the
[data.gov.sg Taxi Availability API](https://data.gov.sg/datasets/d_e25662f1a062dd046453926aa284ba64/view).

For a live snapshot the application:

1. Fetches the realtime taxi-availability GeoJSON (one `MultiPoint` of every
   available taxi, plus an authoritative `taxi_count`).
2. Groups the taxis into areas of high concentration (see
   [Grouping strategies](#grouping-strategies)) and ranks the areas by taxi
   count.
3. Reverse-geocodes each of the top areas to an address in words
   (via Nominatim / OpenStreetMap — **no API key required**).
4. Prints the total, the ranked areas, and a Google Maps link for each.

## Requirements

- **Python 3.13+**
- [**uv**](https://docs.astral.sh/uv/) for dependency management

No API keys are needed. Reverse geocoding uses the public Nominatim service.

## Setup

```bash
uv sync
```

This creates a virtual environment and installs the dependencies pinned in
`uv.lock`.

## Usage

Run against the live API:

```bash
uv run python main.py
```

Options:

| Option | Description |
| --- | --- |
| `--strategy {hotspot,grid}` | Grouping strategy (default `hotspot`). |
| `--top N` | Number of top areas to report (default `10`). |
| `--radius-m METRES` | Radius of each area's footprint — `hotspot` only (default `500`). |
| `--precision DP` | Decimal places for the reported coordinate (default `2`). |
| `--config PATH` | TOML config file of the settings above (CLI flags override it). |
| `--source PATH` | Read taxi-availability GeoJSON from a local file instead of the live API — useful offline, e.g. the bundled sample fixture. |

Run offline against the bundled sample snapshot, using the grid strategy:

```bash
uv run python main.py --source tests/fixtures/taxi_availability_sample.json --strategy grid
```

The live fetch retries transient failures (connection/timeout errors, `429`/`5xx`
responses) with exponential backoff. On an expected failure — an unreachable
API, an unreadable `--source`/`--config` file, a bad config, or malformed data —
the program prints a one-line `Error: …` to stderr and exits non-zero (`1`)
rather than a traceback.

### Configuration file

Instead of flags, settings can live in a TOML file (any CLI flag still
overrides it). See [`config.example.toml`](config.example.toml):

```toml
strategy = "hotspot"   # "hotspot" or "grid"
top = 10               # number of areas to report
radius_m = 500         # hotspot footprint radius in metres (hotspot only)
precision = 2          # decimal places for the reported coordinate
```

```bash
uv run python main.py --config config.example.toml
```

### Example output

```
Total available taxis: 3378

Top 3 areas with the most taxis:
1. Lat: 1.36, Lon: 103.99 - 280 taxis
   Location: ..., Airport Boulevard, Changi, East Region, Singapore, 819666, Singapore
   Google Maps: https://www.google.com/maps/search/?api=1&query=1.36,103.99
2. Lat: 1.35, Lon: 103.98 - 87 taxis
   Location: ..., Changi, East Region, Singapore, 486798, Singapore
   Google Maps: https://www.google.com/maps/search/?api=1&query=1.35,103.98
3. Lat: 1.34, Lon: 103.98 - 67 taxis
   Location: T4 Flyover, Changi, ..., East Region, Singapore, 819645, Singapore
   Google Maps: https://www.google.com/maps/search/?api=1&query=1.34,103.98
```

> **Note on speed:** Nominatim's usage policy allows at most 1 request/second, so
> the application self-throttles. Reporting the top 10 areas makes up to 10
> reverse-geocode calls and therefore takes roughly 10 seconds against the live
> service. Results are cached in memory per run.

## Grouping strategies

Two interchangeable ways to turn taxi points into ranked areas, selected with
`--strategy`:

- **`hotspot`** (default) — grows each area from the densest taxi outward within
  `--radius-m`, greedily and without overlap. A crowd is captured whole no matter
  where it sits, so it does not suffer the grid's boundary-splitting; every area
  is the same-size circle, so counts are directly comparable. Uses numpy; the
  reported coordinate is the member centroid.
- **`grid`** — bins each taxi onto a fixed lat/lon grid by rounding to
  `--precision` decimals (~1.1 km cells at `2`). Pure Python, no numpy; the
  reported coordinate is the grid-cell label. Simpler, but a crowd straddling a
  cell boundary is split across cells.

On the sample snapshot the difference is real: the grid reports the Changi
Airport crowd as several adjacent cells (top cell ≈ 237 taxis), while `hotspot`
consolidates it into one area (≈ 280) and surfaces genuinely distinct areas
lower in the ranking.

## Choosing the grouping method

The grid strategy came first — it is the obvious reading of the sample output,
and it is simple and dependency-free. But a fixed grid has a flaw I wasn't happy
with: a genuine crowd that happens to straddle a cell boundary is split across
two or more cells, so it is under-counted and can rank below a smaller crowd that
sits neatly inside one cell. The grid lines are arbitrary — they ignore where the
taxis actually are.

So I wanted an alternative that groups taxis by where they genuinely cluster. I
came up with a **greedy fixed-radius hotspot** method: repeatedly take the
densest remaining taxi as a seed, claim every taxi within a fixed radius as its
area, and remove them so no taxi is counted twice. A crowd is captured whole,
wherever it sits, and because every area is the same-size circle, the counts stay
directly comparable as a measure of concentration.

I also evaluated **DBSCAN**, the standard density-based clustering algorithm. It
would likewise avoid the grid's boundary problem, but it produces clusters of
**arbitrary shape and size**. The assignment asks for each area to be reported as
a single latitude/longitude point (plus a Google Maps link), and an irregular,
variable-size blob is not faithfully represented by one point. A fixed-radius
hotspot, by contrast, *is* a centre point and a radius by construction — which
maps exactly onto what the required output format expects. DBSCAN would also add
two tuning parameters (`eps`, `min_samples`) and a heavier dependency for no gain
here, so I chose the greedy hotspot method.

Both strategies are kept and selectable via `--strategy`, with `hotspot` as the
default and `grid` retained as the simpler, zero-dependency baseline.

## Project structure

```text
.
├── main.py                   # CLI entry point: wires the pipeline together
├── src/
│   ├── fetcher.py            # fetch taxi-availability GeoJSON (with retries)
│   ├── model.py             # parse/validate GeoJSON into a typed snapshot
│   ├── grouping.py          # grid + hotspot strategies, ranked areas
│   ├── config.py            # resolve settings: defaults < TOML < CLI
│   ├── geocoding.py         # reverse-geocode (Nominatim) + Google Maps link
│   └── report.py            # render the report text
├── tests/                   # offline unit tests (no network, no keys)
│   └── fixtures/            # saved API snapshot for offline runs and tests
├── config.example.toml      # example configuration file
├── pyproject.toml           # project metadata, dependencies, tool config
├── .github/workflows/ci.yml # CI: ruff, black, mypy, pytest
└── README.md
```

## How it works

The code follows a *pure core, imperative shell* split so the decision logic is
testable without the network:

| Module | Responsibility | I/O? |
| --- | --- | --- |
| `src/fetcher.py` | GET the taxi-availability endpoint | network |
| `src/model.py` | Parse/validate the GeoJSON into a typed `TaxiAvailability` | pure |
| `src/grouping.py` | Group points into areas (grid or hotspot), ranked by count | pure |
| `src/config.py` | Resolve settings from defaults, a TOML file, and CLI flags | pure |
| `src/geocoding.py` | Reverse-geocode a coordinate; build the Maps link | network / pure |
| `src/report.py` | Render the report text | pure |
| `main.py` | Wire the pipeline together | shell |

## Development

Run the test suite (all tests are offline — no network, no keys):

```bash
uv run pytest
```

Lint, format, and type-check:

```bash
uv run ruff check .
uv run black .
uv run mypy
```

mypy runs in `--strict` mode over the shipped code (`src/` and `main.py`).

Continuous integration (`.github/workflows/ci.yml`) runs ruff, black `--check`,
mypy, and pytest on every push and pull request against Python 3.13.
