#!/usr/bin/env bash
# Deletes every CareFlow resource in AWS after asking for confirmation.
# The database keeps a final snapshot, which must be deleted by hand.
set -euo pipefail
cd "$(dirname "$0")"

./cdk.sh destroy --all
