#!/bin/sh
set -eu
cd "$(dirname "$0")"
runtime=${OPENVR_RUNTIME_DIR:-/opt/steamvr/bin/linuxarm64}
for dependency in python3 g++ gamescopectl; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$dependency" >&2
        exit 1
    fi
done
if [ "$(uname -m)" != aarch64 ] || [ ! -f "$runtime/libopenvr_api.so" ]; then
    printf '%s\n' 'Run this installer on Steam Frame with its ARM64 SteamVR runtime installed.' >&2
    exit 1
fi
mkdir -p build/include
headers=${OPENVR_INCLUDE_DIR:-"$PWD/build/include"}
if [ -z "${OPENVR_INCLUDE_DIR:-}" ]; then
    python3 - <<'PY'
import hashlib
from pathlib import Path
import urllib.request
revision = '0924064316de3effbcd1acf1e309182a2deb1c05'
expected = '1e6ed57199896cc1f7c5484e50fa18955e97be15be690beb28d998c877ead7fd'
path = Path('build/include/openvr.h')
data = path.read_bytes() if path.exists() else b''
if hashlib.sha256(data).hexdigest() != expected:
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/ValveSoftware/openvr/{revision}/headers/openvr.h', timeout=30) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit('OpenVR header checksum mismatch; installation stopped.')
    path.write_bytes(data)
PY
fi
install -d "$HOME/.local/lib/frame-stereo" "$HOME/.local/bin"
g++ -std=c++17 -O2 -Wall -Wextra -I"$headers" src/overlay.cpp -L"$runtime" -Wl,-rpath,"$runtime" -lopenvr_api -o build/overlay-helper
install -m 755 build/overlay-helper "$HOME/.local/lib/frame-stereo/overlay-helper.new"
mv "$HOME/.local/lib/frame-stereo/overlay-helper.new" "$HOME/.local/lib/frame-stereo/overlay-helper"
cmp build/overlay-helper "$HOME/.local/lib/frame-stereo/overlay-helper"
install -m 644 frame_stereo.py "$HOME/.local/lib/frame-stereo/frame_stereo.py"
install -m 755 frame-stereo "$HOME/.local/bin/frame-stereo"
python3 - <<'PY'
from pathlib import Path
home = Path.home()
applications = home / '.local/share/applications'
applications.mkdir(parents=True, exist_ok=True)
# Quote the executable for Desktop Entry Exec syntax, not for a shell.
exe = str(home / '.local/bin/frame-stereo')
for char in ('\\', '"', '`', '$'):
    exe = exe.replace(char, '\\' + char)
exe = exe.replace('%', '%%').replace('\\', '\\\\')
for mode in ('half', 'full'):
    template = Path(f'frame-stereo-{mode}.desktop').read_text()
    (applications / f'frame-stereo-{mode}.desktop').write_text(template.replace('@FRAME_STEREO_EXEC@', '"' + exe + '"'))
(applications / 'frame-stereo.desktop').unlink(missing_ok=True)
PY
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications"
fi
printf '%s\n' 'Installed Half SBS Toggle and Full SBS Toggle. Reopen Launch Program to see them.'
