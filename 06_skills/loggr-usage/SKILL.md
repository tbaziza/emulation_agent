---
name: loggr-usage
description: >-
  Analyze SLE / NVL_AX emulation logs with the loggr CLI. Pulls errors, plusargs,
  workarea hints, and timing tables out of logbook.log.gz, emurun.log,
  assertion_failures.log, or any text/.gz log under a DOA test workarea. Use after
  a failed simregress DOA run, or when triaging a hang. For deeper bucketing across
  many failing tests, chain with bucketr-usage. For phase detection, pair with
  $KB_ROOT/05_knowledge_and_debugging/run_phase_detection_nvlax.sh.
  Triggers: analyze emu log, parse logbook.log, parse emurun.log, extract errors,
  extract plusargs, DOA log analysis, emu test triage, ZeBu log parsing, NVL_AX
  failure summary, what failed in this DOA run.
---

# loggr — SLE / ZeBu Adapter

`loggr` is a generic log analyzer originally written for UVM/PCH (jestr.log /
postsim.log). On the SLE Emulation Agent we use it for the **generic** flags
that work on **any** text or gzipped log — primarily `--errors`, `--plusargs`,
`--workarea`, `--html`, and the timeline / timing views.

> ⚠️ UVM-specific flags (`--seq-info`, `--sequence-times`, `--phase-times`,
> `--seq-source`, `--domain-info`, `--static-disables`) target UVM sim logs.
> They will usually return empty on ZeBu emu logs — don't rely on them here.

## Tool Location

```
$PCD_VAL_AGENTS_TOOLS_DIR/loggr/loggr.py            # the tool
$PCD_VAL_AGENTS_TOOLS_DIR/loggr/.venv/bin/python    # pre-built venv (DO NOT pip install)
```

`PCD_VAL_AGENTS_TOOLS_DIR` defaults to `~/.copilot/copilot_agent_tools`.

## Wrapper Script (use this, not loggr.py directly)

`run_loggr_tracked.sh` (shipped in this skill folder) handles:
- venv activation
- exit-code propagation
- /tmp logging
- optional session-recorder integration

```bash
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  <logfile> <loggr-flags...>
```

## SLE-Specific Invocations

Assume `TEST=<doa-workarea>` (the dir simregress wrote: results.log, logbook.log.gz,
emurun.log, assertion_failures.log).

### 1. What errors are in this DOA run?

```bash
# Primary error summary (works on .gz too)
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  $TEST/logbook.log.gz --errors --api

# Cross-check against emurun-side errors
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  $TEST/emurun.log --errors --api
```

`--api` returns JSON — easier to pipe into the BUG-matcher.

### 2. What plusargs did simregress launch with?

```bash
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  $TEST/emurun.log --plusargs --api
```

Useful when comparing a failing DOA against a passing reference — diff the
plusarg set to spot env drift.

### 3. Identify the workarea from a stray log

If the user pastes a log path with no context:

```bash
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  <some.log> --workarea
```

Prints the inferred `MODEL_ROOT` and DUT.

### 4. Compare two DOA runs (passing vs failing)

```bash
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  $FAIL/emurun.log --compare-plusargs $PASS/emurun.log
```

Surfaces plusarg deltas — the most common cause of a regression DOA.

### 5. HTML report for sharing

```bash
bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
  $TEST/logbook.log.gz --html /tmp/doa_$(date +%s).html --no-menu
```

Drop the HTML on a wiki page or paste it in an HSD.

## SLE Log Cheat Sheet

| SLE log | What loggr finds | Notes |
|---------|------------------|-------|
| `logbook.log.gz` | stage table, errors, totals | the agent's primary truth source |
| `emurun.log` | plugin / RPATH / kerberos / queue cycling | step-3 emu setup + runtime |
| `assertion_failures.log` | SVA violations from post-processing | empty == passing post-proc |
| `results.log` | overall PASS/FAILED marker | one-liner |
| `testbench.log` | TB plumbing errors | rare, but `--errors` works |
| `ptracker.log` | mailbox / request-response | use grep, loggr won't parse it |
| `bootfsm_state_tracker.log.gz` | boot FSM hangs | use zgrep |

## Recommended Workflow (Step 4b of the Agent)

```text
DOA test failed
   │
   ├── 1. loggr --errors logbook.log.gz   → first-line symptom
   ├── 2. loggr --errors emurun.log       → cross-check emu side
   ├── 3. loggr --plusargs emurun.log     → snapshot the launch env
   │
   ├── 4. Feed top error string into:
   │       grep -rl "<error>" $KB_ROOT/05_knowledge_and_debugging/known_bugs_and_fixes/
   │       run_phase_detection_nvlax.sh $TEST
   │
   └── 5. If 50+ failing DOA tests across a regression → see bucketr-usage
```

## Cross-References

- `$KB_ROOT/05_knowledge_and_debugging/debug_workflow.md` — full debug protocol
- `$KB_ROOT/05_knowledge_and_debugging/run_phase_detection_nvlax.sh` — automated BUG matcher
- `$KB_ROOT/06_skills/bucketr-usage/` — for clustering many failures
- `$KB_ROOT/06_skills/intel-genai-api-setup/` — required if using `--api` with LLM modes

## Constraints

1. ALWAYS use the wrapper script — never call `loggr.py` directly
2. NEVER `pip install` — the venv is pre-built
3. DO NOT use the UVM-only flags listed at the top — they emit empty on emu logs
4. For files >1 GB, gzip them first; loggr handles `.gz` natively
