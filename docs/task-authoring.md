# Authoring a task

A task is one directory under `tasks/<id>/` with a `task.yml` validated
against `schemas/task.schema.json`, plus whatever `prompts/`/`checklists/`
skill files it references. There is no fixed chain and no task-name special
case in the engine (`intake` and `finalize` used to be special-cased; neither
is anymore -- see "Dispositions" below). A task joins the live graph the
moment some other task's `handoff.allowed` names it and an accepted run
proposes a handoff to it; nothing else "wires it in".

## Generic fields

Required: `id`, `version`, `description`, `trigger` (currently always
`enqueued_by` -- who/what enqueues a run is the handoff or intake that named
it, not a field on the task itself), `budget`.

Optional, all schema-validated (`additionalProperties: false` throughout, so
a typo'd key fails `agent-hq tasks validate` rather than being silently
ignored):

- `inputs.artifacts` / `inputs.ticket_fields` -- declares that a run must not
  start before its parent run has recorded these artifacts (`TE-3`, checked
  by `engine.engine._inputs_ready` at dispatch time). This is a *readiness*
  gate, separate from where the files actually come from at execute time (see
  "Artifact namespace" below).
- `context` -- symbolic references injected into the prompt: `constitution`
  (inlines `constitution.md`), `specs/{ticket}/*` (told to read from the
  worktree, `{ticket}` substituted), or a task-local `prompts/*`/`checklists/*`
  file (inlined verbatim).
- `skills` -- task-local `prompts/`/`checklists/` files, inlined into the
  prompt; must exist on disk (`engine.taskdefs.load_task` checks this).
- `components` -- port name -> **logical** binding name. Validated but
  currently inert: `engine.config.resolve_binding` honors a task-supplied
  binding name only for the `gate` port, and the gate binding is actually
  selected via `gates.post[].adapter`, never via `components` (see
  `docs/task-definition.md`). A task
  declaring a `components` entry for a port `components.yml` doesn't
  configure is a load-time error (`engine.config.validate_task_bindings`,
  wired into `agent-hq tasks validate`). A task declaring **no**
  `components` at all (e.g. `qa`) stays registered but unwired -- see
  "Dispositions".
- `model` -- currently unused by any adapter; reserved.
- `gates.post` -- see "Gates" below.
- `outputs.artifacts` -- declared output paths (`{ticket}` substituted); see
  "Artifact namespace".
- `opens_pr` -- open (or reuse) a draft PR on the task's work branch on
  success, independent of any gate (`implement` sets this).
- `handoff.allowed` / `handoff.max` -- see "Handoffs" below.
- `tools` -- allowed tool names passed to the agent adapter.
- `budget.max_cost_usd` / `max_runtime_min` / `retries` -- per-run caps; see
  "Budgets".

Every field that names a repository, a task, or a port is a **configured
value** (from `config/*.yml`) or a **task id from the loaded library** --
never a concrete adapter name. `tests/test_task_library.py`
(`test_no_concrete_adapter_name_leaks_into_task_defs`) enforces that no
`task.yml` ever contains a string like `github-issues` or `copilot-cli`.

## Ports a task uses

Three ports are bound automatically for every run at prepare time
(`engine.engine.BINDABLE_PORTS`): `tracker`, `agent-session`, `messaging`.
A task never names a concrete adapter for these -- `components.yml` does. A
`gates.post` entry additionally binds the `gate` port (see below). `qa-env`
and `poll` are declared as `engine.ports` Protocols with no P0 adapter; a
task that doesn't touch them (every current task) never resolves them, so
they can stay unbound in `components.yml` without breaking validation.

## Handoffs

A task proposes its children by writing `.agent-hq/control.json` with
outcome `"handoff"` (see "Control outcomes" below); the task definition only
constrains what's *allowed*:

- `handoff.allowed` -- the list of task ids this task may hand off to. A
  proposed handoff naming any other target is rejected
  (`engine.handoff.validate_handoffs`).
