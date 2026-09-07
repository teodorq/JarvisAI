# JARVIS OS

JARVIS OS is a Windows desktop assistant with a local-first runtime and an optional Azure cloud planner.

## What stays local

User memory, command history, Google tokens, voice models, logs, generated backups and commercial release artifacts are runtime data. They are intentionally excluded from Git and are created locally when needed.

## Requirements

- Windows 10 or Windows 11
- Python 3.13 (the checkpoint was verified with Python 3.13.7)
- A microphone is optional
- Azure and Google integrations are optional
- Cartesia and ElevenLabs text-to-speech are optional
- MetaTrader 5 desktop and its official Python package are optional for Forex PAPER data

## Fresh installation

1. Clone the repository and switch to the `develop` branch.
2. Run `install.bat`.
3. Run `start_jarvis.vbs` to start JARVIS OS without a console window.

The installer creates a local `.venv` environment. It uses `requirements-lock.txt` when available, so the verified package versions are reproducible.

## Tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For a quick source check:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app cloud_service software_engineer tools
```

## Local paper-trading foundation

JARVIS OS includes an owner-only, broker-neutral trading foundation for safe
simulation and research. It provides strict market models, conservative
pre-trade limits, an atomic local demo ledger, a tamper-evident audit chain, an
emergency stop and next-bar historical backtesting. Optional read-only market
data can feed the simulator, but there is no broker order connection, leverage
or path to real-money orders.

Historical research also supports a strict chronological holdout and rolling
walk-forward validation. Every test period follows its training period, future
test windows cannot overlap, fills still occur only on a later bar, and neither
result can automatically promote PAPER or send an order. The validator does not
claim to audit how external signals were generated; that remains a separate
anti-look-ahead requirement for every strategy adapter.

Say or type `Status paper tradingu` in owner mode to see the local readiness
snapshot. The feature is blocked in client mode. Detailed scope, limits and the
required gates before any future broker integration are documented in
[`TRADING_READINESS.md`](TRADING_READINESS.md). Paper results do not predict
live-market performance; this module is technical research infrastructure, not
investment advice.

The Forex PAPER layer scans seven major currency pairs, ranks deterministic
signals and applies portfolio-wide currency exposure limits. A local autonomous
cycle can open or close simulated positions, recheck risk at execution time,
persist an audit trail and reject duplicate cycles. The primary source can be a
local MetaTrader 5 terminal logged into a DEMO account; an OANDA Practice REST
adapter remains an alternative for regions where v20 is available. Twelve Data
cross-checks prices, NBP supplies the public USD/PLN reference and the public
weekly Forex Factory export supplies the economic calendar. Configuration is
absent by default, so the opening gate remains closed. No broker order route or
real-money execution surface is exposed.
`Holiday` entries are treated as high importance for the complete source-local
calendar day and affect only pairs containing that currency. Event or data
blocks remove every new entry, while a fully cross-checked close-only plan may
still reduce an existing PAPER position.

Before PAPER execution is enabled, use the observation-only cycle. It reads all
configured sources and 211 closed M15 bars per pair, calculates the same
assessment and proposed plan, then stops before the execution boundary.
Evidence is kept in the ignored, tamper-evident
`data/trading/forex_observations.json` journal and never promotes itself:

```powershell
.\.venv\Scripts\python.exe .\tools\run_forex_observation.py
.\.venv\Scripts\python.exe .\tools\run_forex_observation.py --status
```

On Windows, install the local PAPER autostart once:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\install_forex_observer_autostart.ps1
```

The limited interactive task starts only the configured OANDA TMS MT5 terminal,
waits for all seven local ticks and closed-bar series to become fresh, and runs
one local PAPER cycle every 15 minutes while the Forex market is open. This
readiness probe never calls the external providers and has no order surface.
Between full cycles, a close-only guard checks existing positions every 60
seconds using only local MT5 DEMO ticks and the local USD/PLN quote. It can
apply an existing stop loss or take profit but cannot create an entry, call an
external market-data provider or send a broker order.
MT5 stamps each candle at its opening time, so JARVIS
accepts the previous fully closed M15 candle for at most two M15 periods plus a
one-minute synchronization allowance; older data still fails closed. Set
`JARVIS_OS_FOREX_PAPER_AUTOPILOT_ENABLED=true` in the ignored
`config/forex.env` to explicitly activate it. Every cycle records its
observation before it may update the local PAPER ledger. The runtime requires
the `MT5_DEMO` primary source, opens no web pages and exposes no broker order
route. Positions are visible in JARVIS OS, not in MetaTrader. Remove the task
with the same command plus `-Remove`.

