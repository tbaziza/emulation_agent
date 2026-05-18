#!/bin/bash
#
# Wrapper script for loggr with automatic session recording
#
# Usage: run_loggr_tracked.sh <logfile> [loggr options]
#
# This script:
#   1. Executes loggr with provided arguments
#   2. Captures output to /tmp for debugging
#   3. Displays output to terminal (agent sees results)
#   4. Automatically records to session if SESSION_ID is set
#   5. Returns loggr's exit code
#

set -e

# Resolve tools directory

if [ ! -d "$PCD_VAL_AGENTS_TOOLS_DIR/loggr" ]; then
    echo "ERROR: loggr not found at $PCD_VAL_AGENTS_TOOLS_DIR/loggr" >&2
    exit 1
fi

# Parse arguments to extract logfile and options
if [ $# -lt 1 ]; then
    echo "Usage: run_loggr_tracked.sh <logfile> [loggr options]" >&2
    echo "Example: run_loggr_tracked.sh jestr.log --errors --api" >&2
    exit 1
fi

LOGFILE="$1"
shift
LOGGR_ARGS="$@"

# Generate unique temp file for this invocation
TIMESTAMP=$(date +%s)
OUTPUT_FILE="/tmp/loggr_${TIMESTAMP}.log"

# Execute loggr, capture output with tee, preserve exit code
echo "=== Running loggr: $LOGFILE $LOGGR_ARGS ===" >&2
cd "$PCD_VAL_AGENTS_TOOLS_DIR/loggr"
set +e
./loggr.py "$LOGFILE" $LOGGR_ARGS 2>&1 | tee "$OUTPUT_FILE"
LOGGR_EXIT=$?
set -e

echo "" >&2
echo "=== loggr output saved to: $OUTPUT_FILE ===" >&2

# Auto-record to session if SESSION_ID is set
if [ -n "$SESSION_ID" ] && [ -n "$AGENT_NAME" ]; then
    echo "=== Recording to session: $SESSION_ID ===" >&2
    
    # Extract summary from output for results field
    RESULTS_SUMMARY="loggr execution completed"
    if echo "$LOGGR_ARGS" | grep -q "\-\-errors"; then
        # Extract error count if this was error extraction
        ERROR_COUNT=$(grep -E "UVM_ERROR|UVM_FATAL" "$OUTPUT_FILE" 2>/dev/null | wc -l || echo "0")
        RESULTS_SUMMARY="Analyzed errors: found $ERROR_COUNT error lines"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-phase"; then
        RESULTS_SUMMARY="Extracted phase timing information"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-sequence"; then
        RESULTS_SUMMARY="Extracted sequence timing information"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-plusargs"; then
        PLUSARG_COUNT=$(grep -c "+" "$OUTPUT_FILE" 2>/dev/null || echo "0")
        RESULTS_SUMMARY="Extracted $PLUSARG_COUNT plusargs"
    fi
    
    # Determine reason from arguments
    REASON="Execute loggr"
    if echo "$LOGGR_ARGS" | grep -q "\-\-errors"; then
        REASON="Extract errors from simulation log"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-phase-times"; then
        REASON="Get UVM phase timing"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-sequence-times"; then
        REASON="Get sequence execution timing"
    elif echo "$LOGGR_ARGS" | grep -q "\-\-plusargs"; then
        REASON="Extract runtime plusargs"
    fi
    
    # Record to session
    if [ -d "$PCD_VAL_AGENTS_TOOLS_DIR/session_recorder" ]; then
        STATUS="success"
        if [ $LOGGR_EXIT -ne 0 ]; then
            STATUS="error"
        fi
        
        python3 "$PCD_VAL_AGENTS_TOOLS_DIR/session_recorder/session_recorder.py" add-tool \
            "$SESSION_ID" \
            "$AGENT_NAME" \
            --tool "loggr-usage" \
            --reason "$REASON" \
            --results "$RESULTS_SUMMARY" \
            --command "loggr.py $LOGFILE $LOGGR_ARGS" \
            --status "$STATUS" \
            --output "$(cat "$OUTPUT_FILE")" 2>&1 | grep -E "^(Added|Error)" || true
        
        echo "=== Session recording complete ===" >&2
    else
        echo "WARNING: session_recorder not found at $PCD_VAL_AGENTS_TOOLS_DIR/session_recorder" >&2
    fi
elif [ -n "$SESSION_ID" ]; then
    echo "WARNING: SESSION_ID set but AGENT_NAME not set - skipping session recording" >&2
fi

# Return loggr's original exit code
exit $LOGGR_EXIT
