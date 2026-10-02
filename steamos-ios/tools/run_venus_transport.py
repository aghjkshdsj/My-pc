#!/usr/bin/env python3
"""Real hosted Venus vtest serialization check; no phone/Metal/virtio boot claim."""
import hashlib
import json
import os
import pathlib
import subprocess
import time

from verify_graphics_diagnostic import validate

REVISION = '5d26f605f50f8e22002ec6db5fb775e1992d4e96'
PROJECT = pathlib.Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    output = PROJECT / 'out/venus-transport'
    assert not output.exists(), 'A new hosted test directory is required'
    output.mkdir(parents=True)
    source = output / 'virglrenderer'; source.mkdir()
    run('git', '-C', str(source), 'init', '-q')
    run('git', '-C', str(source), 'remote', 'add', 'origin', 'https://github.com/utmapp/virglrenderer.git')
    run('git', '-C', str(source), 'fetch', '--depth=1', 'origin', REVISION)
    run('git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD')
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == REVISION
    run('meson', 'setup', str(source / 'build'), str(source), '--buildtype=release',
        '-Dvenus=true', '-Dneptune=false', '-Dvtest=true', '-Dtests=false', '-Dplatforms=[]',
        '-Drender-server-mode=thread', '-Drender-server-worker=thread')
    run('meson', 'compile', '-C', str(source / 'build'), '-j', '3')
    run('git', '-C', str(source), 'archive', '--format=tar', '-o', str(output / 'virglrenderer-source.tar'), 'HEAD')
    executable = output / 'vk-gate'
    run('gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(PROJECT / 'Guest/vk_gate.c'),
        '-lvulkan', '-o', str(executable))
    for stage in ['vert', 'frag']:
        target = output / ('vertex.spv' if stage == 'vert' else 'fragment.spv')
        run('glslangValidator', '-V', '--target-env', 'vulkan1.1', str(PROJECT / ('Guest/vk_gate.' + stage)), '-o', str(target))
        run('spirv-val', '--target-env', 'vulkan1.1', str(target))
    icd_dir = pathlib.Path('/usr/share/vulkan/icd.d')
    lvp = list(icd_dir.glob('lvp_icd*.json')); venus = list(icd_dir.glob('virtio_icd*.json'))
    assert len(lvp) == len(venus) == 1, (lvp, venus)
    socket = pathlib.Path('/tmp/.virgl_test')
    assert not socket.exists(), 'Never replace an existing server socket'
    server_environment = dict(os.environ, VK_DRIVER_FILES=str(lvp[0]))
    server_environment.pop('VN_DEBUG', None)
    client_environment = dict(os.environ, VK_DRIVER_FILES=str(venus[0]), VN_DEBUG='vtest')
    server_binary = source / 'build/vtest/virgl_test_server'
    with (output / 'server.log').open('w') as server_log:
        server = subprocess.Popen([str(server_binary), '--venus', '--no-fork'],
                                  env=server_environment, stdout=server_log, stderr=server_log)
        try:
            deadline = time.monotonic() + 20
            while not socket.exists():
                assert server.poll() is None, 'Venus renderer terminated before opening its socket'
                assert time.monotonic() < deadline, 'Venus renderer socket timeout'
                time.sleep(0.05)
            command = [str(executable), str(output / 'vertex.spv'), str(output / 'fragment.spv')]
            with (output / 'diagnostic.log').open('w') as log, (output / 'validation.log').open('w') as errors:
                subprocess.run(command + ['--allow-software-diagnostic', '--require-validation'],
                               env=client_environment, stdout=log, stderr=errors, timeout=90, check=True)
            with (output / 'rejection.log').open('w') as log, (output / 'rejection-validation.log').open('w') as errors:
                rejected = subprocess.run(command + ['--require-validation'], env=client_environment,
                                          stdout=log, stderr=errors, timeout=30)
            lines = (output / 'diagnostic.log').read_text().splitlines()
            rows = [json.loads(x.removeprefix('MPC_VK_DIAGNOSTIC ')) for x in lines if x.startswith('MPC_VK_DIAGNOSTIC ')]
            assert len(rows) == 1
            expected = validate(rows[0], rejected.returncode, (output / 'rejection.log').read_text())
        finally:
            if server.poll() is None:
                server.terminate()
                try: server.wait(timeout=5)
                except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
    files = [output / name for name in ['vk-gate', 'vertex.spv', 'fragment.spv', 'diagnostic.log', 'validation.log',
                                        'rejection.log', 'rejection-validation.log', 'server.log', 'virglrenderer-source.tar']]
    files += [server_binary, lvp[0], venus[0]]
    receipt = {'scope': 'hosted-linux-arm64-venus-vtest-software-diagnostic',
               'transport': 'Mesa Venus vtest -> pinned virglrenderer -> lavapipe',
               'renderer_commit': REVISION, 'source_commit': os.environ.get('GITHUB_SHA'),
               'workflow_run': os.environ.get('GITHUB_RUN_ID'), 'diagnostic': rows[0],
               'expected_channel_sum': expected, 'software_rejection_exit': rejected.returncode,
               'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files},
               'phone_tested': False, 'virtio_guest_kernel_tested': False, 'darwin_memory_bridge_tested': False,
               'metal_verified': False, 'presentation_verified': False, 'gameplay_verified': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
