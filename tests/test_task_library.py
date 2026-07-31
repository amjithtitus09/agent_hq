"""Task library: schema/library validity, handoff-target resolution,
gate-adapter resolvability, and no-concrete-adapter-name discipline. The
static P0_CHAIN (on_success/on_failure) is gone with the atomic handoff
cutover (Task 9) -- every enqueue is a validated handoff, so this file
asserts the generic properties every task must hold, not one fixed chain.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.cli import build_parser
from engine.config import load_config, resolve_binding
from engine.engine import build_port_adapter
from engine.taskdefs import load_all, validate_library

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
TASKS_DIR = REPO_ROOT / "tasks"
CONFIG_DIR = REPO_ROOT / "config"

# Every wired task and its P1 (defined-but-unwired) siblings; no `intake` --
# intake is engine entry logic (config.projects["intake"]/["initial_task"]),
# not a task definition.
EXPECTED_TASK_IDS = {
    "spec", "arch-plan", "arch-approval", "breakdown", "implement", "review",
    "finalize", "clinical", "poll", "qa", "docs",
}

# The wired handoff graph a fresh ticket walks (spec's fan-out is capacity,
# not a fixed edge -- it emits 1..handoff.max `implement` handoffs depending
# on how many repos a ticket touches).
EXPECTED_HANDOFF_ALLOWED = {
    "spec": (["implement"], 3),
    "arch-plan": (["arch-approval", "breakdown"], 1),
    "arch-approval": (["breakdown"], 1),
    "breakdown": (["implement"], 2),
    "implement": (["review"], 1),
    "review": (["implement", "qa"], 1),
    "finalize": ([], 0),
    "clinical": (["arch-plan"], 1),
    "poll": ([], 0),
    "qa": (["finalize"], 1),
    "docs": (["finalize"], 1),
}

CONCRETE_ADAPTER_NAMES = (
    "github-issues", "github-comment", "pr-review", "github-issue-comment",
    "claude-code-headless", "copilot-cli",
)


def test_task_library_loads_and_validates_clean():
    taskdefs = load_all(TASKS_DIR, SCHEMAS_DIR)
    assert set(taskdefs) == EXPECTED_TASK_IDS
    assert validate_library(taskdefs) == []


def test_handoff_targets_resolve_within_the_library():
    """Every handoff.allowed target of every task resolves to a loaded task
    id (validate_library's own check), and the graph's specific
    allowed-set/max matches the plan -- most tellingly spec's
    handoff.max: 3, the minimal route's per-repo fan-out point."""
    taskdefs = load_all(TASKS_DIR, SCHEMAS_DIR)
    for task_id, (allowed, max_handoffs) in EXPECTED_HANDOFF_ALLOWED.items():
        handoff = taskdefs[task_id].get("handoff", {})
        assert handoff.get("allowed", []) == allowed, f"{task_id}: handoff.allowed mismatch"
        assert handoff.get("max", 0) == max_handoffs, f"{task_id}: handoff.max mismatch"
        for target in allowed:
            assert target in taskdefs, f"{task_id}: handoff target '{target}' not in library"


def test_gate_tasks_resolve_to_constructible_adapters():
    config = load_config(CONFIG_DIR, SCHEMAS_DIR)
    taskdefs = load_all(TASKS_DIR, SCHEMAS_DIR)
    gate_tasks = [t for t in taskdefs.values() if t.get("gates", {}).get("post")]
    assert gate_tasks, "expected at least one gate task in the library"
    for taskdef in gate_tasks:
        for gate in taskdef["gates"]["post"]:
            adapter_name = resolve_binding(config, "gate", gate["adapter"], [])
            adapter = build_port_adapter(config, "gate", adapter_name, repo="amjithtitus09/care")
            assert adapter is not None


def test_default_and_spec_approval_gate_bindings_use_the_issue_comment_gate():
    """The atomic cutover repoints the default/spec-approval gate bindings
    off pr-review onto the authorized issue-comment gate (docs/ports/gate.md)."""
    config = load_config(CONFIG_DIR, SCHEMAS_DIR)
    assert resolve_binding(config, "gate", "default", []) == "github-issue-comment"
    assert resolve_binding(config, "gate", "spec-approval", []) == "github-issue-comment"


def test_no_concrete_adapter_name_leaks_into_task_defs():
    for task_yml in TASKS_DIR.glob("*/task.yml"):
        text = task_yml.read_text()
        for name in CONCRETE_ADAPTER_NAMES:
            assert name not in text, f"{task_yml}: concrete adapter name '{name}' found"


def test_no_intake_task_directory():
    assert not (TASKS_DIR / "intake").exists()


def test_cli_tasks_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "engine.cli", "tasks", "validate", "--repo-root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT, check=False
)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tasks OK" in result.stdout


def test_cli_tasks_validate_direct_call(capsys):
    parser = build_parser()
    args = parser.parse_args(["tasks", "validate", "--repo-root", str(REPO_ROOT)])
    args.func(args, REPO_ROOT)
    assert "tasks OK" in capsys.readouterr().out
