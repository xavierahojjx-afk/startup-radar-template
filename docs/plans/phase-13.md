# Phase 13 Execution Plan — `httpx` migration + shared `Client`

> Close the last Tier 0 bug (`docs/PRODUCTION_REFACTOR_PLAN.md` §1 row 6: "Inconsistent HTTP timeouts — only EDGAR sets one"). Retire the `requests` import in our three network sources, route every outbound HTTP call through a shared `httpx.Client` singleton whose default `timeout` is sourced from `cfg.network.timeout_seconds`, and delete the `socket.setdefaulttimeout(20)` module-load hack in `sources/rss.py`. Sentry SDK wiring is **dropped from the plan** — single-user tool, structlog + `runs` + `doctor` already cover the observability surface. **Explicitly NOT** async pipeline (§4.6), **NOT** `aiolimiter` rate limiting (§4.5), **NOT** circuit-breaker skip gate (§4.4 deferred) — those are later phases.

## Phase summary

- **One HTTP surface: `startup_radar/http.py`.** Exposes `get_client(cfg: AppConfig) -> httpx.Client` — a lru-cached singleton keyed on the config instance. Default `timeout=cfg.network.timeout_seconds` (already wired in Phase 11, default `10`). Default `headers={"User-Agent": _DEFAULT_UA}` where `_DEFAULT_UA = f"startup-radar/{__version__} (+https://github.com/…)"`. EDGAR's per-request `User-Agent` override continues to win — `httpx` merges request headers over client defaults the same way `requests` does.
- **Why `httpx` over `requests`.** (1) Shared `Client` gives one place to set default timeout — kills the "inconsistent timeouts" bug without threading a `timeout=` kwarg through every call site. (2) Same sync API as `requests` so the diff stays small; async is available later (§4.6) without a second migration. (3) vcrpy 6.0 supports httpx natively — the existing `tests/fixtures/cassettes/` still work after a one-shot re-record. (4) Typed — `httpx.Response` has proper annotations, mypy stops complaining about `r.json() -> Any`.
- **Three call-sites migrate.** `sources/hackernews.py` (healthcheck + `_search`), `sources/sec_edgar.py` (healthcheck + `_fetch`), `sources/rss.py` (healthcheck + the hoisted-string `feedparser.parse` swap). `sources/gmail.py:48` keeps its `from google.auth.transport.requests import Request` — that's google-auth's internal `requests`-backed transport, transitively pulled by `google-auth-oauthlib`; replacing it is out of scope and not load-bearing.
- **`feedparser` stops reaching for the network itself.** Current `rss.py:110` calls `feedparser.parse(feed_url)` which opens its own HTTP connection (hence the `socket.setdefaulttimeout(20)` hack at module load). Phase 13 flips it: fetch the body with the shared `httpx.Client` (`r = client.get(url); r.raise_for_status()`), then `feedparser.parse(r.content)`. Delete the `socket.setdefaulttimeout` line and the corresponding gotcha in `.claude/CLAUDE.md`.
- **Retry helper exception tuple changes.** `_retry.py` callers pass `on=(requests.RequestException, TimeoutError)` today. After migration: `on=(httpx.HTTPError, TimeoutError)`. `httpx.HTTPError` is the root exception class — subsumes `ConnectError`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `HTTPStatusError` (only raised by `raise_for_status`), etc. No behavior change for retry surface; only the type name.
- **Drop `requests` from direct deps.** Today `pyproject.toml` line 14 lists `requests>=2.31.0`. After migration nothing under `startup_radar/` imports it directly. It stays *installed* (transitively via `google-api-python-client` → `google-auth-oauthlib` → `requests`) when the `[gmail]` extra is installed, which is fine — we just don't list it as a direct dep. Run `uv remove requests && uv add httpx`.
- **vcrpy re-record on first run.** vcrpy ≥6.0 supports httpx out of the box, but existing cassettes were recorded against `requests`'s urllib3 transport. Concretely: request headers/order can differ (httpx sorts `Host` differently, omits `Accept-Encoding: identity` by default). Rather than hand-edit YAML, delete the three cassette dirs and re-record: `rm -rf tests/fixtures/cassettes/{rss,hackernews,sec_edgar} && uv run pytest tests/integration/ -k "not ci_gate"`. Cassettes go back in the commit. EDGAR cassette scrubbing (`User-Agent: startup-radar-test`) stays — the scrubber hook in `tests/conftest.py` is transport-agnostic.
- **CI mode unchanged.** `CI=1` still flips vcrpy to `record_mode=none`; missing cassette → loud failure, same as today.
- **Typing stays tight.** `httpx.Client.get()` returns `httpx.Response` (typed). `response.json() -> Any` — same as `requests`. `mypy` stays green; no `# type: ignore` expected. `httpx` ships `py.typed`.
- **No new `cfg.network` knobs.** `timeout_seconds` is the only one needed; `Client` caches connections internally so no pool-size field.

