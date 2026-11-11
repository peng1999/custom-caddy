# Custom Caddy APT repository

Caddy with **Cloudflare DNS** (`dns.providers.cloudflare`) and **Dynamic DNS** (`dynamic_dns`), packaged for Debian/Ubuntu on **amd64** and **arm64**. This is an independent distribution, not an official Caddy build.

A local daily timer checks upstream stable releases and dispatches GitHub Actions only when publication is needed. GitHub builds and tests both binaries, publishes packages in Releases, and serves a signed APT repository through GitHub Pages. There are **no scheduled GitHub workflows** and no heartbeat commits.

## Installation

Back up your Caddy configuration first. If you previously followed Caddy's `dpkg-divert` / `update-alternatives` custom-binary instructions, undo that setup before installing this package: a diversion of `/usr/bin/caddy` would prevent this package's binary from becoming the active command. Check with `dpkg-divert --list | grep caddy` and `readlink -f /usr/bin/caddy`.

Download the public key and repository configuration:

```bash
curl -fsSLo /tmp/custom-caddy.asc https://peng1999.github.io/custom-caddy/archive-key.asc
gpg --show-keys --with-fingerprint /tmp/custom-caddy.asc
# Expected fingerprint: F41C8C0C03677A23F9980B8F95B677EFC798C6D8
sudo install -d -m 0755 /etc/apt/keyrings
sudo install -m 0644 /tmp/custom-caddy.asc /etc/apt/keyrings/custom-caddy.asc
curl -fsSLo /tmp/custom-caddy.sources https://peng1999.github.io/custom-caddy/caddy.sources
curl -fsSLo /tmp/custom-caddy.preferences https://peng1999.github.io/custom-caddy/caddy.preferences
sudo install -m 0644 /tmp/custom-caddy.sources /etc/apt/sources.list.d/custom-caddy.sources
sudo install -m 0644 /tmp/custom-caddy.preferences /etc/apt/preferences.d/custom-caddy
sudo apt update
apt-cache policy caddy
sudo apt install caddy
```

The candidate should have a version such as `2.11.9-1+custom.1` from `custom-caddy`. The preference deliberately gives this distribution priority 1001, including when a newer standard package is available. That prevents standard packages replacing your plugins; on first migration this can select an older upstream version than the installed standard build. Review `apt-cache policy` before installing. You may leave the official APT source enabled.

After this one-time setup:

```bash
sudo apt update
sudo apt upgrade
caddy list-modules | grep -E '^(dns.providers.cloudflare|dynamic_dns)$'
```

The upstream `.deb` supplies systemd units, maintainer scripts, default configuration, manual pages and completion files. We replace `/usr/bin/caddy`, update package metadata/checksums, and add build provenance. Your `/etc/caddy/Caddyfile` is a conffile and is preserved on upgrade. As with upstream, installation starts the service and upgrades may restart it. Package purge follows the upstream scripts and removes Caddy state/configuration; use `remove`, not `purge`, when you want to retain them.

## Local release checks

Requirements: Linux, Python 3, an authenticated GitHub CLI account with write access to this repository, and a systemd user manager. `gh auth login` stores authentication locally; no token belongs in this repository or timer unit. The checker uses only the GitHub API; no Go compiler is needed locally.

```bash
git clone https://github.com/peng1999/custom-caddy.git
cd custom-caddy
python3 scripts/check-update.py --check-only
python3 scripts/check-update.py
python3 scripts/install-local-timer.py
```

The timer runs daily at 09:17 local time with up to 30 minutes of jitter. `Persistent=true` catches missed checks when the user manager next starts. Keep the checkout at that path. For unattended checks while logged out, enable lingering for the account:

```bash
loginctl enable-linger "$USER"
systemctl --user list-timers custom-caddy-check.timer
journalctl --user -u custom-caddy-check.service
```

Checks read `build-config.json` from GitHub, so a stale local checkout still notices new package revisions. A published release is the success marker; drafts and failed builds are retried. Active/queued builds are skipped, and GitHub serializes release workflows. Errors remain errors and are visible in the service journal. If this machine stays offline, checks resume when it returns. To trigger a build without this machine, use Actions → **Build and publish Caddy** → **Run workflow**, or:

