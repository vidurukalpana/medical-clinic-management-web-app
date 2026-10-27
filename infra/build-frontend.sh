#!/usr/bin/env bash
# Builds the React app into frontend/dist, which the website stack uploads to S3.
set -euo pipefail
cd "$(dirname "$0")/../frontend"

npm ci --silent
VITE_CLINIC_TIMEZONE=Asia/Colombo npm run build
