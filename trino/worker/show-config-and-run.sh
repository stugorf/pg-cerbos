#!/usr/bin/env bash
set -euo pipefail
echo "=== EFFECTIVE /etc/trino ==="
ls -l /etc/trino || true
echo "--- config.properties ---"; sed -n '1,200p' /etc/trino/config.properties || true
echo "--- node.properties   ---"; sed -n '1,200p' /etc/trino/node.properties || true
echo "--- jvm.config        ---"; sed -n '1,200p' /etc/trino/jvm.config || true
echo "============================"
exec /usr/lib/trino/bin/launcher run --etc-dir /etc/trino 