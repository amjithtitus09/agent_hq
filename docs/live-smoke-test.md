# Live smoke test (pilot deployment)

Repeatable end-to-end validation of the deployed pilot on real GitHub
infrastructure. Re-run this after every phase of the hardening plan lands
(approvals lifecycle, operator CLI, ...) — the "not yet validated" list at
the bottom is the checklist to burn down. Complements `docs/local-testing.md`
(fakes/local) and `docs/setup-new-repo.md` (one-time setup).

## Deployment under test

| Piece | Value |
|---|---|
| Engine repo | `amjithtitus09/agent_hq` (issues = tickets; state on `agent-hq-state`) |
| Work repos | `amjithtitus09/care` (`backend`, base `develop`), `amjithtitus09/care_fe-1` (`frontend`, base `develop`), `amjithtitus09/docs-1` (`docs`, base `main`) |
| Route | intake → `spec` (product-owner gate; fans out ≤3 `implement`) → `implement` (draft PR) ↔ `review` (loops to `implement` on blockers, prompt-capped 3 rounds → park; else `finalize`) → `finalize` (summary, close) |
| Executor | `copilot-cli`, `claude-sonnet-4.5`, billed via Copilot seat (`cost_usd` records 0.0 — deviation 9) |
| Approver (all gates) | `amjithtitus09` |

## Preconditions

- Config/tasks/prompts under test are **merged to `main`** — workflows and
  the run-dispatch ref resolve against the default branch; a feature branch
  changes nothing.
- Secrets on the engine repo: `AGENT_HQ_TOKEN` (fine-grained PAT: engine +
  work repos, Contents/Issues/PRs/Actions RW), `AGENT_HQ_COPILOT_TOKEN`
  (Copilot-seat account, user-owned fine-grained PAT, account permission
  **Copilot Requests: Read**, no repo access).
- Labels on the engine repo: `hq:intake`, `hq:excluded`.
- Kill switch off: `gh variable set AGENT_HQ_KILL_SWITCH --repo amjithtitus09/agent_hq --body "0"`.

## Procedure

