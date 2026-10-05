#!/usr/bin/env python3
"""Full/half-SBS controls for native and Steam Remote Play screens on Steam Frame."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
VRCMD = '/opt/steamvr/bin/linuxarm64/vrcmd'


def run(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f'{args[0]} failed')
    return result.stdout


def discover(output):
    entries = []
    for line in output.splitlines():
        match = re.match(r"^'(valve\.steam\.desktopgame(?:\.[0-9]+)?|steamlink_openvr-overlay)' -- ", line)
        if match:
            entries.append((match[1], ' visible ' in f'{line} '))
    return entries


def choose(entries, explicit=None):
    if explicit:
        if explicit not in [key for key, _ in entries]:
            raise RuntimeError('Requested overlay is not a supported game or Steam streaming screen. Run frame-stereo list.')
        return explicit
    visible = [key for key, active in entries if active]
    if len(visible) == 1:
        return visible[0]
    if not visible:
        raise RuntimeError('No visible game or Steam streaming screen. Open the app or stream in theatre, then retry. Run frame-stereo list to inspect screens.')
    raise RuntimeError('Multiple game screens: ' + ', '.join(visible) + '. Choose --overlay KEY.')


def session():
    # PID plus process start ticks and boot ID prevent state reuse after SteamVR restarts.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if (proc / 'comm').read_text().strip() == 'vrserver':
                ticks = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
                return Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + proc.name + ':' + ticks
        except (OSError, IndexError):
            continue
    raise RuntimeError('SteamVR is not running.')


def helper(key, state=None):
    args = [str(ROOT / 'overlay-helper'), key]
    if state is not None:
        args += [str(state['handle']), str(int(state['parallel'])), str(int(state['crossed'])), str(state['aspect'])]
    return json.loads(run(args))


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data))
    temp.replace(path)


def visible_layers(key):
    output = run([VRCMD, '--overlays'])
    return any(re.match("^'" + re.escape(key) + r"\.layer[0-9]+' -- ", line)
               and ' visible ' in f'{line} ' for line in output.splitlines())


def flatten(key, path, data, sid):
    if key == 'steamlink_openvr-overlay':
        return  # Steam streaming already supplies one image; do not alter Gamescope.
    if not visible_layers(key):
        return
    # Visible subviews establish that forced composition is currently off.
    # Save ownership before changing the session-wide setting.
    data['_composition'] = sid
    save(path, data)
    run(['gamescopectl', 'composite_force', '1'])
    run(['gamescopectl', 'debug_force_repaint'])
    for _ in range(10):
        if not visible_layers(key):
            return
        time.sleep(.1)
    raise RuntimeError('Gamescope did not combine the image layers; use off to restore.')


def restore_composition(path, data, sid):
    if data.get('_composition') != sid:
        return
    if any(k.startswith(sid + ':') for k in data):
        return
    run(['gamescopectl', 'composite_force', '0'])
    run(['gamescopectl', 'debug_force_repaint'])
    data.pop('_composition', None)
    save(path, data)


def operate(command, key, swap, path, sid, sbs_format="half"):
    current = helper(key)
    data = json.loads(path.read_text()) if path.exists() else {}
    identity = sid + ':' + current['handle'] + ':' + key
    original = data.get(identity)
    enabled = bool(current['parallel'] or current['crossed'])
    baseline = original['aspect'] if original is not None else current['aspect']
    wanted_aspect = baseline * (2.0 if sbs_format == 'half' else 1.0)
    if command == 'status':
        mode = 'normal'
        if enabled:
            mode = ('half-SBS' if abs(current['aspect'] - baseline * 2) < .0001 else 'full-SBS') if original else 'stereo'
        print(f"{key}: {mode}; aspect={current['aspect']}; swapped={bool(current['crossed'])}; saved original={original is not None}")
        return
    same_format = enabled and original is not None and abs(current['aspect'] - wanted_aspect) < .0001
    turn_on = command == 'on' or (command == 'toggle' and ((enabled and original is not None and not same_format) or (not enabled and original is None)))
    if turn_on:
        if original is None:
            data[identity] = current
            save(path, data)  # Persist before changing the overlay, including on interruption.
        flatten(key, path, data, sid)
        # Half SBS stretches compressed eye images; full SBS keeps native proportions.
        target = dict(current, parallel=not swap, crossed=swap, aspect=wanted_aspect)
    else:
        if original is None:
            if enabled:
                raise RuntimeError('Stereo was enabled outside this tool; no original settings saved. Refusing to guess the restore aspect. Use on first to capture the current state.')
            restore_composition(path, data, sid)
            print(f'{key}: already normal; unchanged')
            return
        target = original
    result = helper(key, target)
    if not turn_on:
        data.pop(identity, None)
        save(path, data)
        restore_composition(path, data, sid)
    print(f"{key}: {sbs_format + '-SBS enabled' if turn_on else 'original display restored'}; aspect={result['aspect']}; verified for 2 seconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['toggle', 'on', 'off', 'status', 'list'], default='toggle')
    parser.add_argument('--overlay', metavar='KEY', help='explicit supported main screen (including a hidden screen)')
    parser.add_argument('--swap-eyes', action='store_true', help='right image to left eye when enabling')
    parser.add_argument('--format', choices=['half', 'full'], default='half', help='SBS packing (default: half)')
    parser.add_argument('--menu', action='store_true', help='launcher mode with desktop error notifications')
    args = parser.parse_args()
    try:
        entries = discover(run([VRCMD, '--overlays']))
        if args.command == 'list':
            for key, active in entries:
                print(f"{key}\t{'visible' if active else 'hidden'}")
            if not entries:
                print('No Gamescope game screens found.')
            return 0
        if args.menu and not args.overlay and not any(active for _, active in entries):
            games = [key for key, _ in entries if key != 'valve.steam.desktopgame.0']
            if len(games) == 1:
                args.overlay = games[0]
        key = choose(entries, args.overlay)
        directory = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'frame-stereo'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (directory / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            operate(args.command, key, args.swap_eyes, directory / 'state.json', session(), args.format)
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'frame-stereo: {error}', file=sys.stderr)
        if args.menu:
            try:
                subprocess.run(['notify-send', 'Stereo 3D Toggle', str(error)], timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return 1


if __name__ == '__main__':
    sys.exit(main())