Run one enabled cycle manually with:

```powershell
.\.venv\Scripts\python.exe .\tools\run_forex_paper_cycle.py
```

This explicit demo override may test an unvalidated strategy, but it still
enforces 0.25% risk per trade, 0.5% total open risk, a 1% daily loss stop, a 2%
weekly loss stop against the initial PAPER balance and at most two local PAPER
positions. The weekly gate uses audited closed PAPER fills from Monday 00:00 UTC;
it blocks only new entries and resets automatically with the next week. After
three consecutive closed losses it also
pauses new entries for six hours. The cooldown is derived from the persistent
tamper-evident fill history, survives restarts and never blocks verified position
closes. It cannot send MT5, broker or real-money orders.

In owner mode, say or type `Ile obserwacji Forex?`,
`Status obserwatora Forex` or `Czy PAPER jest gotowy?`. JARVIS reads the local
tamper-evident journal and reports qualified observations, distinct market days,
the remaining gate and whether PAPER execution is actually enabled. The same
status also reports the local Forex PAPER balance, realized result, open and
closed positions, processed cycle count, latest decision and data-block reasons.
It loads the ignored `config/forex.env` through the allowlisted loader but never
shows a key or token.

While the local MT5 DEMO autopilot is explicitly enabled, the JARVIS owner UI
also polls the bounded watchdog result and displays a deduplicated notification
for simulated opens, closes, the first data-block transition and recovery. It
does not speak these alerts, repeat an already-seen cycle, expose credentials or
add any broker-order capability.

The owner sidebar now includes a `FOREX PAPER` page. It refreshes every five
seconds and shows the sanitized local PAPER balance, equity, unrealized result,
position count, pair, direction, units, entry, current price, stop loss and take
profit. The page has no buy, sell or close controls and cannot route broker
orders. The `status Forex` command also lists the currently open PAPER entries.
When a safe cycle blocks new entries, the dashboard and durable activity history
show the validated reason (including a high-impact macro window and its affected
pairs) while making clear that verified PAPER closes remain active.
It also derives a read-only performance review from closed fills that match the
tamper-evident execution audit and reconcile with the PAPER balance. The second
metric row shows sample progress, average trade result, profit factor and the
maximum closed-equity drawdown. Twenty valid closed trades only make the sample
available for manual review; they never validate the strategy or enable LIVE.
The `WYNIKI PAR` tab keeps the same metrics separate for all seven configured
pairs and shows each pair's progress toward 20 closed PAPER trades. A completed
pair sample only opens a manual review; it never enables, disables or promotes a
pair automatically. Every new opening must also carry the exact deterministic
sample-contract fingerprint covering the scanner, risk limits, universe and fill
model. The two earlier unversioned fills remain in all-time history but are not
silently merged into the new frozen sample. Average result, win rate, profit
factor and drawdown shown for review use only that current contract. A separate
all-time summary preserves the complete account history and balance
reconciliation without contaminating the comparable sample. Current-contract
diagnostics also report holding-time coverage and separate stop-loss,
take-profit and strategy/rule exits; these read-only measurements cannot alter
an entry, exit or promotion decision. The owner status
also groups actual V1 PAPER openings into the frozen V2
`retained` and `filtered` cohorts at entry time. This is cohort attribution, not
a counterfactual V2 portfolio simulation, and cannot prove that V2 is better.
The observer also writes an atomic, bounded heartbeat to
`data/trading/forex_observer_status.json`. Owner status can therefore distinguish
a healthy closed-market idle state from a stale or missing observer without
starting MT5 or spending a market-data request outside the trading window. The
heartbeat also reports the last minute-protection result and a consecutive
failure counter. One stale local tick remains a safe skipped check; three
consecutive protection failures raise `PROTECTION_ATTENTION_REQUIRED` while the
15-minute PAPER cycle continues and all broker-order routes remain unavailable.
The counter survives observer restarts. Entering the attention state and later
recovering each create one durable event in `HISTORIA ZDARZEŃ`; repeated minute
checks in the same state do not create notification spam.
The `FOREX PAPER` toolbar projects the same bounded heartbeat as a separate
`OCHRONA` pill, so healthy, retrying, stale, closed-market and attention states
are visible without opening the owner text report.
On observer start, MT5 recovery or a long runtime gap, JARVIS runs the local
close-only position check before any full analysis cycle. New PAPER entries stay
locked until that check returns a healthy result. This stricter execution rule is
frozen as sample contract `FOREX_PAPER_V3_20260901`; V1 and V2 fills remain
visible in all-time history but are excluded from the V3 comparison sample.
The observer restores the last successful protection timestamp across Windows
restarts and keeps the most recent long recovery gap in its bounded heartbeat.
This makes overnight and sleep recovery visible without weakening the entry lock.
For an open position it replays bounded, closed M1 bars from that checkpoint before
using the current quote. The first historical SL/TP touch wins; if one minute can
contain both, the PAPER ledger records the stop-loss conservatively together with
the M1 timestamp. Recovery evidence is local, bounded and never reaches an order API.
This M1 recovery model is frozen as `FOREX_PAPER_V4_20260902`. The next sample
contract, `FOREX_PAPER_V5_20260902`, adds the audited 2% weekly entry brake.
Any mismatch between close fills and their tamper-evident execution audit fails
closed for new entries, while verified position closes remain available.
The Windows task has both a logon trigger and a 15-minute recovery trigger; the
single-instance policy ignores the recovery trigger while the observer is healthy
and restarts it after an unexpected exit.