1. **File a ticket** — the body must be ≥30 words, contain exactly one
   routing keyword (`backend` / `frontend` / `docs`), describe work the repo
   *genuinely lacks* (a spec that finds nothing to do legitimately ends the
   route with `complete`), and avoid injection-flag phrasing ("ignore
   previous instructions").

   ```bash
   gh issue create --repo amjithtitus09/agent_hq --label "hq:intake" \
     --title "<task>" --body "<≥30 words, one routing keyword>"
   ```

2. **Intake** (fires on the label event; duplicate opened/labeled runs are
   deduped by event key): expect a pinned "Accepted by agent-hq; work has
   been queued" comment on the issue, and the ticket state on the state
   branch with a QUEUED `spec` run targeting the right repo.

3. **Run workflow** (intake wakes the dispatcher, which triggers `run.yml`):
   watch prepare → execute → collect. Execute is the slow leg (devcontainer
   build + agent run, ~5–10 min).

4. **Gate** — after spec's collect, a gate comment @-mentions the approver
   group with the decision grammar. Approve as a group member:

   ```
   /agent-hq approve <run-id>
   ```

   Decisions are only noticed by the next dispatch sweep (~15-min cron until
   Task 14 lands) — wake it manually:
   `gh workflow run dispatch.yml --repo amjithtitus09/agent_hq`.

5. **Implement** — expect a run per affected repo, committing on the stable
   `agent-hq/<issue>` branch cut from the repo's `base_branch`, and one
   draft PR per repo.

6. **Finalize** — expect `specs/<ticket>/summary.md`, a closing summary
   comment, the PR(s) marked ready for review, the issue closed, ticket
   `DONE`. DONE means engine-complete: merging the PR stays human.

## Inspection commands

```bash
# Workflow surface
gh run list --repo amjithtitus09/agent_hq --limit 10
gh run view <run-db-id> --repo amjithtitus09/agent_hq --log-failed

# Ticket state / events / artifacts (state branch is plain git+JSON)
gh api "repos/amjithtitus09/agent_hq/contents/tickets/<n>/state.json?ref=agent-hq-state" -q .content | base64 -d | python3 -m json.tool
gh api "repos/amjithtitus09/agent_hq/contents/tickets/<n>/events.jsonl?ref=agent-hq-state" -q .content | base64 -d
gh api "repos/amjithtitus09/agent_hq/contents/tickets/<n>/artifacts/<run-id>/specs/<n>/spec.md?ref=agent-hq-state" -q .content | base64 -d

# Pause / resume all dispatch
gh variable set AGENT_HQ_KILL_SWITCH --repo amjithtitus09/agent_hq --body "1"   # pause
gh variable set AGENT_HQ_KILL_SWITCH --repo amjithtitus09/agent_hq --body "0"   # resume
```

## Findings log

**2026-07-22 — round 1 (ticket #3, glossary page)**
- intake / routing / dispatch / prepare / collect all ✅ first try; state
  branch self-bootstrapped.
- execute ❌: unpinned `devcontainers/python:3.11` had moved to Debian
  trixie, where docker-in-docker's `moby` default can't install → container
  build died pre-agent. Fixed by pinning `3.11-bookworm` (PR #4).
- Policy observation: an execute failure *before the agent runs* reports
  `usage_known: false`, which **blocks the ticket with no auto-retry** (spend
  unverifiable). Until the operator CLI (Task 18) / guarded reopen (Task 16)
  land, such a ticket needs manual state repair (`/hq-recover`). Ticket #3
  left BLOCKED.

**2026-07-22 — round 2 (ticket #5, local-dev docs)**
- Full three-phase run ✅ — devcontainer fix good, Copilot token good, agent
  cloned the work repo, wrote a well-grounded `spec.md`, artifacts and spend
  recorded.
- Flow gap: the ticket asked for docs that already existed, and the spec
  prompt gave no routing guidance, so the agent emitted `complete` → "queue
  empty; awaiting human input", and the spec gate never fired (gates approve
  handoffs; a `complete` outcome bypasses them). Prompts now route
  explicitly (PR #6). Ticket #5 left awaiting input; closing it manually is
  fine.

**2026-07-22 — round 3 (ticket #7, glossary page): full route validated**
- spec → gate → implement → finalize end-to-end ✅: post-PR-#6 spec proposed
  the `implement` handoff, the gate comment posted, `/agent-hq approve
  <run-id>` advanced it, implement landed on `agent-hq/7` and opened
  `amjithtitus09/docs-1#1` (draft), finalize wrote `summary.md`, posted the
  closing summary, marked the PR ready, closed the issue, ticket `DONE`.
- Known-usage retry ✅: implement attempt 0 failed in collect and was
  auto-re-enqueued (contrast round 1's unknown-spend block). Root cause was
  an engine bug — `apply_patch` passed the patch path relative to the
  process cwd into `git apply` running with `cwd=worktree`, so the
  workdir-relative clone paths of `run-phases.sh` doubled up ("can't open
  patch"); unit tests only used absolute paths. Fixed + regression test
  (PR #8). Attempt 1 burned pre-merge via the 15-min cron (kill switch was
  set too late); attempt 2 succeeded on the fixed code.
- Ops lesson: when a fix must merge before a queued run may retry, set the
  kill switch **immediately** on diagnosing — the cron dispatcher races you.

**2026-07-22 — round 4 (ticket #11, patient-age format on care_fe): review loop + park validated**
- First live exercise of the `implement ↔ review` loop on a real frontend
  feature (`care_fe`). Spec was strongly grounded — located the actual
  `formatPatientAge()` in `src/Utils/utils.ts` and the real patient-card
  components. Gate approved, implement opened `care_fe#1` and handed to
  review (not finalize). ✅
- Loop ran the full 3 rounds, each doing real work: R1 found 4 test-
  expectation blockers → implement; R2 cleared them, found a pluralization
  blocker → implement; R3 cleared that, found one more test-string blocker,
  recognized "Round 3 (the round cap)" and emitted `complete`. `review.md`
  accumulated `## Round 1/2/3` via input-artifact forwarding — round memory
  works. ✅
- Park endpoint ✅: engine posted the accumulated findings to the thread
  (`…:done:review-findings`), pinned awaiting-human (`…:done:awaiting`), and
  left `care_fe#1` in **draft**. Ticket stays ACTIVE (not DONE), issue open.
- Note: the loop never took the clean `review → finalize` exit here — the
  reviewer found a fresh (minor, test-only) blocker every round. The feature
  itself is functionally complete per the reviewer; a human finishes the one
  test-string fix and merges. Clean-exit path still unproven (below).

## Not yet validated

- [ ] `request-changes` / `reject` / gate timeout paths
- [ ] Multi-repo fan-out (ticket spanning two routing keywords)
- [ ] Unknown-spend blocked ticket recovery (`/hq-recover`; tickets #3, #5
      still parked from rounds 1–2)
- [ ] `implement` → `review` → `finalize` **clean** path (review finds no
      blockers and exits to finalize → ticket DONE, PR marked ready) — round 4
      exercised the loop + park but never the clean exit

## Known limits until pending phases land

- Gate/close/reopen comment events ride the ~15-min dispatch cron (Task 14).
- **Never close or relabel a ticket issue mid-flight** — close events are
  invisible and a DONE ticket still labeled `hq:intake` can re-intake
  (Tasks 14–16).
- No `retry`/`unblock`/`reopen` operator commands yet (Tasks 16/18) — manual
  state repair only.
- `pages.yml` (dashboard) fails until GitHub Pages is enabled / Task 17.
