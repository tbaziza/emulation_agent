---
name: bucketr-usage
description: >-
  Cluster many SLE / NVL_AX emulation failures into root-cause buckets using
  embeddings + LLM. Use after a multi-test simregress DOA run produces dozens of
  failures, or to deduplicate the 59 known BUG entries in
  $KB_ROOT/05_knowledge_and_debugging/known_bugs_and_fixes/. Pairs with
  loggr-usage (per-test extraction) and run_phase_detection_nvlax.sh (single-test
  scoring).
  Triggers: bucket DOA failures, cluster emu failures, group similar failures,
  reduce buckets, find root causes, regression triage, ZeBu regression bucketing,
  NVL_AX failure clustering, dedupe known bugs.
---

# bucketr — SLE / ZeBu Adapter

`bucketr` clusters arbitrary failure descriptions into semantic buckets using
**text-embedding-3-small** (cosine-similarity grouping at 80%) followed by an
**LLM** (azure:gpt-5.1 by default) to name each cluster.

> ℹ️ Origin context: bucketr was built to wrap PCH's `lsti` regression-report
> tool. **You do NOT need `lsti` on SLE.** Use bucketr in **file-mode**: point
> it at a directory of failure-text files (or the `known_bugs_and_fixes/` BUG
> set) and let it cluster.

## Tool Location

```
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python   # pre-built venv
```

## Prerequisites

| What | How |
|------|-----|
| `OPENAI_API_KEY` | `setenv OPENAI_API_KEY \`cat ~/.openai_api_key\`` — see `intel-genai-api-setup` |
| Python 3.11+ | already inside `.venv` |
| Input | one or more text files OR a directory containing them |

## Invocation Pattern

```bash
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python \
  $PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py [options] <file_or_dir>...
```

Run `--help` once to see the full menu — most flags are pass-through to lsti and
are irrelevant on SLE.

## SLE Use Cases

### 1. Cluster failures from a multi-test DOA regression

After a `simregress -l <reglist>` run that produced dozens of failing
sub-workareas, grab one error file per test and bucket them:

```bash
# Collect first-line error per failing test
mkdir -p /tmp/doa_errs && \
for t in $MODEL_ROOT/regress.*/*FAIL*; do
  bash $KB_ROOT/06_skills/loggr-usage/run_loggr_tracked.sh \
    $t/logbook.log.gz --errors --api 2>/dev/null \
    | head -3 > /tmp/doa_errs/$(basename $t).txt
done

# Cluster them
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python \
  $PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py \
  --show-reasoning /tmp/doa_errs/
```

Output: 50 failing tests → ~5–10 root causes with confidence scores.

### 2. Deduplicate the BUG KB

```bash
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python \
  $PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py \
  $KB_ROOT/05_knowledge_and_debugging/known_bugs_and_fixes/BUG-*.md
```

Surfaces near-duplicate BUG entries that should be merged. As of writing the
KB has **59 BUG files** — useful before adding BUG-060.

### 3. Diff two regression runs (week-over-week)

```bash
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python \
  $PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py \
  /tmp/doa_errs_ww46/ /tmp/doa_errs_ww47/
```

Tells you which failure buckets are new vs. recurring.

### 4. Quick non-LLM run (for sanity / offline)

```bash
$PCD_VAL_AGENTS_TOOLS_DIR/bucketr/.venv/bin/python \
  $PCD_VAL_AGENTS_TOOLS_DIR/bucketr/bucketr.py \
  --no-llm /tmp/doa_errs/
```

Embeddings-only — works without `OPENAI_API_KEY`, faster, less descriptive
cluster names.

## bucketr-Specific Flags Worth Knowing

| Flag | When to use |
|------|-------------|
| `--no-llm` | API down, offline, or fast preview |
| `--llm-model azure:gpt-4o-mini` | Cheaper / faster than default gpt-5.1 |
| `--show-reasoning` | See why two failures merged — great for tuning |
| `--sort confidence` | Surface most-certain merges first |
| `--sort failures` | Default — biggest-blast-radius cluster first |

## What to Skip on SLE

- All `-rgr_id <id>`, `-triage`, `-compare`, `-f` flags — these are `lsti`
  pass-through and require PCH's regression DB. Not used in the NVL_AX flow.

## Recommended Workflow

```text
50+ DOA failures in this regression
        │
        ├── For each failing test:
        │     loggr --errors logbook.log.gz   → 1 text file per test
        │
        ├── bucketr /tmp/doa_errs/            → 5–10 root-cause buckets
        │
        ├── For each bucket:
        │     grep -rl "<bucket signature>" $KB_ROOT/.../known_bugs_and_fixes/
        │     → known bug? apply fix
        │     → unknown? file a new BUG-NNN.md (see documentation_rules.md)
        │
        └── Done: 50 failures → 5 actions
```

## Cross-References

- `$KB_ROOT/06_skills/loggr-usage/` — produces the per-test input bucketr consumes
- `$KB_ROOT/06_skills/intel-genai-api-setup/` — required for LLM mode
- `$KB_ROOT/05_knowledge_and_debugging/known_bugs_and_fixes/` — what to grep into after bucketing
- `$KB_ROOT/05_knowledge_and_debugging/documentation_rules.md` — how to add a new BUG

## Constraints

1. NEVER `pip install` — venv is pre-built
2. Always set `OPENAI_API_KEY` before LLM-mode runs
3. Stick to file-mode on SLE; the `lsti` integration is PCH-only
4. LLM cluster names are advisory — always cross-check against the BUG KB before
   declaring a root cause
