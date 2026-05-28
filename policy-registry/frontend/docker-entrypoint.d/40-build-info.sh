#!/bin/sh
set -eu

APP_VERSION="${APP_VERSION:-1.0.10}"
BUILD_ID="${BUILD_ID:-${HOSTNAME:-unknown}}"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > /usr/share/nginx/html/build-info.json <<EOF
{
  "version": "${APP_VERSION}",
  "build_id": "${BUILD_ID}",
  "build_time": "${BUILD_TIME}"
}
EOF
