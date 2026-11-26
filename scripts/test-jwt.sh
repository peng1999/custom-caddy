#!/usr/bin/env bash
set -euo pipefail
caddy_binary=${1:-caddy}
export CADDY_TEST_HTTP_PORT=${CADDY_TEST_HTTP_PORT:-8080}
export CADDY_TEST_JWT_PORT=${CADDY_TEST_JWT_PORT:-8081}
test_dir=$(mktemp -d)
caddy_pid=
cleanup() {
  if [[ -n $caddy_pid ]]; then
    kill "$caddy_pid" 2>/dev/null || true
    wait "$caddy_pid" 2>/dev/null || true
  fi
  if [[ $1 != 0 && -f $test_dir/caddy.log ]]; then cat "$test_dir/caddy.log" >&2; fi
  rm -rf "$test_dir"
}
trap 'cleanup "$?"' EXIT
# This config has no Dynamic DNS app, so serving never calls provider APIs.
XDG_CONFIG_HOME="$test_dir/config" XDG_DATA_HOME="$test_dir/data" \
  "$caddy_binary" run --config "$(dirname "$0")/../tests/JWT.Caddyfile" \
  --adapter caddyfile >"$test_dir/caddy.log" 2>&1 &
caddy_pid=$!
for _attempt in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$CADDY_TEST_HTTP_PORT/" >"$test_dir/page"; then
    test -s "$test_dir/page"
    break
  fi
  kill -0 "$caddy_pid"
  sleep 1
done
test -s "$test_dir/page"
token() {
  python3 - "$1" <<'PYTOKEN'
import base64
import hashlib
import hmac
import json
import sys
import time


def encode(value):
    data = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=")


key = base64.b64decode("Y3VzdG9tLWNhZGR5LWp3dC1zbW9rZS10ZXN0LWtleS0x")
claims = {
    "sub": "test-user",
    "iss": "https://issuer.example.invalid/",
    "aud": sys.argv[1],
    "exp": int(time.time()) + 60,
}
message = encode({"alg": "HS256", "typ": "JWT"}) + b"." + encode(claims)
signature = hmac.new(key, message, hashlib.sha256).digest()
print((message + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode())
PYTOKEN
}
jwt_url="http://127.0.0.1:$CADDY_TEST_JWT_PORT/"
valid_token=$(token 'https://mcp.example.invalid/mcp')
wrong_audience=$(token 'https://other.example.invalid/mcp')

test "$(curl --fail --silent --show-error -H "Authorization: Bearer $valid_token" "$jwt_url")" = 'JWT accepted'
test "$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$jwt_url")" = 401
test "$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  -H "Authorization: Bearer $wrong_audience" "$jwt_url")" = 401
echo 'HTTP serving and JWT validation passed.'