Every watchdog cycle also appends safe open, close, first data-block and recovery
events to the bounded, ignored `data/trading/forex_paper_activity_history.json`.
This happens in the hidden observer process, not in the GUI. When JARVIS starts
again it drains unread events in sequence without repeating delivered entries;
the `FOREX PAPER` page keeps the latest 50 entries in its `HISTORIA ZDARZEŃ` tab.
Old ledger fills are visible as history but are not replayed as new alerts.

Use `Raport obserwacji Forex` for a deeper read-only review. It aggregates every
recorded cycle, market-day coverage, blocked reasons, proposed but unexecuted
actions, all seven-pair coverage and order-safety invariants. The report cannot
promote or enable PAPER or LIVE execution.

Each new observation also evaluates the frozen development candidate
`FOREX_REGIME_V2_20260820`. It keeps the 10/30 M15 crossover but allows a new
entry only when a 20/50 H1 trend, aggregated exclusively from complete closed
M15 bars, agrees with it. The policy, freeze time and SHA-256 fingerprint are
recorded with every eligible observation. Existing-position exits are never
blocked by the H1 filter. This candidate is research-only, sends no order and
cannot promote itself; observations made before its freeze time do not count as
forward evidence.

## Optional Forex PAPER data

For OANDA TMS in Poland, install its Windows MetaTrader 5, sign the terminal in
to a DEMO account and install the optional local package:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_trading_mt5.txt
```

JARVIS does not store the MT5 login or password. It uses the terminal's current
session and rejects real and contest accounts before reading the first price.

Export a local research snapshot of 5,000 closed M15 bars for all seven
tradable pairs plus the non-tradable USD/PLN conversion series:

```powershell
.\.venv\Scripts\python.exe .\tools\export_mt5_history.py --bars 5000
.\.venv\Scripts\python.exe .\tools\export_mt5_history.py --verify-latest
```

The export is stored under ignored `data/trading/history/`. Every series gets a
validated CSV and SHA-256 fingerprint in a secret-free manifest. USD/PLN is
available only to value historical portfolio risk and profit in PLN; the
trading universe remains the seven major pairs. Verification
re-reads every CSV and fails if a file, fingerprint, pair set or safety flag has
changed. It also checks timestamp alignment across pairs, positive tick volume
and distinguishes regular weekend closures from unexpected intraday gaps. MT5
position zero is the current bar, so the adapter deliberately starts at position
one and exports closed bars only.

Run the fixed LONG/SHORT 10/30 moving-average research on the newest verified
export:

```powershell
.\.venv\Scripts\python.exe .\tools\run_forex_historical_research.py
```

The test generates every signal from current and earlier closed bars and fills
it only at the next M15 open. It uses isolated chronological walk-forward
windows plus a conservative synthetic spread/slippage model. Individual-pair
results remain diagnostic, while candidate readiness is decided by one aligned
multi-pair portfolio valued in PLN through the exported USD/PLN series. The
ignored detailed report is written to `data/trading/research/latest.json`.
This command cannot connect to the broker or promote PAPER/LIVE trading, and
its results are research rather than a prediction of future profit.

Historical entries reuse the local PAPER scanner, pair ranking, PLN portfolio
risk engine and volatility-based 10-to-100-pip stop-loss formula. Position
sizing therefore follows the same per-trade, total-risk, currency-exposure and
two-position limits as PAPER. PAPER and research both store a fixed 2:1
take-profit. Even a fully passing report cannot start PAPER automatically; a
separate explicit activation and review remain required.
The same report contains an isolated `development_candidate_v2` replay. It
marks the already-known history as reused development data and always requires
new post-freeze evidence, so repeatedly running the report cannot turn an
overfit result into validation.
Its read-only forward scorecard separates unqualified post-freeze cycles from
invalid candidate contracts and compares base entry signals with the entries
retained or filtered by V2. Counts never validate performance, promote the
candidate, or enable PAPER/LIVE execution.
If one M15 candle touches both stop and target, the backtest records the stop
first. Gaps through a stop use the worse opening execution price, while target
gaps are capped at the target. These deliberately conservative assumptions
avoid selecting a strategy from unknowable intrabar price order.
Then copy `config/forex.env.example` to the ignored `config/forex.env` and fill
in:

- a Twelve Data API key for the independent price check;
- the public weekly Forex Factory economic calendar needs no key.

On Windows, copy one key to the clipboard and store it without placing the
secret in shell history:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\set_local_forex_secret.ps1 -Name JARVIS_OS_TWELVE_DATA_API_KEY
```

