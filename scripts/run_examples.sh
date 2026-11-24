#!/usr/bin/env bash
# Run every example script with arguments that exercise it, and fail on the first error.
# Used by `make examples` and by .github/workflows/examples.yml (single source of truth).
set -euo pipefail
cd "$(dirname "$0")/../examples"

run() {
  echo "+ $*"
  "$@"
}

run python basic_example.py --name "TestApp" --count 3 --debug
run python advanced_example.py --name "TestServer" --debug
run python advanced_example.py --name "FileServer" --system-prompt "@prompts/server_prompt.txt"
run python advanced_example.py --config server_config.yaml --name "ConfigServer"
run python cli_short_example.py -n "TestApp" -p 9000 --workers 4 -d
run python cli_choices_example.py -n "TestDeploy" -e prod -r us-west-2
run python boolean_flags_example.py -p "TestBuild" --no-test -d
run python all_features_example.py -n "TestApp" -e staging -r us-east-1 -d
run python programmatic_example.py
run python deep_merge_example.py
run python layered_config_example.py

for example in basic_example advanced_example cli_short_example cli_choices_example \
  boolean_flags_example all_features_example; do
  run python "${example}.py" --help > /dev/null
done

echo "All examples passed"
