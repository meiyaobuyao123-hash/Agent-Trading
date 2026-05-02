#!/usr/bin/env bash
# verify.sh — 本地一键 verify(等同 CI eval gate 跑的内容)
#
# 引用 docs/runbook/eval-runbook.md
# 引用 .github/workflows/eval-gate.yml
#
# Usage:
#   ./scripts/verify.sh                  # 默认:跳 launch(开发模式)
#   ./scripts/verify.sh --full           # 跑全 9 含 launch(模拟 nightly)
#   ./scripts/verify.sh --tests-only     # 只跑 self-tests
#   ./scripts/verify.sh --eval-only      # 只跑 9 suite eval(跳 self-tests)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."  # services/pump-scanner

MODE="${1:-default}"
SKIP_ARG="--skip launch_criteria"
RUN_TESTS=true
RUN_EVAL=true

case "$MODE" in
  --full)
    SKIP_ARG=""
    ;;
  --tests-only)
    RUN_EVAL=false
    ;;
  --eval-only)
    RUN_TESTS=false
    ;;
  default|"") ;;
  *)
    echo "Usage: $0 [--full | --tests-only | --eval-only]"
    exit 1
    ;;
esac

echo "=================================================="
echo "Local verify (mode: $MODE)"
echo "  CWD: $(pwd)"
echo "  SKIP_ARG: $SKIP_ARG"
echo "  RUN_TESTS: $RUN_TESTS"
echo "  RUN_EVAL: $RUN_EVAL"
echo "=================================================="

EXIT_CODE=0

if [ "$RUN_EVAL" = true ]; then
  echo ""
  echo "▶ Step 1/2: 9 suite eval ($SKIP_ARG)"
  echo "--------------------------------------------------"
  if ! python3 -m agent.eval.run_all $SKIP_ARG; then
    echo "❌ eval hard gate failed"
    EXIT_CODE=1
  fi
fi

if [ "$RUN_TESTS" = true ]; then
  echo ""
  echo "▶ Step 2/2: eval framework self-tests"
  echo "--------------------------------------------------"
  if ! python3 -m pytest \
      tests/test_eval_runner.py \
      tests/test_eval_skill_runner.py \
      tests/test_eval_prompt_runner.py \
      tests/test_eval_chain_runner.py \
      tests/test_eval_safety_runner.py \
      tests/test_eval_trajectory_runner.py \
      tests/test_eval_launch_runner.py \
      tests/test_eval_rubric_runner.py \
      tests/test_eval_judge_runner.py \
      tests/test_eval_run_all.py \
      tests/test_input_filter.py \
      tests/test_rollout_gate.py \
      tests/test_rollout_gate_integration.py \
      tests/test_tools_t01_t02_t03_t08.py \
      -q --tb=line; then
    echo "❌ self-tests failed"
    EXIT_CODE=1
  fi
fi

echo ""
echo "=================================================="
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ verify passed — safe to commit / push"
else
  echo "❌ verify FAILED — fix before commit"
  echo "   See docs/runbook/eval-runbook.md §4 (triage)"
fi
echo "=================================================="

exit $EXIT_CODE
