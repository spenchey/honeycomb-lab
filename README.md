<div align="center">

<img src="docs/logo.png" width="120" alt="Honeycomb"/>

# Honeycomb

**Every GPU you own — one living map.**

A control plane and OpenAI-compatible gateway for your home AI fleet:
route every model through one endpoint, watch traffic light up the map,
and drive it all from your Mac, iPad, or phone.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-1d1d1f?logo=apple&logoColor=white)
![Swift 6](https://img.shields.io/badge/Swift-6-F05138?logo=swift&logoColor=white)
![gateway: Python stdlib · zero deps](https://img.shields.io/badge/gateway-Python%20stdlib%20%C2%B7%20zero%20deps-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-3fb950)

<img src="docs/honeycomb-demo.gif" width="760" alt="Honeycomb — the map goes LIT as traffic flows, with live GPU and tok/s"/>

[**Install**](#install) · [**Quickstart**](#install) · [**How it works**](#the-gateway) · [**Web dashboard**](#web-dashboard)

</div>

## What it does

<table>
<tr>
<td width="50%" valign="top">

**🔌 One API for the whole fleet**

Point any OpenAI-compatible client at `http://<hub>:4000/v1`. Route by
alias to vLLM boxes, LM Studio, or any endpoint. `cheap` picks the least
expensive healthy backend; `any` adds automatic failover mid-request.

</td>
<td width="50%" valign="top">

**🗺️ A map that tells the truth**

Each node is a hex — color is health, and it goes **LIT** with animated
pulses when traffic flows. The inspector shows real GPU %, memory,
KV-cache, tok/s, and latency trend. Never a catalog dump.

</td>
</tr>
<tr>
<td width="50%" valign="top">

**🛠️ Fleet control from the map**

**PING** a node through the real wire, **SERVE / STOP** its inference
container over SSH, and **DOCTOR** it with
[spark-doctor](https://github.com/joeynyc/spark-doctor) — auto-run when a
node fails, so the "why" is already waiting.

</td>
<td width="50%" valign="top">

**📱 Works everywhere**

A native macOS app (menu bar + notifications) **and** a self-contained
web dashboard the gateway serves itself. Open it on an iPad or phone, Add
to Home Screen, and run the fleet from anywhere over Tailscale.

</td>
</tr>
</table>

## Architecture

<div align="center">
<img src="docs/architecture.svg" width="720" alt="Client → gateway → your GPU fleet"/>
</div>

The hub is the Mac that runs the gateway and the app. Everything the
system believes about your fleet lives in one file: `fleet.json`.

## Install

### Download the app (no build tools needed)

Grab `Honeycomb-<version>-macos-universal.zip` from Releases, unzip, and
drag **Honeycomb.app** to `/Applications`. The app is universal (Apple
Silicon + Intel) and **carries the gateway inside it** — if the gateway
isn't running, the map offers a **START GATEWAY** button.

> **First launch:** the app is signed ad-hoc, not notarized (that needs a
> paid Apple Developer ID). macOS will refuse a plain double-click.
> **Right-click the app → Open → Open** once; after that it launches
> normally. Everything it runs is in this repo — read it before you trust it.

Requirements: macOS 14+, `python3` (from Xcode Command Line Tools:
`xcode-select --install`), and SSH keys to your GPU boxes. Optional per
feature: vLLM on the boxes, LM Studio + LM Link, Docker (SERVE/STOP),
[spark-doctor](https://github.com/joeynyc/spark-doctor) (DOCTOR).

Then describe your machines — the app shows the exact path, and names any
mistake it finds:

- **fleet.json** → `~/Library/Application Support/Honeycomb/fleet.json`
  (see [fleet.example.json](fleet.example.json))
- **gateway config** → `~/Library/Application Support/Honeycomb/gateway-config.json`
  (seeded from the example on first start; set a `control_token`)

The web dashboard is then live at `http://<hub-ip>:4000` for any browser,
iPad, or phone.

### Build from source

```bash
git clone <this repo> && cd honeycomb-lab
cp gateway/config.example.json gateway/config.json   # edit backends + token
(cd gateway && ./start.sh)                           # → http://0.0.0.0:4000
./Scripts/compile_and_run.sh                         # build + package + launch
cp -R Honeycomb.app /Applications/

./Scripts/make_release.sh    # universal .zip in dist/, for distribution
```

To run the gateway as a service (start at login, restart on crash), see [docs/launchd.md](docs/launchd.md).

## The gateway

| Model id | Routes to |
|----------|-----------|
| `cheap` | Cheapest healthy backend with a chat model loaded (`cheap_order` in config) |
| `any` | Like `cheap`, plus automatic failover to the next backend on upstream errors |
| *your aliases* | Whatever you define in `config.json` (e.g. `spark-main` → box A's vLLM) |
| `backend/<model>` | Explicit model on an explicit backend |

Any alias can opt into failover per-request with `"failover": true`.
Aliases with no pinned model auto-pick the backend's first chat-capable
model (embedding models are skipped).

<div align="center">
<img src="docs/routing.svg" width="760" alt="cheap/any routing picks the cheapest healthy backend, then fails over"/>
</div>

Endpoints: `/v1/chat/completions` · `/v1/completions` · `/v1/embeddings`
(all proxied, stream + non-stream) · `/health` (backends, activity,
telemetry) · `/telemetry` (accounted usage by agent, model, device, and the
combined agent/model/device route) · `/nodes` (fleet status for the dashboard) · `/requests` (recent
traffic) · `/control/*` (ping / doctor / container / configured pair mode —
see security below).

### Telemetry

Honeycomb records each routed request by the authenticated agent token, route
alias, resolved model, configured device, and the combined agent/model/device
route. Token totals are counted only when the upstream model returns a `usage`
object; streamed usage can be enabled per backend with `"stream_usage": true`.
The dashboard's **ACCOUNTED USAGE** strip shows the same data without estimating
missing tokens. Spark
nodes show GPU, memory, and CPU through SSH; an HTTP-only endpoint can also
provide CPU by adding `sshHost` and `metricsCommand` to its fleet entry.

An agent should point at a stable Honeycomb alias such as `dev-local`, not a
hardware URL. The alias is the centrally managed routing policy; it maps to a
specific model/device and can have an explicit fallback. Changing a physically
loaded model is intentionally a separate configured operation, because it
stops and reloads the serving process.

#### Operational history and alerts

`/telemetry` is the live cumulative view. The gateway also writes a
metadata-only JSONL ledger (no prompts, completions, or credentials) and
serves time-window data at `/telemetry/history?since=<unix-seconds>`. This
makes daily reporting, error-rate review, and capacity decisions reproducible.
`/alerts` reports unavailable, slow, or repeatedly failing backends. Set
`alert_webhook` to an `env:VARIABLE_NAME` reference to deliver those alerts to
a Slack-compatible incoming webhook; alerts are de-duplicated by cooldown.
Alternatively, `alert_command` may be an explicit argv list for a protected
local sender such as `Scripts/send-honeycomb-alert.py`; its generated alert
message is appended as the final argument. Honeycomb never accepts alert
commands from a browser or agent request.

#### Authenticated cloud providers

Honeycomb can proxy any provider that exposes a compatible OpenAI API, but
provider credentials are never placed in agent configuration, dashboard code,
or committed JSON. Add a backend with a header reference such as:

```json
"headers": { "Authorization": "env:HONEYCOMB_PROVIDER_API_KEY" }
```

Then put that environment variable only in the gateway service environment.
Honeycomb uses it for health checks and proxied requests, while each agent
still authenticates to Honeycomb with its own inference token. First test a
dedicated non-production alias; do not move a working production cloud agent
until its smoke test and usage accounting are confirmed.

#### Safe model profiles and audit trail

The gateway never accepts a shell command from the browser. A fleet node may
declare named `modelProfiles`, each with an `activateCommand`, optional
`verifyCommand`, and optional `rollbackCommand`. `POST /control/profile`
requires a control token and an exact profile-name confirmation. Every control
action is appended to the protected `/audit` trail. This keeps a physical model
swap explicit, testable, and recoverable instead of mixing it into model alias
routing.

`links` may be topology-only `["node-a", "node-b"]` or declare a configured
SSH `checkHost` and `checkCommand`. Honeycomb labels topology-only links
**unverified** rather than claiming a cabled Spark fabric is healthy without a
real link probe.

## fleet.json

Nodes are described in `~/Library/Application Support/Honeycomb/fleet.json`
(created from the bundled default on first launch; `HONEYCOMB_FLEET` env
var overrides the path). Start from `fleet.example.json`.

**Probe types:**
- `vllm-ssh` — a GPU box running vLLM; SSH reachability = online, metrics
  via `nvidia-smi`/`free`, throughput via vLLM's `/metrics`.
- `lmstudio-hub` — the hub itself, serving via LM Studio.
- `lmlink-peer` — a remote GPU reached through the hub's LM Studio via
  LM Link (`lmLinkPeer` = the peer's device name).
- `http-only` — any OpenAI-compatible endpoint, health by HTTP only.

**Per-node fields:** `gatewayBackend` + `litAliases` map the node to a
gateway backend so its hex lights on traffic; `pingAlias` enables PING;
set `gpuUtilReliable` to `false` when a GB10 host reports misleading
instantaneous utilization. For ComfyUI nodes, `workloadURL` adds live running
and queued job counts plus unified GPU-memory usage from `/queue` and
`/system_stats`. `llmURL`, `llmKind` (`openai` or `ollama`), and `llmRole`
add serving-model state; a clustered worker may point `llmURL` at the shared
controller endpoint while retaining its own `llmRole`.
`container` (+ `sshHost`) enables SERVE/STOP; `doctorCommand` enables
DOCTOR; `hub: true` marks the center node; `axial: [q, r]` pins the map
position; top-level `links` adds extra edges between nodes.

## Web dashboard

Served by the gateway at `/` for browsers (API clients still get JSON).
Full feature parity: map, LIT pulses, inspector with metrics + latency
trend, traffic feed, and PING/DOCTOR/SERVE/STOP.

**Security model:**
- Model requests require an `Authorization: Bearer <agent-token>` header when
  `api_tokens` is configured. Give each agent a different token. An inference
  token can route requests but cannot operate a machine.
- Control actions (`/control/*`) require the `X-Honeycomb-Token` header
  from anywhere but localhost. Set `control_token` in `config.json`
  (`openssl rand -hex 16`); the dashboard prompts once and remembers it.
  The example config's `__REPLACE_ME__` sentinel never authorizes.
- Requests must address the hub by IP literal or localhost. To reach it
  by hostname (e.g. a tailnet MagicDNS name), add that name to
  `allowed_hosts` — this blocks DNS-rebinding attacks that would
  otherwise let a malicious web page inherit the localhost exemption.
- Control responses carry no CORS headers, so a page in your browser
  can't script them; doctor findings in `/nodes` are only returned to
  authorized callers.
- There is no TLS: the gateway is built for a trusted LAN or a tailnet
  (Tailscale/WireGuard), not the open internet. Don't port-forward it.

## spark-doctor integration

Give any `vllm-ssh` node a `doctorCommand` that prints a
[spark-doctor](https://github.com/joeynyc/spark-doctor) scan JSON to
stdout, and Honeycomb runs it on demand (DOCTOR button) and automatically
when inference dies or the node drops — findings render right in the
inspector, and fresh critical findings turn an online hex amber.

## License

MIT — see [LICENSE](LICENSE).