## File changes

| File | Action | Detail |
|---|---|---|
| `startup_radar/http.py` | **new** | `get_client(cfg: AppConfig) -> httpx.Client` lru-cached on `id(cfg)`. Sets `timeout=cfg.network.timeout_seconds`, `headers={"User-Agent": _DEFAULT_UA}`, `follow_redirects=True`. Exports `_DEFAULT_UA` so EDGAR's override can reference it. Module docstring documents "one client per process; tests call `get_client.cache_clear()` in `conftest.py`". |
| `startup_radar/sources/hackernews.py` | edit | Drop `import requests`. Healthcheck `requests.get(...)` → `get_client(cfg).get(...)`, `except requests.RequestException` → `except httpx.HTTPError`. `_search` retry lambda same swap; retry `on=(httpx.HTTPError, TimeoutError)`. Drop the per-call `timeout=` kwarg (inherited from client). |
| `startup_radar/sources/sec_edgar.py` | edit | Same swap. EDGAR headers dict continues to carry the per-request `User-Agent` (compliance-required) — httpx merges it over the client default. Drop `timeout=` kwargs. |
| `startup_radar/sources/rss.py` | edit | Drop `import socket` and `socket.setdefaulttimeout(20)`. Healthcheck HEAD/GET switches to `client.head(...)` / `client.get(...)`. `_fetch_one` becomes `r = client.get(feed_url); r.raise_for_status(); parsed = feedparser.parse(r.content)` — `feedparser` no longer opens sockets. Retry wraps the `client.get` call, not the `feedparser.parse` (parsing is pure). |
| `startup_radar/sources/_retry.py` | no edit | Exception tuple is passed per-call by each source; helper body stays the same. (Docstring mentions `requests.RequestException` as an example — update the one-liner to `httpx.HTTPError`.) |
| `pyproject.toml` | edit via `uv` | `uv remove requests && uv add httpx`. `[project.dependencies]` gains `httpx>=0.27`; loses `requests>=2.31.0`. `uv.lock` regenerates. `requests` stays in the resolved graph via `google-auth-oauthlib` when `[gmail]` is installed — acceptable. |
| `tests/fixtures/cassettes/{rss,hackernews,sec_edgar}/` | regenerate | Delete + re-record locally (first pytest run under `record_mode=once`). Commit the fresh YAMLs. EDGAR UA scrubbing in `tests/conftest.py` still applies. |
| `tests/conftest.py` | edit | Two-line addition next to the `secrets.cache_clear()` autouse: `get_client.cache_clear()` between tests so per-test `cfg.network.timeout_seconds` tweaks don't leak. |
| `tests/unit/test_http.py` | **new** | Four cases: (1) `get_client(cfg)` returns same instance across calls with same `cfg`. (2) Default timeout matches `cfg.network.timeout_seconds`. (3) Default `User-Agent` is set and contains `startup-radar/`. (4) `get_client.cache_clear()` forces a new instance. |
| `.claude/CLAUDE.md` | edit | **Core invariants** block: drop the `feedparser` exception callout ("`feedparser` is the exception — see `sources/rss.py`"). Replace with "every outbound HTTP call goes through `startup_radar.http.get_client(cfg)` — no bare `httpx.get` / `requests.*` in `startup_radar/`". **Gotchas** block: delete the "`feedparser` doesn't take a `timeout` kwarg" bullet (no longer true). Add "shared `httpx.Client` is cached per-process via `get_client(cfg)`; tests call `get_client.cache_clear()` in `conftest.py` alongside `secrets.cache_clear()`". |
| `.claude/hooks/pre-commit-check.sh` | edit | If the hook currently greps for `^import requests` / `^from requests` under `startup_radar/` (it may not — confirm), tighten it: allow only `gmail.py`'s `google.auth.transport.requests` line, deny everything else. One-line addition if needed. |
| `docs/PRODUCTION_REFACTOR_PLAN.md` | edit | Row 1 (Tier 0 bug #6) — mark `✅ FIXED (Phase 13)`. §3.1 — no change (already lists `httpx>=0.27`). §4.4 — strike the Sentry bullet (single-user tool; dropped). §4.4 "Deferred" — leave httpx line but reword: "~~shared `httpx.Client` migration~~ ✅ Phase 13. Circuit-breaker semantics still deferred." Add `Tag: phase-13` on the corresponding row. |

## Out of scope

- **Sentry SDK.** Dropped from the plan — this is a single-user local tool. structlog + `runs` table + `doctor`'s `⚠ source.<key>.streak` already surface source failures. The `sentry_dsn` field on `Secrets` stays defined (harmless) so a future user who wants Sentry can wire it without a schema change — but no `sentry_sdk.init()` call is added.
- **Async pipeline (`httpx.AsyncClient`).** §4.6 — deferred. The sync `Client` migration is the 90% win; going async is a second refactor, not part of this one.
- **`aiolimiter` rate limiting.** §4.5 — deferred. EDGAR's ≤10 req/s is already honored by the current sequential pipeline (we make one request per issuer per run, well under the limit). Revisit only if the EDGAR source grows a multi-issuer fan-out.
- **Circuit-breaker skip gate.** §4.4 — deferred. `storage.failure_streak` exists; `pipeline()` still runs every enabled source every run. Skip-after-N-failures is its own phase.
- **Dropping `requests` from the resolved dep graph.** Impossible without ripping out `[gmail]` extra (transitively depends on `requests`). Out of scope; not worth it.
- **Dashboard changes.** No new config knobs, no "HTTP client: httpx" diagnostic panel.
- **Windows-specific quirks.** httpx uses the same `certifi` bundle as `requests`; no Windows cert-store shim needed.

## Tests

Six new / touched test points:

1. `tests/unit/test_http.py` — the four cases listed above.
2. `tests/integration/test_rss.py`, `test_hackernews.py`, `test_sec_edgar.py` — re-recorded cassettes. Failure-path tests (`httpx.ConnectError` / `httpx.ReadTimeout`) replace the old `requests.ConnectionError` variants; retry `on=` tuple change is covered.
3. `tests/unit/test_retry_backoff.py` (existing) — confirm it still asserts 3 attempts × `(1,2,4)` s backoff with the new exception types. One-line `pytest.raises(httpx.HTTPError)` swap.
4. `tests/conftest.py` — new `get_client.cache_clear()` autouse; verified by running integration tests twice in one session (no cached-client leak).
5. `make ci` green: ruff + format-check + mypy + full pytest, ≥80% coverage maintained.
6. Manual: `uv run startup-radar run` against live network — sanity-check that all three sources return at least one item each with the new client.

## Exit criteria

- [ ] `startup_radar/http.py` exists with `get_client(cfg)` + `_DEFAULT_UA` + `get_client.cache_clear()` exposed.
- [ ] `grep -rn "^import requests\|^from requests" startup_radar/` returns only `sources/gmail.py:48` (the `google.auth.transport.requests.Request` line).
- [ ] `grep -rn "socket\.setdefaulttimeout" startup_radar/` returns zero matches.
- [ ] `requests` removed from `[project.dependencies]`; `httpx>=0.27` added. `uv.lock` regenerated.
- [ ] Three cassette directories re-recorded and committed.
- [ ] `tests/unit/test_http.py` passes all four cases.
- [ ] `make ci` green on the phase-13 branch.
- [ ] `uv run startup-radar doctor --network` reports all three HTTP sources healthy end-to-end.
- [ ] `docs/PRODUCTION_REFACTOR_PLAN.md` Tier 0 row 6 flipped to ✅; Sentry bullet struck from §4.4.
- [ ] `.claude/CLAUDE.md` gotcha about `feedparser` timeout removed; `http.get_client` gotcha added.
- [ ] Commit message follows Conventional Commits: `feat(http): shared httpx.Client + retire requests (Phase 13)`.
- [ ] Tag: `phase-13`.
