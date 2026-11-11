#!/usr/bin/env bash
set -euo pipefail
# GNUPGHOME must point at an isolated keyring containing the repository signing key.
site=${1:-site}
mkdir -p "$site/pool/main/c/caddy"
cp dist/*.deb "$site/pool/main/c/caddy/"
cp keys/archive-key.asc "$site/archive-key.asc"
cp dist/manifest.json "$site/latest.json"
cp packaging/caddy.preferences "$site/caddy.preferences"
cp packaging/caddy.sources "$site/caddy.sources"
cp packaging/index.html "$site/index.html"
root=$(realpath "$site")
for arch in amd64 arm64; do
  directory="$root/dists/stable/main/binary-$arch"
  mkdir -p "$directory"
  (cd "$root" && apt-ftparchive --arch "$arch" packages pool) > "$directory/Packages"
  gzip -n -9 -c "$directory/Packages" > "$directory/Packages.gz"
  # APT prefers the strongest advertised hash (apt-ftparchive emits SHA512 too).
  for algorithm in sha256 sha512; do
    mkdir -p "$directory/by-hash/${algorithm^^}"
    for file in "$directory/Packages" "$directory/Packages.gz"; do
      digest=$("${algorithm}sum" "$file" | cut -d ' ' -f1)
      cp "$file" "$directory/by-hash/${algorithm^^}/$digest"
    done
  done
done
(cd "$root" && apt-ftparchive \
  -o APT::FTPArchive::Release::Origin=custom-caddy \
  -o APT::FTPArchive::Release::Label=custom-caddy \
  -o APT::FTPArchive::Release::Suite=stable \
  -o APT::FTPArchive::Release::Codename=stable \
  -o APT::FTPArchive::Release::Architectures='amd64 arm64' \
  -o APT::FTPArchive::Release::Components=main \
  -o APT::FTPArchive::Release::Acquire-By-Hash=yes \
  release dists/stable) > "$root/dists/stable/Release"
fingerprint=$(gpg --show-keys --with-colons keys/archive-key.asc | awk -F: '$1 == "fpr" {print $10; exit}')
gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 \
  --clearsign --output "$root/dists/stable/InRelease" "$root/dists/stable/Release"
gpg --batch --yes --local-user "$fingerprint" --digest-algo SHA256 \
  --armor --detach-sign --output "$root/dists/stable/Release.gpg" "$root/dists/stable/Release"
gpg --verify "$root/dists/stable/InRelease"
printf 'Signed repository with %s\n' "$fingerprint"
