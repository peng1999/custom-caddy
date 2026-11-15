#!/usr/bin/env bash
set -euo pipefail
caddy_binary=${1:-caddy}
export WEBDAV_TEST_HTTP_PORT=${WEBDAV_TEST_HTTP_PORT:-8080}
export WEBDAV_TEST_PORT=${WEBDAV_TEST_PORT:-8081}
test_dir=$(mktemp -d)
caddy_pid=
cleanup() {
  if [[ -n $caddy_pid ]]; then
    kill "$caddy_pid" 2>/dev/null || true
    wait "$caddy_pid" 2>/dev/null || true
  fi
  if [[ $1 != 0 ]]; then cat "$test_dir/caddy.log" >&2; fi
  rm -rf "$test_dir"
}
trap 'cleanup "$?"' EXIT
export WEBDAV_TEST_ROOT="$test_dir/storage"
mkdir -p "$WEBDAV_TEST_ROOT"
# This config has no Dynamic DNS app, so serving never calls provider APIs.
XDG_CONFIG_HOME="$test_dir/config" XDG_DATA_HOME="$test_dir/data" \
  "$caddy_binary" run --config "$(dirname "$0")/../tests/WebDAV.Caddyfile" \
  --adapter caddyfile >"$test_dir/caddy.log" 2>&1 &
caddy_pid=$!
for _attempt in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$WEBDAV_TEST_HTTP_PORT/" >"$test_dir/page"; then
    test -s "$test_dir/page"
    break
  fi
  kill -0 "$caddy_pid"
  sleep 1
done
test -s "$test_dir/page"
printf 'custom-caddy WebDAV smoke test\n' >"$test_dir/upload"
curl --fail --silent --show-error -T "$test_dir/upload" "http://127.0.0.1:$WEBDAV_TEST_PORT/smoke.txt"
curl --fail --silent --show-error "http://127.0.0.1:$WEBDAV_TEST_PORT/smoke.txt" >"$test_dir/download"
cmp "$test_dir/upload" "$test_dir/download"
cmp "$test_dir/upload" "$WEBDAV_TEST_ROOT/smoke.txt"
test "$(curl --silent --show-error --output "$test_dir/propfind" --write-out '%{http_code}' \
  -X PROPFIND -H 'Depth: 0' "http://127.0.0.1:$WEBDAV_TEST_PORT/smoke.txt")" = 207
curl --fail --silent --show-error -X DELETE "http://127.0.0.1:$WEBDAV_TEST_PORT/smoke.txt"
test ! -e "$WEBDAV_TEST_ROOT/smoke.txt"
echo 'HTTP and WebDAV upload/download, PROPFIND and DELETE passed.'
