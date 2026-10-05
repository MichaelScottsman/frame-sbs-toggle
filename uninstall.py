#!/usr/bin/env python3
"""Restore saved overlays, then remove only files installed by frame-sbs-toggle."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import frame_stereo as stereo


def restore(path):
    if not path.exists():
        return
    data = json.loads(path.read_text())
    if not data:
        return
    try:
        sid = stereo.session()
    except RuntimeError as error:
        if str(error) == 'SteamVR is not running.':
            return  # Saved overlay instances no longer exist.
        raise
    keys = {key for key, _ in stereo.discover(stereo.run([stereo.VRCMD, '--overlays']))}
    for identity in list(data):
        if not identity.startswith(sid + ':'):
            continue
        _, key = identity[len(sid) + 1:].split(':', 1)
        original = data[identity]
        if key in keys:
            current = stereo.helper(key)
            if current['handle'] == original['handle']:
                stereo.helper(key, original)
                print(f'Restored {key}')
        # Missing/recreated overlays must not receive old settings.
        data.pop(identity)
        stereo.save(path, data)
    stereo.restore_composition(path, data, sid)


def uninstall(home, runtime):
    stereo.ROOT = home / '.local/lib/frame-stereo'
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (runtime / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(runtime / 'state.json')  # Any failure stops before deleting recovery tools.
        files = [home / '.local/bin/frame-stereo']
        files += [home / '.local/share/applications' / name for name in (
            'frame-stereo.desktop', 'frame-stereo-half.desktop', 'frame-stereo-full.desktop')]
        files += [stereo.ROOT / name for name in ('overlay-helper', 'overlay-helper.new', 'frame_stereo.py')]
        files += [runtime / 'state.json', runtime / 'state.tmp']
        for path in files:
            path.unlink(missing_ok=True)
        try:
            stereo.ROOT.rmdir()
        except OSError:
            pass  # Keep unexpected files rather than recursively deleting them.
    if shutil.which('update-desktop-database') and (home / '.local/share/applications').is_dir():
        subprocess.run(['update-desktop-database', str(home / '.local/share/applications')], check=True)
    print('Uninstalled SBS toggles. Reopen Launch Program to refresh the menu. Source checkout retained.')


def main():
    try:
        uninstall(Path.home(), Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'frame-stereo')
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Uninstall stopped: {error}. Resolve the error and rerun; recovery files are retained if restoration failed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
