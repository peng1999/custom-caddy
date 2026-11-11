#!/usr/bin/env bash
set -euo pipefail
# Runs in a clean container. The repository is mounted read-only at /repo.
"$(dirname "$0")/install-test-deps.sh" ca-certificates gnupg
install -m 0644 /repo/archive-key.asc /usr/share/keyrings/custom-caddy.asc
printf 'deb [signed-by=/usr/share/keyrings/custom-caddy.asc] file:/repo stable main\n' > /etc/apt/sources.list.d/custom-caddy.list
cp /repo/caddy.preferences /etc/apt/preferences.d/custom-caddy
# Signature verification must succeed; no trusted=yes or insecure-repository bypass.
apt-get -o Acquire::By-Hash=force update
apt-cache policy caddy
apt-get download caddy
candidate=$(apt-cache policy caddy | sed -n 's/^  Candidate: //p')
case "$candidate" in *+custom.*) ;; *) echo 'Custom package was not selected' >&2; exit 1;; esac
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d
apt-get install -y caddy
caddy list-modules | grep -qx dns.providers.cloudflare
caddy list-modules | grep -qx dynamic_dns
