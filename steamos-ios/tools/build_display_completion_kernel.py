#!/usr/bin/env python3
"""Compile an isolated opt-in kernel fork; retain original kernel/build outputs."""
import pathlib
import shutil
import subprocess
import tarfile
from patch_linux_display_completion import once

PROJECT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / 'out/source-display-completion-kernel'


def build():
    if OUTPUT.exists():
        raise ValueError('Fresh output required')
    recipe = (PROJECT / 'tools/build_gpu_guest_gate.sh').read_text(encoding='utf-8')
    recipe = once(recipe, 'output="$project/out/source-gpu-guest"',
                  'output="$project/out/source-display-completion-kernel"')
    recipe = once(recipe, 'make ARCH=arm64 tinyconfig',
                  'python3 "$project/tools/patch_linux_display_completion.py" "$PWD" "$output/display-patch"\n'
                  'make ARCH=arm64 tinyconfig')
    generated = PROJECT / 'out/build-display-completion-kernel.sh'
    generated.parent.mkdir(exist_ok=True)
    generated.write_text(recipe, encoding='utf-8', newline='\n')
    subprocess.run(['bash', str(generated)], check=True)
    corresponding = OUTPUT / 'corresponding-source'
    shutil.copytree(OUTPUT / 'display-patch', corresponding / 'display-patch')
    for name in ('tools/build_display_completion_kernel.py', 'tools/patch_linux_display_completion.py'):
        shutil.copy2(PROJECT / name, corresponding / name)
    shutil.copy2(generated, corresponding / 'build-display-completion-kernel.sh')
    shutil.copy2(PROJECT.parent / '.github/workflows/steamos-display-completion-control.yml', corresponding)
    with tarfile.open(OUTPUT / 'Display-Completion-Kernel-Corresponding-Source.tar.gz', 'w:gz') as archive:
        archive.add(corresponding, arcname='corresponding-source')


if __name__ == '__main__':
    build()
