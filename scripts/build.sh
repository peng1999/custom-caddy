#!/usr/bin/env bash
set -euo pipefail
version=${1:?usage: build.sh vX.Y.Z package_version}
package_version=${2:?package version required}
[[ $version =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ $package_version =~ ^[0-9]+\.[0-9]+\.[0-9]+-1\+custom\.[0-9]+$ ]]
root=$(pwd)
mkdir -p work/upstream dist
config() { python3 -c 'import json,sys; print(json.load(open("build-config.json"))[sys.argv[1]])' "$1"; }
GOBIN="$root/work/bin" go install "github.com/caddyserver/xcaddy/cmd/xcaddy@$(config xcaddy)"
gh release download "$version" --repo caddyserver/caddy --dir work/upstream --clobber \
  --pattern "caddy_${version#v}_linux_amd64.deb" \
  --pattern "caddy_${version#v}_linux_arm64.deb" \
  --pattern "caddy_${version#v}_checksums.txt"
python3 scripts/verify-upstream.py "${version#v}" work/upstream
for arch in amd64 arm64; do
  build="$root/work/$arch"
  mkdir -p "$build/tmp"
  CGO_ENABLED=0 GOOS=linux GOARCH="$arch" TMPDIR="$build/tmp" \
    XCADDY_SKIP_CLEANUP=1 XCADDY_PRINT_VERSION=0 \
    "$root/work/bin/xcaddy" build "$version" --output "$build/caddy" \
    --with "github.com/caddy-dns/cloudflare@$(config cloudflare)" \
    --with "github.com/mholt/caddy-dynamicdns@$(config dynamicdns)"
  go version -m "$build/caddy" > "dist/build-info_${arch}.txt"
  # Reject dependency resolution that silently upgrades Caddy itself.
  awk -v expected="$version" '$1 == "dep" && $2 == "github.com/caddyserver/caddy/v2" {found=1; if ($3 != expected) exit 1} END {if (!found) exit 1}' "dist/build-info_${arch}.txt"
  runner=()
  if [[ $arch == arm64 ]]; then runner=(qemu-aarch64-static); fi
  "${runner[@]}" "$build/caddy" version | tee "dist/version_${arch}.txt"
  "${runner[@]}" "$build/caddy" list-modules > "dist/modules_${arch}.txt"
  grep -qx 'dns.providers.cloudflare' "dist/modules_${arch}.txt"
  grep -qx 'dynamic_dns' "dist/modules_${arch}.txt"
  "${runner[@]}" "$build/caddy" validate --config tests/Caddyfile --adapter caddyfile
  dpkg-deb --raw-extract "work/upstream/caddy_${version#v}_linux_${arch}.deb" "$build/package"
  install -m 0755 "$build/caddy" "$build/package/usr/bin/caddy"
  python3 scripts/repackage.py "$build/package" "$package_version" "$arch"
  dpkg-deb --build --root-owner-group "$build/package" "dist/caddy_${package_version}_${arch}.deb"
  # Retain the exact resolved module graph, including checksums, for inspection/rebuilds.
  module_dir=$(find "$build/tmp" -maxdepth 2 -name go.mod -printf '%h\n' | head -1)
  test -n "$module_dir"
  tar -czf "dist/source_${arch}.tar.gz" -C "$module_dir" main.go go.mod go.sum
done
python3 - "$version" "$package_version" <<'PY'
import json, os, sys
from pathlib import Path
manifest = json.load(open('build-config.json'))
manifest.update(upstream_version=sys.argv[1], package_version=sys.argv[2],
                repository=os.environ.get('GITHUB_REPOSITORY', 'peng1999/custom-caddy'),
                source_commit=os.environ.get('GITHUB_SHA', 'local'),
                run_url=f'https://github.com/{os.environ.get("GITHUB_REPOSITORY", "peng1999/custom-caddy")}/actions/runs/{os.environ.get("GITHUB_RUN_ID", "local")}')
Path('dist/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
(cd dist && sha256sum ./*.deb ./*.txt ./*.tar.gz manifest.json > SHA256SUMS)
