#!/usr/bin/env bash
# Deletes every CareFlow resource in AWS after asking for confirmation.
# The database keeps a final snapshot and its automated backups; the audit log bucket is kept too.
set -euo pipefail
cd "$(dirname "$0")"

read -r -p "This deletes the CareFlow website, API and database. Type DELETE to continue: " answer
if [[ "$answer" != "DELETE" ]]; then
  echo "Cancelled."
  exit 1
fi

# Turn off the database's deletion protection, then remove all stacks.
./cdk.sh deploy CareFlow-Database --exclusively --context allowDatabaseDeletion=true --require-approval never
./cdk.sh destroy --all --force
