#!/usr/bin/env bash
# Creates or updates every CareFlow resource in AWS. Safe to run again after any change.
set -euo pipefail
cd "$(dirname "$0")"

./build-frontend.sh
./cdk.sh bootstrap   # One-time CDK setup in both regions; does nothing if already done.
./cdk.sh deploy --all