```bash
gh workflow run release.yml --repo peng1999/custom-caddy --ref main
```

To uninstall the timer:

```bash
systemctl --user disable --now custom-caddy-check.timer
rm ~/.config/systemd/user/custom-caddy-check.{service,timer}
systemctl --user daemon-reload
```

## Release process and maintenance

`build-config.json` pins xcaddy and both plugin commits. The workflow resolves Caddy's latest stable `vX.Y.Z` release, verifies official `.deb` checksums, and builds with CGO disabled. It verifies that dependency resolution did not silently upgrade Caddy, checks module registration on native amd64 and arm64 runners, and validates a configuration containing both plugins without calling Cloudflare's API. Disposable Debian 12 and Ubuntu 24.04 containers test an official-to-custom upgrade, conffile preservation, removal/reinstallation, HTTP serving, and signed APT installation. CI retries Ubuntu archive failures through the USTC mirror with Ubuntu signature verification still required; this affects only disposable runners/containers. Other systemd-based Debian/Ubuntu versions may work but are not part of this test matrix. Package lifecycle container tests run natively on both architectures.

GitHub Actions uses standard public-repository runners. Build artifacts expire after three days. Release assets keep the complete package history, checksums, build manifest, dependency listings, and the generated source module (`main.go`, `go.mod`, `go.sum`). These record exact resolved inputs; byte-for-byte reproducibility across toolchains is not claimed.

Only after tests pass does the workflow import `APT_SIGNING_KEY` on a fresh publication runner. It builds a signed repository with `InRelease` and `Release.gpg`, tests APT signature verification/installation, stages a draft Release, deploys Pages, and finally marks the Release published. Publication failures leave the version eligible for retry. A deployment can become visible just before a final API failure; rerunning safely completes that same draft.

APT retains the current and two previous published builds; older packages remain in Releases. Indexes use acquire-by-hash. Very stale clients may need `apt update` again after an old package leaves the pool. Release metadata has no `Valid-Until` because upstream may go months without releases; signature/hash verification remains required. The signing key has no automatic expiry: retain a secure backup and rotate it deliberately if compromised.

To update a plugin or rebuild the same upstream Caddy release, edit its pin and increment `package_revision`, commit/push, then dispatch the workflow. Published versions are immutable. Pinned plugins can become incompatible with future Caddy releases: the build fails rather than publishing an unverified package. Review Actions failures and update the pins when necessary.

For a fresh fork/setup:

1. Replace repository URLs in `packaging/`, the checker defaults and this README.
2. Create an APT signing key in a private local keyring. Export only the public key to `keys/archive-key.asc` and its fingerprint to `keys/FINGERPRINT`.
3. Store the ASCII-armored secret key as the repository Actions secret `APT_SIGNING_KEY`; keep a secure backup outside Git. Never commit the private key.
4. Enable GitHub Pages with **GitHub Actions** as its build source.
5. Push to `main`, run CI, then dispatch `release.yml`.

## Rollback and returning to standard Caddy

Use `apt-cache madison caddy` to see retained versions, then explicitly select one:

```bash
sudo apt install --allow-downgrades caddy=VERSION
```

An older version can also be downloaded from Releases after checking its `SHA256SUMS`. For a sustained rollback, use `sudo apt-mark hold caddy` and later `sudo apt-mark unhold caddy`.

To return to standard packages, remove `/etc/apt/sources.list.d/custom-caddy.sources` and `/etc/apt/preferences.d/custom-caddy`, update APT, then explicitly install the desired standard version with `--allow-downgrades` if necessary. Remove plugin-dependent configuration before starting a standard Caddy build. No uninstall/reinstall or purge is needed.

## Upstream projects and licenses

- [Caddy](https://github.com/caddyserver/caddy) — Apache-2.0
- [xcaddy](https://github.com/caddyserver/xcaddy) — Apache-2.0
- [Cloudflare DNS provider](https://github.com/caddy-dns/cloudflare) — Apache-2.0
- [Dynamic DNS app](https://github.com/mholt/caddy-dynamicdns) — Apache-2.0

Repository automation is MIT-licensed. Packaged upstream files and dependencies retain their respective licenses.
