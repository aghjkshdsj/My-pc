#!/bin/bash
# Full ARM64 Linux client, following winlator-contents' steamdeck-steam route.
# CPU affinity and graphics settings are specific to this Linux VM on iPhone.
set -euo pipefail
steam_root="${XDG_DATA_HOME:-$HOME/.local/share}/Steam"
mkdir -p "$steam_root" "$HOME/.steam"
exec 9>"$HOME/.steam/my-pc-bootstrap.lock"
flock -n 9 || { echo 'Steam is already running.'; exit 1; }
if [ ! -s "$steam_root/arm64-verification.json" ] || [ ! -x "$steam_root/steamrtarm64/steam" ]; then
    echo 'Downloading the full ARM64 Steam client from Valve. Keep My-pc open.'
    python3 /usr/local/lib/my-pc/steam-arm-fetch.py --destination "$steam_root"
fi
# Valve's ARM helper currently pins CPUs 2-6, absent in our two-core VM.
# Remove only that known affinity prefix. Leave the rest of the wrapper intact.
prepare_helper() {
python3 - "$steam_root/steamrtarm64/steamwebhelper.sh" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
content = path.read_text()
content = content.replace('exec taskset 0x7c ', 'exec ')
path.write_text(content)
path.chmod(0o755)
PY
}
ln -sfn "$steam_root" "$HOME/.steam/steam"
ln -sfn "$steam_root" "$HOME/.steam/root"
export STEAM_RUNTIME=1 SDL_VIDEO_X11_DGAMOUSE=0
export LD_LIBRARY_PATH="$steam_root/steamrtarm64:$steam_root/steamrtarm64/panorama${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Bring-up renderer: software Mesa. Hardware acceleration is a separate gate.
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
cd "$steam_root"
restarts=0
while :; do
    prepare_helper
    status=0
    "$steam_root/steamrtarm64/steam" -clientbeta publicbeta \
        -no-cef-sandbox -cef-disable-gpu -cef-ozone-platform=x11 "$@" || status=$?
    echo "ARM64 Steam exited with status $status"
    # Steam's normal updater returns 42 to ask its parent launcher to restart.
    # The update also restores its helper, so reapply the VM affinity fix.
    [ "$status" = 42 ] || exit "$status"
    restarts=$((restarts + 1))
    [ "$restarts" -lt 5 ] || { echo 'Steam requested too many update restarts.'; exit 1; }
done