- `handoff.max` -- the most handoffs one run may propose in a single
  `control.json`. Most tasks are `max: 1` (a linear next step); `breakdown`
  is `max: 2` -- the pilot's fan-out point, emitting one `implement` handoff
  per affected configured repo (`config/repos.yml`), each carrying that
  repo in the handoff's `repo` field.

Validation is pure and total-rejection: `engine.handoff.validate_handoffs`
checks the whole proposed set against `schemas/control.schema.json`, then
path containment on every artifact, then per-handoff semantics (target in
`handoff.allowed` and in the loaded library, `repo` if given is a configured
repo, key uniqueness, total count `<= handoff.max`, and each artifact is in
the run's **provenance set** -- its inherited `input_artifacts` union its own
substituted `outputs.artifacts`, never an arbitrary worktree file). Any
single violation rejects the *entire* set, not just the offending item.

State-dependent guards that the pure validator can't see (each artifact's
ledger entry actually exists, and the ticket's loop/budget/depth limits
still hold) are enforced atomically in `engine.engine.apply_handoffs`, inside
the same state-store transaction that marks the source run terminal --
so a crash between "run succeeded" and "children queued" can't happen.
Handoff-spawned run identity is `(source_run_id, handoff_key, attempt)` only
-- the target task id is **not** part of it, so a re-delivered handoff key
always resolves to the same run id regardless of payload content (the first
accepted delivery wins; a duplicate is a no-op).

## Control outcomes

Every completed run writes exactly one `.agent-hq/control.json`
(`schemas/control.schema.json`, `additionalProperties: false` --
schema-invalid means the run *fails* per its own retry budget, never
"ignored"):

- `{"outcome": "handoff", "handoffs": [...]}` -- `handoffs` required,
  non-empty. With no `gates.post` on this task, accepted handoffs enqueue as
  `QUEUED` runs immediately and this run finishes `SUCCEEDED`. With a
  `gates.post` entry, the proposals are stored as `run.pending_handoffs` and
  the run stops at `WAITING_GATE`; a gate `APPROVED` decision applies them
  and completes the run — unless that gate sets `auto_approve`, in which case
  they apply immediately as if there were no gate (see "Gates" below).
- `{"outcome": "complete"}` -- `handoffs` forbidden; the run finishes
  `SUCCEEDED` with no children. This is what feeds queue-empty completion
  (see "Terminal-summary convention" below) -- a task with no
  `handoff.allowed` at all (e.g. `finalize`) always emits this.
- `{"outcome": "blocked", "reason": "..."}` -- `handoffs` forbidden, `reason`
  required; the run is recorded blocked and the ticket moves to `BLOCKED`
  with that reason, escalating to a human with no auto-retry.

Any outcome may also carry `summary` -- a Conventional Commits description of
what the run changed in the work repo. Its first line becomes the subject of
the commit the run lands, the rest the body; the ticket reference and run id
are appended as trailers. A run's own commits are squashed into that single
commit by `materialize_work_patch`, so `summary` is the only description that
reaches the work repo. A run that changed no files can omit it (collect falls
back to the ticket title).