The helper writes the ignored file and removes the secret from the clipboard.

Keep `JARVIS_OS_FOREX_PRIMARY_PROVIDER=MT5_DEMO` and, for OANDA TMS,
`JARVIS_OS_MT5_SYMBOL_SUFFIX=.pro`. The optional
`OANDA_PRACTICE` provider is retained for non-TMS divisions with REST-v20
Practice access and requires its separate practice account ID and token.

NBP and Forex Factory need no keys. Secrets are sent in HTTPS headers and
excluded from status
and object representations, and are never committed. A cycle requires all
seven primary quotes, 31 completed M15 candles per pair, matching fresh prices
from the second source, a fresh calendar and a sufficiently recent NBP
reference. Missing, stale or divergent data blocks new positions. The MT5
adapter requests only current ticks and already-closed M15 bars; it contains no
method for placing, changing or closing broker orders.

## Optional Google Workspace integration

Copy `config/google_workspace_client_secret.example.json` to a local credentials file and fill it with credentials from Google Cloud. Real client secrets and OAuth tokens must never be committed.

## Weather without an API key

JARVIS OS can answer `Jaka jest pogoda w Miami?` and
`Jaka bedzie pogoda jutro w Warszawie?` through a direct, read-only Open-Meteo
lookup. The fixed HTTPS endpoints use bounded responses and short timeouts; no
account or API key is required. Location text is used only for the lookup and is
not written to a separate weather history. The response identifies Open-Meteo
as its source.

## Optional Azure planner

Copy `config/cloud.env.example` to `config/cloud.env` and provide:

- `JARVIS_OS_CLOUD_URL`
- `JARVIS_OS_CLOUD_API_TOKEN`
- `JARVIS_OS_REMOTE_DEVICE_ID=desktop-main` to receive commands from the
  private phone page
- `JARVIS_OS_REMOTE_QUEUE_URL` with the SAS-free queue URL; the signed-in
  Microsoft Entra user receives only queue-message processor permission

The desktop validates every cloud plan. Windows actions, confirmations and private memory remain local, and the local planner is used automatically if Azure is unavailable.

