#!/usr/bin/env bash
# Runs the CDK command-line tool with the settings and AWS credentials in infra/.env.
# Examples: ./cdk.sh synth   ./cdk.sh diff
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing infra/.env. Copy .env.example to .env and fill it in." >&2
  exit 1
fi
set -a
source .env
set +a
export AWS_DEFAULT_REGION="${AWS_REGION:-ap-south-1}"

# Python packages for the CDK app; reinstalled when requirements.txt changes.
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if [[ requirements.txt -nt .venv/.installed ]]; then
  .venv/bin/pip install --quiet -r requirements.txt
  touch .venv/.installed
fi

# The CDK command-line tool, pinned in package.json.
if [[ ! -d node_modules ]] || [[ package-lock.json -nt node_modules/.package-lock.json ]]; then
  npm ci --silent
fi

exec npx --no-install cdk "$@"
