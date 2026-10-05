# Steam Frame SBS toggles

[Install](#install-from-the-frame-console) · [Uninstall](#uninstall) · [Command line](#command-line)

Choose **Half SBS Toggle** or **Full SBS Toggle** in the Frame's **Launch Program** menu.
Click once to enable that format and again to restore the original view. Clicking the other
format switches directly to it. Half SBS stretches compressed eye images horizontally;
Full SBS keeps their native proportions. Native games and Steam’s built-in Remote Play theatre screens are supported. No terminal is needed.
If the menu was already open during installation, close and reopen it.

## Install from the Frame console

Run this in a terminal **on your Steam Frame**. Requires `git`, Python 3, `g++`,
`gamescopectl`, and the Frame's installed SteamVR runtime. The installer needs internet
access for its pinned OpenVR header; it does not require sudo or restart Steam.

```sh
git clone https://github.com/MichaelScottsman/frame-sbs-toggle.git "$HOME/.local/share/frame-sbs-toggle" &&
sh "$HOME/.local/share/frame-sbs-toggle/install-on-frame.sh"
```

Then reopen **Launch Program** and select **Half SBS Toggle** or **Full SBS Toggle**.
If a required command is missing, the installer names it and stops without installing system packages.

To update an existing installation:

```sh
git -C "$HOME/.local/share/frame-sbs-toggle" pull --ff-only &&
sh "$HOME/.local/share/frame-sbs-toggle/install-on-frame.sh"
```

## Uninstall

Open a terminal on your Steam Frame and run:

```sh
git -C "$HOME/.local/share/frame-sbs-toggle" pull --ff-only &&
sh "$HOME/.local/share/frame-sbs-toggle/uninstall-on-frame.sh"
```

If you already have the latest checkout, you can uninstall directly without downloading anything:

```sh
sh "$HOME/.local/share/frame-sbs-toggle/uninstall-on-frame.sh"
```

If you cloned into a different folder, use that folder's `uninstall-on-frame.sh` instead.
No sudo or Steam restart is needed.

The uninstaller restores saved settings for surviving overlays, releases forced composition
owned by the tool, and removes the command, helper, menu entries, and saved runtime state.
If restoring an active screen fails, it stops before removing the tools needed for recovery.
Reopen Launch Program afterward. It leaves the source checkout and system dependencies in place,
and it is safe to run again. Reinstall using `install-on-frame.sh` from the retained checkout.

## Command line

The command remains available:

```sh
~/.local/bin/frame-stereo
~/.local/bin/frame-stereo on --format half
~/.local/bin/frame-stereo on --format full
~/.local/bin/frame-stereo on --swap-eyes
~/.local/bin/frame-stereo off
~/.local/bin/frame-stereo status
~/.local/bin/frame-stereo list
```

Each eye receives its corresponding half of the source image. Half SBS uses 2× the original
texel aspect; Full SBS uses the original aspect. The default command-line format is half.
This can be tested with any 2D app, although actual stereoscopic depth requires an SBS source.

For native games, Gamescope's separate image layers must be combined before the split. The tool uses
`gamescopectl composite_force 1` when visible subviews are present, verifies that they disappear,
and applies the selected stereo aspect. This combination was visually confirmed
on the user's Frame. Applying stereo to the separate layers caused black gaps; omitting the
stretch after combining them left the image too narrow.

Steam Remote Play uses its own `steamlink_openvr-overlay` screen. It is detected automatically,
including when the launcher menu hides it, and does not require changing Gamescope composition.
PC-rendered VR streams and third-party streaming apps are not automatically targeted.

Forced composition is session-wide and may add GPU work. When this tool enables it, it records
ownership and disables it after the last saved screen in that SteamVR session is restored.
If no visible layers exist, the tool leaves the existing composition setting alone.
No startup service or automatic restart is installed.

The launcher selects the sole visible game screen. If opening the menu hides it, the sole
non-fallback game overlay can still be selected. Multiple candidates require an explicit key:

```sh
~/.local/bin/frame-stereo on --overlay valve.steam.desktopgame.413150
```

Errors from the launcher are sent through desktop notifications when `notify-send` is available.
Original stereo flags and aspect are stored under `$XDG_RUNTIME_DIR/frame-stereo/state.json`.
State is bound to the boot, SteamVR process start, overlay handle, and key. Repeated `on` calls
preserve the original and do not multiply the aspect again. Other overlay properties are preserved.

Overlay changes are checked for two seconds; API failures or resets trigger an attempted rollback.
Saved recovery state remains available after errors. Run `off --overlay KEY` after an interrupted
operation. Gamescope can recreate screens later; rerun the toggle when switching apps.
If stereo was enabled outside this tool without a saved original, `off` refuses to guess its original aspect.

## Installation and validation

The installer builds locally against the Frame's ARM64 OpenVR runtime and verifies the
installed helper matches the build. It downloads Valve's public OpenVR header pinned to
commit `0924064316de3effbcd1acf1e309182a2deb1c05` and checks its SHA-256 before compiling.
The downloaded header is a build dependency and is not tracked here; it is covered by
[Valve's OpenVR license](https://github.com/ValveSoftware/openvr/blob/0924064316de3effbcd1acf1e309182a2deb1c05/LICENSE).
Set `OPENVR_INCLUDE_DIR` or `OPENVR_RUNTIME_DIR` to use an existing SDK or alternate runtime.

Local checks: `python3 -m unittest discover -s tests -v`.
Tests cover screen filtering, restoration, repeat toggles, eye order, simulated runtime restart,
recovery state, and composition ownership. The helper was compiled and exercised on Frame;
installed binaries were compared with their build. The user confirmed the composed, stretched
view looks correct on 2026-10-05.