## Optional Cartesia or ElevenLabs voice

The existing local voice remains the default and needs no external account.
To opt in to a cloud voice, copy `config/voice.env.example` to the ignored
`config/voice.env` file and configure exactly one provider, its API key and a
voice ID. Use `JARVIS_OS_VOICE_PROVIDER=CARTESIA` or
`JARVIS_OS_VOICE_PROVIDER=ELEVENLABS`. API keys are never committed or shown in
voice status. Spoken text is sent to the selected provider only while it is
explicitly enabled. If credentials are absent, the request fails, the provider
times out or returns invalid audio, JARVIS OS repeats the same response using a
local Windows voice. Cloud audio is cached only under the ignored local
`runtime/voice_output/cloud_cache` directory.

Say or type `Pokaż status integracji` (or use `INTEGRACJE` in the daily tools)
to see the local configuration state of Azure, voice, RevenueCat, Meta Ads and
Claude. This status check makes no external request and never displays API keys
or private endpoint addresses.

Say or type `Co potrafisz?` (or use `CO POTRAFIĘ` in the daily tools) for a
short, client-safe guide with verified example commands. The guide performs no
action and never advertises owner-only development or business controls.

The Azure deployment also exposes a private, installable `/phone` app. Access
uses the owner's Microsoft account and a fixed 60-minute Azure session instead
of a pairing code. Signing out invalidates the current session; the Microsoft
"My sign-ins" page can revoke a lost phone. The relay stores commands for at
most 24 hours and never bypasses the desktop confirmation policy. The page
restores the last command status after a refresh without storing its text.
Desktop command polling goes directly to Azure Storage Queue, so the Container
App can scale to zero while the phone page is not being used.
If a mobile connection drops during submission, the page safely reuses a
short-lived request identifier. Azure returns the original command instead of
placing a duplicate in the desktop queue; command text is not persisted in
browser storage.

The phone page has a separate owner-only computer power card. Shutdown cannot
be requested through the free-text command box: the owner must open the red
control, type `WYLACZ` and press the second confirmation button. The dedicated
request expires after five minutes. Once the desktop receives it, JARVIS keeps
a local 60-second countdown and exposes `ANULUJ WYŁĄCZENIE` on the phone.
The phone displays the remaining seconds from the desktop completion timestamp
and restores that countdown after a page refresh. A confirmed cancellation
clears the saved visual state; the local Windows timer remains the only
shutdown authority. The final Windows call uses `/t 0` without `/f`, so
applications can still protect
unsaved work. Closing JARVIS during the countdown cancels it, and no power
request is restored after an application or computer restart.

For a reliable iPhone start, open `/mobile-start` in full Safari (not the
embedded browser of another app). It is a static page outside the phone Service
Worker and never redirects or signs out automatically. `/mobile-logout` exposes
an explicit Azure sign-out button, while `/mobile-diagnostics` shows only safe
connection checks and a request identifier that can be matched with server
logs. It never displays the owner's account identifier.
Microsoft returns an authorization code through the callback query instead of
a fragment that depends on callback JavaScript. Successful login stops at the
script-free `/mobile-complete` page so the owner can verify the session before
opening the panel with a normal tap.

## Optional Windows autostart

The phone bridge can receive commands only while the desktop application is
running. Install the per-user watchdog to start JARVIS OS after sign-in and
restart it after an unexpected exit:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_jarvis_autostart.ps1
```

The watchdog uses a single instance and a 5-to-60-second restart backoff after
an application failure. Closing JARVIS OS normally also closes the watchdog,
so the application stays off until it is started manually or at the next
Windows sign-in. To remove the scheduled task and stop the watchdog, run the
same script with `-Remove`.

## Repository layout

- `app/` - desktop application and local capabilities
- `cloud_service/` - Azure planner service
- `infra/` - Azure infrastructure definitions
- `tests/` - regression and safety tests
- `tools/` - maintenance and verification utilities
- `data/`, `archive/`, `AI_PLIKI/`, `runtime/` - local runtime state, excluded from Git

## Security

The repository is public. Do not commit passwords, API tokens, OAuth files, private keys, user memory, logs or generated customer packages.
