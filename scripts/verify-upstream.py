#!/usr/bin/env python3
import hashlib
from pathlib import Path
import sys

version, directory = sys.argv[1:]
root = Path(directory)
checksums = {}
for line in (root / f'caddy_{version}_checksums.txt').read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    checksums[name.lstrip('*')] = digest
for arch in ('amd64', 'arm64'):
    name = f'caddy_{version}_linux_{arch}.deb'
    expected = checksums[name]
    algorithm = {64: 'sha256', 128: 'sha512'}[len(expected)]
    actual = hashlib.file_digest((root / name).open('rb'), algorithm).hexdigest()
    if actual != expected:
        raise SystemExit(f'Checksum mismatch: {name}')
    print(f'Upstream checksum verified: {name}')
