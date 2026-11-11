#!/usr/bin/env bash
set -euo pipefail
# Runs only inside disposable Debian/Ubuntu containers (see workflow).
arch=$(dpkg --print-architecture)
"$(dirname "$0")/install-test-deps.sh" ca-certificates curl gnupg
# Suppress service starts inside this container; do not touch the host systemd.
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d
apt-get install -y /upstream/*_linux_"$arch".deb
printf '\n# preserved across custom-caddy upgrade\n' >> /etc/caddy/Caddyfile
cp /etc/caddy/Caddyfile /tmp/Caddyfile.before
apt-get install -y /dist/*_"$arch".deb
cmp /tmp/Caddyfile.before /etc/caddy/Caddyfile
caddy list-modules | grep -qx dns.providers.cloudflare
caddy list-modules | grep -qx dynamic_dns
caddy validate --config /tests/Caddyfile --adapter caddyfile
getent passwd caddy
# A running HTTP server proves the installed binary works, without DNS-provider calls.
caddy file-server --listen 127.0.0.1:8080 --root /usr/share/caddy >/tmp/caddy.log 2>&1 &
caddy_pid=$!
trap 'kill "$caddy_pid" 2>/dev/null || true' EXIT
for _attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8080/ >/tmp/page; then
    test -s /tmp/page
    break
  fi
  sleep 1
done
test -s /tmp/page
# Test remove and reinstall as well as upgrade, retaining the conffile.
apt-get remove -y caddy
apt-get install -y /dist/*_"$arch".deb
cmp /tmp/Caddyfile.before /etc/caddy/Caddyfile
