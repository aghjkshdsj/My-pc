#!/usr/bin/env python3
"""Apply the native host overlay to an exact, checked-out source revision."""
from pathlib import Path
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys

DRIVER = Path(__file__).resolve().parent
LOCK = json.loads((DRIVER / 'source-lock.json').read_text())


def git(directory, *args):
    return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()


def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f'{label}: expected exactly one source marker')
    return text.replace(before, after, 1)


def prepare(runtime):
    runtime = runtime.resolve()
    expected = (DRIVER / 'runtime').resolve()
    if runtime != expected or runtime.is_symlink():
        raise ValueError('Only native-ios/runtime may be prepared')
    if git(runtime, 'rev-parse', 'HEAD') != LOCK['source']['commit']:
        raise ValueError('Source revision does not match the lock')
    for path, sha in LOCK['submodules'].items():
        if git(runtime / path, 'rev-parse', 'HEAD') != sha:
            raise ValueError(f'{path}: source revision does not match the lock')

    stamp = runtime / '.mypc-native-overlay.json'
    if stamp.exists():
        old = json.loads(stamp.read_text())
        if old != LOCK:
            raise ValueError('Overlay source lock changed; use a fresh checkout')
        # The only mutable app overlay is reapplied on every invocation.
        shutil.copyfile(DRIVER / 'NativeApp.swift', runtime / 'app/Madeira/MadeiraApp.swift')
        return

    # Read and preflight every replacement before changing the checkout.
    app = runtime / 'app/Madeira'
    library_path = app / 'Library.swift'
    library = library_path.read_text()
    library = replace_once(library,
        '            onboarding.presentIfNeeded()\n',
        '            NativePerformance.libraryVisible()\n            onboarding.presentIfNeeded()\n',
        'library appearance')

    # The reference server builder updates an unavailable prebuilt archive.
    # Compile every server object instead, retaining all current patched inputs
    # and the reference's complete collision-renaming pass.
    server_path = runtime / 'build/wineserver/build.sh'
    server = server_path.read_text()
    start = server.index('# Copy the base library if we don\'t have one yet')
    end = server.index('CC_FLAGS=(', start)
    server = server[:start] + 'rm -f "$OBJ_DIR"/*.o\n\n' + server[end:]
    start = server.index('case "${1:-all}" in')
    end = server.index('echo "=== Renaming colliding symbols in every .o (objcopy sweep) ==="', start)
    rebuilt = '''echo "=== Building every wineserver object from source ==="
for source in "$WINE_SRC"/server/*.c; do
    name=$(basename "$source" .c)
    for entry in "${PATCHED_FILES[@]}"; do
        IFS=: read -r patched_name patched_source old_object <<< "$entry"
        if [ "$old_object" = "$name.o" ]; then
            case "$patched_source" in
                /*) source="$patched_source" ;;
                *) source="$BUILD_DIR/$patched_source" ;;
            esac
            break
        fi
    done
    compile_one "$source" "$name"
done
compile_one "$BUILD_DIR/wine_log_ios.c" wine_log_ios
rm -f "$OBJ_DIR/libwineserver.a"
ar rcs "$OBJ_DIR/libwineserver.a" "$OBJ_DIR"/*.o

'''
    server = server[:start] + rebuilt + server[end:]

    project_path = runtime / 'app/Madeira.xcodeproj/project.pbxproj'
    project = project_path.read_text()
    if project.count('com.willfaust.madeora') != 2:
        raise ValueError('Unexpected native Xcode bundle identity')
    project = project.replace('com.willfaust.madeora', LOCK['bundle_id'])
    project = project.replace('IPHONEOS_DEPLOYMENT_TARGET = 17.0;',
                              f'IPHONEOS_DEPLOYMENT_TARGET = {LOCK["minimum_ios"]};')

    plist_path = app / 'Info.plist'
    info = plistlib.loads(plist_path.read_bytes())
    info['CFBundleDisplayName'] = LOCK['display_name']
    info['MyPCNativeSourceCommit'] = LOCK['source']['commit']
    info['MyPCNativeBackend'] = 'native-ios-fex-wine-metal'
    info['SomethingPCBuildCommit'] = os.environ.get('GITHUB_SHA', 'local')
    info['CFBundleVersion'] = str(3_000_000 + int(os.environ.get('GITHUB_RUN_NUMBER', '0')))
    info['MadeiraBuild'] = 'My-pc Native ' + info['CFBundleVersion']

    # The native target must never pick up the older project's Linux sources.
    for path in app.rglob('*'):
        if path.is_file() and re.search(r'(LinuxVM|QEMU|virgl)', path.name, re.I):
            raise ValueError(f'Unexpected VM source in native target: {path.name}')

    shutil.copyfile(DRIVER / 'NativeApp.swift', app / 'MadeiraApp.swift')
    library_path.write_text(library)
    server_path.write_text(server)
    project_path.write_text(project)
    plist_path.write_bytes(plistlib.dumps(info, sort_keys=False))
    stamp.write_text(json.dumps(LOCK, indent=2) + '\n')


if __name__ == '__main__':
    prepare(Path(sys.argv[1]))
    print('Prepared locked native iOS source; no Linux runtime included')
