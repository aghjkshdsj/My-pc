#!/usr/bin/env python3
"""Package linked frameworks plus ANGLE providers loaded dynamically by epoxy."""
import pathlib
import plistlib
import shutil
import subprocess

ANGLE_PROVIDERS = {
    'EGL.framework': {'_eglGetProcAddress', '_eglGetDisplay', '_eglInitialize'},
    'GLESv2.framework': {'_glGetString', '_glReadPixels', '_glClear'},
}


def copy_frameworks(source, destination, *, metal, platform):
    source, destination = pathlib.Path(source), pathlib.Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    pending = ['qemu-aarch64-softmmu.framework']
    if metal:
        # These are dlopen() providers, absent from QEMU's otool -L closure.
        pending.extend(ANGLE_PROVIDERS)
    done = set()
    while pending:
        name = pending.pop()
        if name in done:
            continue
        framework = source / name
        # macOS versioned frameworks put their plist in Resources; iPhone
        # frameworks are flat. Keep the actual bundle layout when copying.
        plist = framework / 'Info.plist'
        if platform == 'MACOS' and not plist.is_file():
            plist = framework / 'Resources/Info.plist'
        info = plistlib.loads(plist.read_bytes())
        executable = info['CFBundleExecutable']
        if pathlib.Path(executable).name != executable:
            raise ValueError(f'Invalid framework executable: {name}')
        binary = framework / executable
        subprocess.run(['xcrun', 'lipo', str(binary), '-verify_arch', 'arm64'], check=True)
        build = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
        if not any(line.strip() == 'platform ' + platform for line in build.splitlines()):
            raise ValueError(f'Framework has the wrong Apple platform: {name}')
        dependencies = subprocess.check_output(['otool', '-L', str(binary)], text=True)
        for line in dependencies.splitlines()[1:]:
            dependency = line.strip().split(' (', 1)[0]
            if dependency.startswith(('/usr/lib/', '/System/Library/')):
                continue
            if dependency.startswith('@rpath/') and '.framework/' in dependency:
                linked = dependency.split('/')[1]
                if not (source / linked).is_dir():
                    raise ValueError(f'Missing dependency: {dependency}')
                pending.append(linked)
            else:
                raise ValueError(f'Unbundled host library: {dependency}')
        if name in ANGLE_PROVIDERS:
            exports = subprocess.check_output(['xcrun', 'nm', '-gU', str(binary)], text=True)
            symbols = {line.split()[-1] for line in exports.splitlines() if line.split()}
            missing = ANGLE_PROVIDERS[name] - symbols
            if missing:
                raise ValueError(f'Missing ANGLE exports in {name}: {sorted(missing)}')
        shutil.copytree(framework, destination / name, symlinks=True, dirs_exist_ok=True)
        if platform == 'IOS':
            subprocess.run(['codesign', '--remove-signature',
                            str(destination / name / executable)], check=True)
        done.add(name)
    return sorted(done)
