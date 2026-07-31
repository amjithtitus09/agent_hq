# Dashboard design requirements

Requirements for the rich operator dashboard that replaces the single
state-table page in `engine/dashboard.py`. Restores "Full dashboard" from
[`roadmap.md`](roadmap.md) — the deferral trigger ("someone actually asks for
a view the minimal page lacks") has fired.

Requirements only. Visual direction is decided separately.

## 1. The job

**Answer "does anything need a human right now?" in under three seconds, then
let you find out why.**

Everything else — spend, run history, adapter health — is secondary.
agent_hq's premise is that agents run autonomously and every human decision
is an explicit gate; the dashboard is where an operator discovers a gate is
waiting for them.

Audience: one to a few technical operators who already know what a run, a
handoff and a gate are. Not a stakeholder report.

## 2. Data contract

The page is static. It fetches one document and derives every view from it
client-side.

| | |
|---|---|
| Source | `dashboard.json` at the root of the `agent-hq-state` branch, written by `GitJsonStateStore.write()` |
| Transport | `raw.githubusercontent.com` — verified `access-control-allow-origin: *` |
| Size | 58.6 KB across 11 tickets today (mean 5.3 KB/ticket, max 14 KB) |
| Freshness | `cache-control: max-age=300` — up to 5 minutes stale, not bustable |
| Shape | `{tickets: [...], health: {...}}` |

Per-ticket detail (`tickets/<id>/state.json`) and artifacts are already
public URLs on the same branch, available for lazy loading if the single
document outgrows one fetch (~1 MB, roughly 200 tickets at the current mean).

## 3. Data models

All examples below are real documents from the pilot's state branch.

### Ticket

```json
{
  "ticket_id": "30",
  "pinned_comment_id": 5043543793,
  "status": "DONE",
  "work_repos": [
    {
      "repo": "amjithtitus09/care_fe-1",
      "branch": "agent-hq/30",
      "base_branch": "develop",
      "recorded_head": "3ce3813d3abfc882a54456182b93fe7e369283b3",
      "pr_ref": "amjithtitus09/care_fe-1#6"
    }
  ],
  "runs": [ ... ]
}
```

`status` is one of `ACTIVE` | `BLOCKED` | `DONE` (`schemas/state.schema.json`).

`block_reason`, `block_source` and `interrupted_run_id` appear only
sometimes — ticket 3 is `BLOCKED` and carries none of them. **Every optional
field may be absent entirely rather than null.**

### Run

```json
{
  "run_id": "34ec7b95644fcf2a",
  "task_id": "spec",
  "task_version": 1,
  "ticket_id": "3",
  "state": "FAILED",
  "attempt": 0,
  "bindings": {
    "tracker": "github-issues",
    "agent-session": "copilot-cli",
    "messaging": "github-comment",
    "gate": "github-issue-comment"
  },
  "cost_usd": null,
  "tokens": null,
  "usage_known": false,
  "artifacts": [],
  "chain_depth": 0,
  "source_event_id": "3:opened:2026-07-22T08:19:47Z",
  "enqueue_index": 0,
  "repo": "amjithtitus09/docs-1",
  "deadline": "2026-07-22T08:50:44Z",
  "attempt_started_at": "2026-07-22T08:20:44Z",
  "base_commit": "dbd221992b4569412c1969bffff99f2642160205"
}
```

`state` is one of `QUEUED` | `RUNNING` | `WAITING_GATE` | `SUCCEEDED` |
`FAILED` | `BLOCKED`. Handoff-spawned runs additionally carry
`parent_run_id`, `handoff_key`, `input_artifacts`, and on completion
`output_commit` and `pr_ref`. Runs in `WAITING_GATE` carry
`gate_request_id` and `gate_requested_at`.

### Health

```json
{
  "agent-session/copilot-cli": { "ok": true, "detail": "collect", "ts": "2026-07-29T02:16:23Z" }
}
```

Keyed `<port>/<adapter>`. P0 records health only for adapters a run actually
exercised, so absence is not failure — it means untested.

### The run chain

This is the model most likely to be got wrong. Ticket 30, all 14 runs in
array order:

| # | task | state | attempt | depth | handoff_key | parent |
|---|---|---|---|---|---|---|
| 0 | spec | SUCCEEDED | 0 | 0 | — | — |
| 1 | implement | SUCCEEDED | 0 | 1 | `implement-clinical-age-display` | `1112aa25` |
| 2 | review | SUCCEEDED | 0 | 2 | `review` | `148ba5d3` |
| 3 | implement | SUCCEEDED | 0 | 3 | `30-round2-implement` | `f9dec7d0` |
| 4 | review | SUCCEEDED | 0 | 4 | `review` | `6d8a9176` |
| 5 | implement | SUCCEEDED | 0 | 5 | `review-to-implement-round-3` | `2290fa8f` |
| 6 | review | SUCCEEDED | 0 | 6 | `review` | `1e3fa28d` |
| 7 | qa | FAILED | 0 | 7 | `qa-1` | `8c13c392` |
| 8 | qa | FAILED | 1 | 7 | `qa-1` | `8c13c392` |
| 9 | qa | SUCCEEDED | 2 | 7 | `qa-1` | `8c13c392` |
| 10 | finalize | SUCCEEDED | 0 | 8 | `finalize-30` | `6ca2c033` |
| 11 | qa | BLOCKED | 3 | 7 | `qa-1` | `8c13c392` |
| 12 | qa | SUCCEEDED | 4 | 7 | `qa-1` | `8c13c392` |
| 13 | finalize | SUCCEEDED | 0 | 8 | `finalize-30` | `a742dbc4` |

Four properties the renderer must handle:

1. **`chain_depth` is not unique and not a row index.** Five runs sit at
   depth 7 and two at depth 8.
2. **Array order is enqueue order, not depth order.** Run 11 (depth 7) lands
   after run 10 (depth 8). Sorting by array index and sorting by depth give
   different pictures; both are legitimate and neither is a timeline.
3. **A logical step is `(parent_run_id, handoff_key)`; `attempt` is the retry
   axis within it.** Runs 7–9 and 11–12 are one qa step with five attempts,
   not five steps.
4. **The same task appears many times.** `implement`↔`review` looped three
   times, and `finalize` ran twice off different parents. Nothing here is a
   fixed pipeline — the route is whatever each agent's control document
   asked for, so the app must not assume a known task sequence.

Edges come from `parent_run_id`. The root run has none.

### Artifacts

A run's `artifacts` array lists relative paths the run **produced**:

```json
["specs/30/qa.md", "specs/30/screenshots/patient-newborn-15-days.png", ...]
```

- URL: `https://raw.githubusercontent.com/<engine_repo>/agent-hq-state/tickets/<ticket_id>/artifacts/<run_id>/<path>`
- A run's artifact namespace on the branch may also contain artifacts
  **restored from its parent** as inputs. Render the declared `artifacts`
  list; never list the directory tree and present it as this run's output.
- Directory artifacts expand at collect time, so counts are not knowable in
  advance — one qa attempt produced 12 screenshots, another 11.
- Content is bytes, not necessarily text. PNGs are routine (qa screenshots);
  Markdown is routine (specs, reviews, summaries).

### Values that are absent, null, or zero

- `cost_usd: null` with `usage_known: false` is the normal case under the
  Copilot binding, which has no per-run USD metering
  (`architecture.md` deviation 9). **A zero or blank cost means unmetered,
  not free**, and the UI must not let those be read as $0 spend.
- `pr_ref` is `owner/repo#N`; the URL is
  `https://github.com/owner/repo/pull/N`.
- Optional fields are omitted, not nulled. Read defensively.

## 4. Hard constraints

1. **Read-only. Never a source of truth.** `architecture.md` classes the
   dashboard as a rebuildable projection.
2. **No backend, no auth, no secrets.** The bundle is served from a public
   Pages site. Anything in it is public.
3. **Public deployments only.** The design assumes the engine repo is public,
   because that is what makes the state readable without a token. Private
   installs use the `agent-hq` CLI (`operations.md` §9) — the page fails
   closed there rather than degrading into a partial view.
4. **Every string in the data is untrusted.** Ticket text, block reasons and
   artifact paths come from issues and agent output.
   `tests/fixtures/state/tickets/HQ-1/state.json` deliberately plants
   `</script><img src=x onerror=alert(1)>` in a run's `artifacts`, and that
   assertion must survive the migration. No `dangerouslySetInnerHTML`, no
   `innerHTML`, and no URL built by concatenating state data without
   validating the scheme.
5. **Deploys are decoupled from state.** The site rebuilds when dashboard
   source changes, never when state changes. No build step may read the
   state branch.
6. **Stale data must announce itself.** Given the 5-minute cache, the page
   always shows when the data was generated and offers explicit refresh.

## 5. Views

**v1 — required**

- **Gate queue.** Every run in `WAITING_GATE`: ticket, task, what is being
  asked, how long it has waited, and a link to the issue or PR where the
  decision actually happens.
- **Board.** Every ticket by status, dense enough to take in twenty at a
  glance.
- **Ticket detail.** Full run history for one ticket — the chain via
  `parent_run_id`/`handoff_key`, attempts and retries grouped per §3,
  artifacts as links, PRs, cost. Deep-linkable; a ticket URL must be
  pasteable into Slack.
- **Spend.** Total and broken down by task and by adapter binding, honest
  about `usage_known: false`.
- **Adapter health.**

**Later, if asked**

Per-month spend trends, effective-config view, throughput and cycle-time
stats. Don't build them speculatively.

## 6. Non-goals

- **Acting on gates from the dashboard.** Approving, blocking, retrying and
  re-running stay in GitHub. The page links out; it never mutates. This is
  what keeps constraint 2 true.
- Real-time updates. 5-minute polling is the ceiling.
- Mobile-first. Desktop is the working context, but it must stay usable on a
  phone, because gates get checked from phones.
- Authentication, accounts, per-user preferences.
- Rendering artifact contents inline beyond images and plain text.

## 7. Quality floor

- **State is never encoded in colour alone.** Every status signal carries a
  text or positional channel too.
- Visible keyboard focus; gate queue and board are keyboard-navigable.
- `prefers-reduced-motion` respected.
- Semantic headings and landmarks.
- Readable at 320 px wide without horizontal scroll.
- Bundle under ~150 KB gzipped JS — the data is 59 KB; the renderer should
  not dwarf it.
- Empty and error states are directional: no tickets says how a ticket gets
  created; a failed fetch says the state branch could not be read and offers
  retry.
- **Engine vocabulary renders verbatim.** State and status names appear
  exactly as written (`WAITING_GATE`, not "Waiting for gate") so they can be
  grepped against logs and state JSON. Runs, gates and handoffs keep their
  names.

## 8. Open decisions

- How rich is rich? A dense board plus ticket detail is meaningfully less
  work than that plus kanban affordances and spend charts. Both fit the data.
- Whether to pull ticket titles from GitHub. They are not in the state ledger
  today; adding them means an engine change and a second untrusted string.
- Whether the gate queue should distinguish gate types once more than one
  gate adapter is wired.
