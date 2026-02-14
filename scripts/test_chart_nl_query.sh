#!/usr/bin/env bash
# Call the natural-language graph endpoint with "Show me a bar chart of Alert types"
# and evaluate the response for chart_type, echarts_option, and data.
set -e
API_BASE="${API_BASE:-http://localhost:8082}"
EMAIL="${TEST_USER_EMAIL:-admin@pg-cerbos.com}"
PASSWORD="${TEST_USER_PASSWORD:-admin123}"

echo "=== 1. Login ==="
LOGIN_RESP=$(curl -s -X POST "${API_BASE}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}")
echo "$LOGIN_RESP" | head -c 200
echo "..."

TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)
if [ -z "$TOKEN" ]; then
  echo "Failed to get access_token from login response."
  exit 1
fi
echo "Got token (length ${#TOKEN})"

echo ""
echo "=== 2. POST /query/graph/natural-language (execute=true) ==="
NL_RESP=$(curl -s -X POST "${API_BASE}/query/graph/natural-language" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query":"Show me a bar chart of Alert types","execute":true}')

echo "Response (first 800 chars):"
echo "$NL_RESP" | head -c 800
echo ""
echo ""

echo "=== 3. Evaluate charting response ==="
echo "$NL_RESP" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print("JSON parse error:", e)
    sys.exit(1)

success = d.get("success")
executed = d.get("executed")
chart_type = d.get("chart_type")
chart_subtype = d.get("chart_subtype")
has_echarts = d.get("echarts_option") is not None
data = d.get("data")
rows = (data.get("results") if isinstance(data, dict) and "results" in data else []) or []
nrows = len(rows)
cols = (data.get("columns") if isinstance(data, dict) and "columns" in data else []) or []

print("success:", success)
print("executed:", executed)
print("chart_type:", chart_type)
print("chart_subtype:", chart_subtype)
print("echarts_option present:", has_echarts)
print("data.results row count:", nrows)
print("data.columns:", cols[:10] if len(cols) > 10 else cols)
if has_echarts:
    opt = d.get("echarts_option")
    print("echarts_option keys:", list(opt.keys()) if isinstance(opt, dict) else type(opt))
    if isinstance(opt, dict) and "series" in opt and opt["series"]:
        print("echarts_option.series[0].type:", opt["series"][0].get("type"))
print("")
if success and executed and chart_type and chart_type != "table_only" and has_echarts:
    print("PASS: Charting functions returned a chart (chart_type=%s, echarts_option present)." % chart_type)
elif success and executed and (chart_type == "table_only" or not has_echarts):
    print("FAIL: Charting did not return a chart (chart_type=%s, echarts_option=%s)." % (chart_type, has_echarts))
else:
    print("CHECK: success=%s executed=%s; inspect response above." % (success, executed))
'