`engine.runner._assemble_prompt` injects this contract into every prompt
automatically (the required outcome shapes, the `summary` convention, this
task's own `handoff.allowed`/`max`, and the output path) -- a task never needs
to spell this out itself, and it does not depend on the task including
`constitution.md` in `context`.

## Artifact namespace: ledger vs. work-patch

There is exactly one artifact namespace and one input source:

- **Ledger artifacts** are a run's declared `outputs.artifacts`, persisted
  by collect into `tickets/<id>/artifacts/<run_id>/` (keyed by the
  *producing* run id, via `engine.state.GitJsonStateStore.write_artifact`/
  `read_artifact`/`artifacts_dir`) -- never a work-repo commit. If an
  accepted handoff forwards an artifact the run itself only *inherited*
  (e.g. `arch-plan` -> `breakdown` forwarding `spec.md`), collect also
  snapshots that file into the *source* run's own ledger directory, so a
  transitive handoff still resolves. Artifacts are stored as **bytes** --
  they are not all text (`qa`'s screenshots), and anything that inlines one
  into a comment decodes it, skipping what has no text.
- **Directory artifacts.** An `outputs.artifacts` entry ending in `/` is a
  directory: the engine collects whatever files it holds, recursively, zero
  or more (`engine.runner._expand_declared`). Use it for output a task cannot
  name in advance -- `qa` writes one screenshot per acceptance criterion it
  managed to exercise, which is not a list anyone can write into `task.yml`.
  Unlike a plain entry they are never *required*: an empty or absent
  directory is a valid run. They expand to concrete paths before anything is
  recorded, so `run.artifacts`, handoff forwarding, and `_inputs_ready` only
  ever see real files -- nothing downstream knows the convention exists.
- **Input artifacts** on a handoff-spawned run
  (`run.input_artifacts`, copied from the accepted handoff's `artifacts[]`
  at apply time) are the run's **only** input source -- there is no
  separate task-level input list. Prepare restores their content from the
  **source** (parent) run's ledger namespace (`engine.runner
  ._restore_input_artifacts`) into a transported manifest -- execute (its
  own, credential-free Actions job, hardening plan Task 12) then
  materializes them into its worktree (`engine.runner._materialize_inputs`),
  so a child reads exactly what its handoff accepted, never a sibling's
  file.
- The **work patch** excludes both: execute's `materialize_work_patch`
  diffs out every declared output path and every inherited
  `input_artifacts` path before handing the patch to collect, which
  `git apply`s it to a fresh clone and lands it on the target branch
  (`engine.runner._collect_success`). Neither is code; both live only in
  the ledger.

Every artifact path a handoff proposes is **containment-checked** against
the worktree root before it's trusted anywhere (absolute paths, `..`
segments, and symlink escapes are all rejected;
`engine.handoff._check_containment`).

## Gates

`gates.post` is a list (P0 uses one entry) of `{approvers, adapter,
timeout_working_hours, auto_approve}`. `approvers` names a group in `config/approvers.yml`;
`adapter` is a **logical** gate name resolved through `components.yml`'s
`gate.named` map (or the plain `gate.adapter` default) -- never a concrete
adapter id. The pilot's `default`/`spec-approval` logical names both resolve
to the `github-issue-comment` adapter (an authorized-comment approval on the
parent engine issue); `pr-review` remains registered for a task that wants a
work-repo-PR-based approval instead. See `docs/ports/gate.md` for the full
adapter contract. A gate past `timeout_working_hours` with no decision
resolves to `EXPIRED` at the next sweep, blocking the ticket and escalating.

`auto_approve: true` decides the gate without a human: the run never enters
`WAITING_GATE` and its handoffs apply immediately. It defaults to false — a
declared gate is a human decision unless the task says otherwise.

What it does **not** skip is the record. The gate still posts its comment,
carrying the run's declared artifacts exactly as a real request would — that
comment is where a spec becomes readable to a human, and an auto-approved
task that posted nothing would be invisible in the thread. It is rendered as
a record rather than a request: heading "Gate auto-approved", no decision
grammar, and no `@`-mention of a group with nothing to decide. A
`gate.decided` event records it in the ledger too.

Turning it on is **retroactive**. The sweep honors it for runs already parked
at `WAITING_GATE`, so flipping the flag drains the gates currently waiting on
the next pass rather than stranding them behind a flag that says they need no
human. Those runs already posted a request comment asking for a decision that
will now never come, so the sweep posts a short follow-up saying the gate was
auto-approved after the fact. Turning the flag back off is not retroactive in
the same way — a run that already sailed through is finished.

Use it for a checkpoint you want in the graph but not in the critical path
today — a task whose gate you intend to staff later, or one you are still
tuning. Note what it costs: `WAITING_GATE` is also what holds a ticket's
in-flight slot for review, so auto-approving trades a human checkpoint for
throughput. Weigh that per task, not as a default. Because it lives in the
task definition, it applies to **every** deployment of the library; a gate
that should be automatic in one environment and staffed in another wants a
config-level switch instead, which does not exist yet
(`docs/roadmap.md`).

## Environment setup

A task rarely wants to build its own environment. `repos.yml` carries a
`setup` map per repo — task id to shell command, with `default` covering any
task that has no entry of its own:

```yaml
amjithtitus09/care_fe-1:
  setup:
    default: npm ci
    qa: |
      make -C .agent-hq/care up load-fixtures
      npm ci && npm run build
```

The engine runs it in the worktree before the agent starts
(`engine.runner._run_setup`), and resolution is
`setup[task_id] or setup["default"] or None`
(`engine.engine.resolve_setup`). It lives in config, not in a prompt or in
engine code, so a different project configures a different command without
touching either.

Why it is not the agent's job: a fixed sequence of shell commands costs one
agent request per step under a per-request billing model, fails differently
every time, and is exactly the part that needs no judgment. Doing it in shell
also means a broken environment **fails the run** — non-zero exit becomes a
normalized `execute-result` failure carrying the command and a log tail, so
the ordinary retry budget applies and the reason reaches the ticket. The
alternative is an agent flailing against a half-built environment and
reporting whatever it managed, which is what QA did before this existed.

The command runs with the engine's credentials stripped
(`AGENT_HQ_TOKEN`/`GITHUB_TOKEN`/`GH_TOKEN`/`COPILOT_GITHUB_TOKEN`): it is
operator-authored config and so trusted further than agent output, but it has
no business holding tokens. It is bounded by the run's own deadline — note
that deadline starts at *claim* time, so setup time comes out of the task's
`budget.max_runtime_min`.

Anything the agent needs to know goes in `.agent-hq/setup-notes.md` (URLs,
credentials, paths). When a setup command is configured, the assembled prompt
gains an Environment section telling the agent the worktree is already
prepared, to read that file, and not to rebuild anything itself. The engine
never learns what the command did — that contract is entirely between the
config and the notes file.

## Budgets

Per-task `budget.max_cost_usd`/`max_runtime_min`/`retries` bound one run.
Ticket-wide caps live in `config/budgets.yml`: `ticket_cap_usd` (total spend
across every run on a ticket), `in_flight_cap` (global concurrent-ticket
cap), and `loop_guard.max_runs`/`max_depth` (runaway-handoff protection --
total run count and causal chain depth). All four are checked before a
handoff set is applied (`engine.engine.apply_handoffs`) and before a queued
run is dispatched, so a task cannot out-run these limits by proposing more
handoffs. Under the default Copilot-billed executor, run cost is not
metered (`cost_usd: 0.0`, `usage_known: true`), so `max_cost_usd`/
`ticket_cap_usd` don't bind in that configuration -- `retries`, the loop
guard, the in-flight cap, and runtime deadlines still do (see
`docs/architecture.md` deviation 9).

## Terminal-summary convention

Queue-empty completion (`engine.engine._complete_if_queue_empty`) fires once
a ticket has no `QUEUED`/`RUNNING`/`WAITING_GATE` run and no
`pending_handoffs` left anywhere, but only actually closes the ticket if the
**terminal run's own recorded artifacts** include the declared summary path
`specs/{ticket}/summary.md` -- a reopened ticket can't complete off a prior
lifecycle's stale summary. `finalize` is exactly this: no `handoff.allowed`,
one declared output (`specs/{ticket}/summary.md`), always emits
`{"outcome": "complete"}`. Any task chain that wants queue-empty completion
to land on a real "done" message should end the same way: declare the
summary artifact, emit `complete`, propose no further handoffs. Without a
matching summary, completion instead pins "awaiting human input" and takes
no terminal action.

## Validation

- `agent-hq tasks validate` loads every `tasks/*/task.yml`
  (`engine.taskdefs.load_all`, schema + on-disk skill/context checks),
  cross-checks the library (`engine.taskdefs.validate_library`: every
  `handoff.allowed` target resolves to a loaded task id), and checks every
  task's declared `components` port against `components.yml`
  (`engine.config.validate_task_bindings`).
- `agent-hq config validate` validates `config/*.yml` against
  `schemas/*.schema.json` (including the `handoff`/`initial_task`/`intake`/
  `base_branch` additions).
- `tests/test_task_library.py` pins the graph-level properties (no
  P0_CHAIN, no concrete adapter names, gate bindings resolve to
  constructible adapters, no `tasks/intake/` directory).

## Dispositions

| Task | Status |
|---|---|
| intake | **Not a task.** Engine entry logic (`engine.runner.intake_ticket`) reads eligibility from `config.projects["intake"]`/`["public"]`/`["public_safe_label"]` and enqueues `config.projects["initial_task"]` (`spec` in the pilot config) with the root run's resolved repo. There is no `tasks/intake/` directory and no task-name special case for it. |
| spec | Converted (wired). `handoff.allowed: [implement]`, gated (`spec-approval`) but currently `auto_approve: true` -- the checkpoint is declared and evented, decided by the engine rather than a product owner; staffing it is deleting that one line. The fan-out point in the minimal route: `handoff.max: 3`, one `implement` handoff per affected configured repo. |
| arch-plan | Converted, defined, **unwired** -- its header names the activation edit (point `spec`'s `handoff.allowed` back at it). `handoff.allowed: [arch-approval, breakdown]`. |
| arch-approval | Converted, defined, **unwired** (activated with `arch-plan`, its only in-edge). Confirms the plan artifacts, no changes; gated (`default`); `handoff.allowed: [breakdown]`. |
| breakdown | Converted, defined, **unwired** (activated with the `arch-plan` chain). `handoff.max: 2`, one `implement` handoff per affected repo when wired. |
| implement | Converted (wired). `opens_pr: true`; `handoff.allowed: [review]`. |
| review | Converted (wired). `handoff.allowed: [implement, qa]` -- loops back to `implement` while blockers remain (prompt-capped at 3 rounds; on the cap it emits `complete` and the engine posts the accumulated `review.md` findings to the thread, parking awaiting-human with the PR left in draft), else hands to `qa`. Round memory is `review.md` forwarded around the loop as an input artifact. Every review round also reflects its latest-round findings onto the work-repo PR as a comment (`engine.engine.post_pr_comment`, in the credentialed collect phase -- the read-only agent can't, PD-5). |
| finalize | Converted (wired). Terminal task: writes `summary.md`, always `complete`, feeds queue-empty completion (see above). No task-name special case; any task ending this way completes the same way. |
| clinical | Converted, defined, **unwired** until an accepted handoff selects it -- its own header names the one-line activation edit (point `spec`'s `handoff.allowed` at it). Gated (`clinical-reviewers`, `default` adapter). |
| poll | Converted, defined, **unwired** -- needs the P1 reaction-based `poll` adapter (`docs/roadmap.md`); no task currently hands off to it. |
| docs | Converted, defined, **unwired** until an accepted handoff selects it (its header names the activation edit: point `qa`'s `handoff.allowed` at it). |
| qa | Converted (wired). `handoff.allowed: [finalize]`, always -- `qa` reports, it never gates. `writes_code: false`, so the engine discards its work patch outright: everything it leaves in the worktree is scratch, and an instruction to keep scratch under `.agent-hq/` is advisory where discarding is not. Stands the app up with the work repo's own tooling inside the devcontainer and screenshots each acceptance criterion; it declares **no** `components` port, so the deferred `qa-env` binding (`docs/ports/qa-env.md`) is still not required. Screenshots are ledger artifacts under the **directory artifact** `specs/{ticket}/screenshots/` -- kept out of the work repo, which is for product code -- and collect rewrites `qa.md`'s relative image links to their state-branch URLs before posting it to the PR (`engine.runner._ledger_image_urls`). |

None of the above is a name the engine special-cases; every row describes a
task-graph state (wired vs. defined-but-unwired), not an engine code path.
