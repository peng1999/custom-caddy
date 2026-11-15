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
caddy list-modules | grep -qx http.handlers.webdav
caddy validate --config /tests/Caddyfile --adapter caddyfile
getent passwd caddy
"$(dirname "$0")/test-webdav.sh"
# Test remove and reinstall as well as upgrade, retaining the conffile.
apt-get remove -y caddy
apt-get install -y /dist/*_"$arch".deb
cmp /tmp/Caddyfile.before /etc/caddy/Caddyfile
