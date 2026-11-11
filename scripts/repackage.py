#!/usr/bin/env python3
"""Keep the official package's support files and maintainer scripts."""
import hashlib
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
version, arch = sys.argv[2:]
control = root / 'DEBIAN/control'
text = control.read_text()
if not re.search(r'^Package: caddy$', text, re.M):
    raise SystemExit('Unexpected upstream package name')
if not re.search(rf'^Architecture: {arch}$', text, re.M):
    raise SystemExit('Unexpected upstream package architecture')
for field, value in {
    'Version': version,
    'Maintainer': 'peng1999 <12483662+peng1999@users.noreply.github.com>',
    'Homepage': 'https://github.com/peng1999/custom-caddy',
    'Installed-Size': str(sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and 'DEBIAN' not in p.parts) // 1024 + 1),
}.items():
    pattern = rf'^{field}:.*$'
    if re.search(pattern, text, re.M):
        text = re.sub(pattern, f'{field}: {value}', text, flags=re.M)
    else:
        text += f'{field}: {value}\n'
# Explicitly label the custom distribution while retaining upstream description.
text = re.sub(r'^Description:.*$', 'Description: Caddy with Cloudflare DNS and Dynamic DNS plugins', text, flags=re.M)
control.write_text(text)
# Refresh checksums after replacing the binary and adding provenance documentation.
(root / 'usr/share/doc/caddy').mkdir(parents=True, exist_ok=True)
(root / 'usr/share/doc/caddy/custom-build-info.txt').write_text(
    Path(f'dist/build-info_{arch}.txt').read_text())
lines = []
for path in sorted(root.rglob('*')):
    relative = path.relative_to(root)
    if path.is_file() and not path.is_symlink() and relative.parts[0] != 'DEBIAN':
        lines.append(f'{hashlib.md5(path.read_bytes()).hexdigest()}  {relative}\n')
(root / 'DEBIAN/md5sums').write_text(''.join(lines))
