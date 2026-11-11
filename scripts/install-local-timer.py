#!/usr/bin/env python3
"""Install a daily systemd user timer for this checkout; no GitHub cron is needed."""
import argparse
from pathlib import Path
import shutil
import subprocess


MARKER = '# Managed by custom-caddy/scripts/install-local-timer.py\n'


def quote(value):
    # systemd specifiers and ExecStart environment expansion are escaped explicitly.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='peng1999/custom-caddy')
    args = parser.parse_args()
    gh = shutil.which('gh')
    if not gh:
        raise SystemExit('Install and authenticate GitHub CLI first.')
    subprocess.run([gh, 'api', 'user', '--jq', '.login'], check=True)
    subprocess.run(['systemctl', '--user', 'show-environment'], stdout=subprocess.DEVNULL, check=True)
    checker = Path(__file__).resolve().with_name('check-update.py')
    directory = Path.home() / '.config/systemd/user'
    units = {
        'custom-caddy-check.service': MARKER + f'''[Unit]
Description=Check upstream Caddy and dispatch custom package builds
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment={quote('PATH=' + str(Path(gh).parent) + ':/usr/local/bin:/usr/bin:/bin')}
ExecStart=/usr/bin/python3 {quote(checker)} --repo {quote(args.repo)}
TimeoutStartSec=5min
''',
        'custom-caddy-check.timer': MARKER + '''[Unit]
Description=Check for Caddy releases daily

[Timer]
OnCalendar=*-*-* 09:17:00
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
''',
    }
    for name in units:
        target = directory / name
        if target.exists() and not target.read_text().startswith(MARKER):
            raise SystemExit(f'Refusing to overwrite an unrelated unit: {target}')
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in units.items():
        (directory / name).write_text(body)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'custom-caddy-check.timer'], check=True)
    print('Installed daily local timer. Keep this checkout at its current path.')
    print('Run: systemctl --user start custom-caddy-check.service')
    print('Logs: journalctl --user -u custom-caddy-check.service')
    print('For operation while logged out, enable user lingering: loginctl enable-linger "$USER"')


if __name__ == '__main__':
    main()
