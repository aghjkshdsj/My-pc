#!/usr/bin/env python3
"""Extend only the exact disposable graphics payload with a fresh image gate."""
import argparse
import gzip
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import tarfile
import uuid

from make_initramfs import record
from run_gpu_kernel_gate import validate as validate_kernel

PROJECT = pathlib.Path(__file__).resolve().parents[1]
PARENT_RUN = 37095653651
PARENT_SOURCE = '004853222a3b6fccc76277f9d669fdc2e42d56f1'
PARENT_FILES = {'Image': 'a8f995e831fcfe43807873c1579ab0f80658afb701b80b08047f00c29e1ad166',
                'initramfs.cpio.gz': '159084848d00a252299922628f933cd52dd777b5af93b9ed46340b4d960cdef1'}


def extend_newc(data, replacements, additions=('vk-image-gate', 'kms-format-control')):
    """Keep accepted raw records, never extract paths or follow archive symlinks."""
    assert len(data) < 128 * 1024 * 1024
    assert set(additions) <= {'vk-image-gate', 'kms-format-control', 'vk-frames-gate', 'release-channel-probe', 'vk-moving-gate', 'kms-atomic-gate'}
    position, names, output, inode = 0, set(), [], 20000
    remaining = dict(replacements)
    while True:
        start = position
        assert data[position:position + 6] == b'070701'
        fields_raw = data[position + 6:position + 110]
        assert len(fields_raw) == 104
        fields = [int(fields_raw[i:i + 8], 16) for i in range(0, 104, 8)]
        mode, length, name_length = fields[1], fields[6], fields[11]
        assert 1 < name_length < 4096 and length < 64 * 1024 * 1024
        name_raw = data[position + 110:position + 110 + name_length]
        assert len(name_raw) == name_length and name_raw[-1:] == b'\0' and b'\0' not in name_raw[:-1]
        name = name_raw[:-1].decode('utf-8')
        path = pathlib.PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and name not in names
        names.add(name)
        content_start = (position + 110 + name_length + 3) & ~3
        position = (content_start + length + 3) & ~3
        assert len(data[content_start:content_start + length]) == length and position <= len(data)
        if name == 'TRAILER!!!':
            assert length == 0 and not any(data[position:])
            break
        assert stat.S_IFMT(mode) in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK, stat.S_IFCHR)
        if name in remaining:
            replacement_mode, content = remaining.pop(name)
            assert stat.S_IFMT(mode) == stat.S_IFREG, 'Never replace a symlink/directory/device'
            output.append(record(name, replacement_mode, content, inode=inode))
            inode += 1
        else:
            output.append(data[start:position])
    for name, (mode, content) in remaining.items():
        assert name in additions and name not in names and stat.S_IFMT(mode) == stat.S_IFREG
        output.append(record(name, mode, content, inode=inode))
        inode += 1
    output.append(record('TRAILER!!!', 0, inode=inode))
    return b''.join(output)


def build(parent):
    output = PROJECT / 'out/guest-image-payload'
    assert not output.exists(), 'Fresh output required; preserve earlier payloads'
    output.mkdir()
    payload = output / 'payload'
    payload.mkdir()
    receipt = json.loads((parent / 'payload/payload-receipt.json').read_text())
    assert receipt['scope'] == 'linux-arm64-graphics-payload-missing-3d-boot-controls'
    assert receipt['source_commit'] == PARENT_SOURCE and int(receipt['workflow_run']) == PARENT_RUN
    with tarfile.open(parent / 'Guest-GPU-Payload.tar.gz') as archive:
        inputs = {name: archive.extractfile('payload/' + name).read() for name in PARENT_FILES}
    for name, data in inputs.items():
        assert hashlib.sha256(data).hexdigest() == PARENT_FILES[name]
        assert len(data) == receipt['files'][name]['bytes']
    binary = output / 'vk-image-gate'
    format_test = output / 'image-format-contract-test'
    subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I/usr/include/libdrm',
                    str(PROJECT / 'tests/GuestImageFormatTests.c'), '-o', str(format_test)], check=True)
    subprocess.run([str(format_test)], check=True)
    pixel_test = output / 'image-pixel-contract-test'
    subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(PROJECT / 'tests/ImagePixelContractTests.c'), '-o', str(pixel_test)], check=True)
    subprocess.run([str(pixel_test)], check=True)
    kms_binary = output / 'kms-format-control'
    subprocess.run(['gcc', '-O2', '-Wall', '-Wextra', '-Werror', '-I/usr/include/libdrm',
                    str(PROJECT / 'Guest/kms_format_probe.c'), '-ldrm', '-o', str(kms_binary)], check=True)
    command = ['gcc', '-O2', '-Wall', '-Wextra', '-Werror', '-DMPC_IMAGE_SCANOUT',
               '-DMPC_VK_DIAGNOSTIC_PREFIX="MPC_VK_IMAGE_RENDER "',
               '-I/usr/include/libdrm', str(PROJECT / 'Guest/vk_gate.c'), '-lvulkan', '-ldrm', '-o', str(binary)]
    subprocess.run(command, check=True)
    assert binary.read_bytes()[:4] == b'\x7fELF'
    assert 'AArch64' in subprocess.check_output(['readelf', '-h', str(binary)], text=True)
    dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
    dependencies = [line.split('[')[1].split(']')[0] for line in dynamic.splitlines() if '(NEEDED)' in line]
    required = {'libvulkan.so.1', 'libdrm.so.2', 'libc.so.6'}
    assert required <= set(dependencies) <= required | {'ld-linux-aarch64.so.1'}, dependencies
    assert any(name.endswith('/ld-linux-aarch64.so.1') for name in receipt['inventory'])
    init = (PROJECT / 'Guest/init-gpu-userspace').read_text()
    anchor = 'vk_status=$?\n'
    assert init.count(anchor) == 1
    init = init.replace(anchor, anchor + '''image_requested=0
for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in mpc_image=1) image_requested=1;; esac
done
case "$image_requested" in
1)
    export MPC_KMS_RUN="$nonce"
    /kms-format-control
    kms_status=$?
    /bin/busybox echo "MPC_KMS_FORMAT_CONTROL_EXIT=$kms_status"
    image_status=99
    case "$vk_status:$abi_status:$gpu_status" in
    0:0:0)
        export MPC_IMAGE_RUN="$nonce"
        /vk-image-gate /vertex.spv /fragment.spv
        image_status=$?
        ;;
    esac
    /bin/busybox echo "MPC_IMAGE_GUEST_EXIT=$image_status"
    ;;
esac
''')
    (output / 'init-image-userspace').write_text(init, encoding='utf-8')
    cpio = extend_newc(gzip.decompress(inputs['initramfs.cpio.gz']), {
        'init': (stat.S_IFREG | 0o755, init.encode()),
        'vk-image-gate': (stat.S_IFREG | 0o755, binary.read_bytes()),
        'kms-format-control': (stat.S_IFREG | 0o755, kms_binary.read_bytes())})
    (payload / 'Image').write_bytes(inputs['Image'])
    (payload / 'initramfs.cpio.gz').write_bytes(gzip.compress(cpio, mtime=0))
    cases = []
    for has_device in [True, False]:
        nonce = uuid.uuid4().hex
        command = ['qemu-system-aarch64', '-machine', 'virt', '-cpu', 'max', '-accel',
                   'tcg,thread=multi,split-wx=on,tb-size=32', '-smp', '2', '-m', '512', '-nodefaults',
                   '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-kernel', str(payload / 'Image'),
                   '-initrd', str(payload / 'initramfs.cpio.gz'), '-append',
                   'console=ttyAMA0 rdinit=/init panic=1 mpc_image=1 mpc_run=' + nonce, '-no-reboot']
        if has_device:
            command += ['-device', 'virtio-gpu-pci']
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        serial = result.stdout + result.stderr
        (payload / ('2d-image-control.log' if has_device else 'missing-image-control.log')).write_text(serial)
        print(serial)
        assert result.returncode == 0
        kernel = validate_kernel(serial, nonce, has_device)
        assert serial.splitlines().count('MPC_GPU_GUEST_EXIT=3') == 1
        assert serial.splitlines().count('MPC_IMAGE_GUEST_EXIT=99') == 1
        assert 'MPC_IMAGE_PRODUCER' not in serial and 'MPC_IMAGE_EXIT ' not in serial
        kms_rows = [json.loads(line.removeprefix('MPC_KMS_FORMAT_CONTROL ')) for line in serial.splitlines()
                    if line.startswith('MPC_KMS_FORMAT_CONTROL ')]
        assert len(kms_rows) == (1 if has_device else 0)
        assert serial.splitlines().count('MPC_KMS_FORMAT_CONTROL_EXIT=' + ('0' if has_device else '3')) == 1
        if has_device:
            assert kms_rows[0] == dict(schema=1, run=nonce, abgr_errno=2, xrgb_framebuffer_created=True,
                framebuffer_released=True, scope='linux-kernel-cpu-allocation-format-control',
                gpu_rendering_verified=False, host_memory_import_verified=False, presentation_verified=False)
        cases.append({'run': nonce, 'has_2d_device': has_device, 'engine_exit': result.returncode,
                      'missing_3d_rejected_before_image': True, 'kms_format_control': kms_rows, **kernel})
    shaders = output / 'shaders'
    shaders.mkdir()
    subprocess.run(['glslangValidator', '-V', str(PROJECT / 'Guest/vk_gate.vert'), '-o', str(shaders / 'vertex.spv')], check=True)
    subprocess.run(['glslangValidator', '-V', str(PROJECT / 'Guest/vk_gate.frag'), '-o', str(shaders / 'fragment.spv')], check=True)
    manifests = list(pathlib.Path('/usr/share/vulkan/icd.d').glob('lvp*.json'))
    assert len(manifests) == 1, 'Need one actual installed Lavapipe control ICD'
    lvp = manifests[0]
    assert 'lvp' in json.loads(lvp.read_text())['ICD']['library_path']
    env = dict(os.environ, VK_DRIVER_FILES=str(lvp), VK_ICD_FILENAMES=str(lvp), MPC_IMAGE_RUN=uuid.uuid4().hex)
    negative = subprocess.run([str(binary), str(shaders / 'vertex.spv'), str(shaders / 'fragment.spv')],
                              env=env, capture_output=True, text=True, timeout=60)
    (output / 'software-image-rejected.log').write_text(negative.stdout + negative.stderr)
    print(json.dumps({'scope': 'hosted-software-image-negative-control', 'icd': str(lvp),
                      'returncode': negative.returncode, 'stdout': negative.stdout, 'stderr': negative.stderr}))
    assert negative.returncode == 20 and 'MPC_VK_REJECTED software_renderer=' in negative.stdout
    assert 'MPC_IMAGE_PRODUCER' not in negative.stdout
    source_files = {name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in [
        'Guest/vk_gate.c', 'Guest/image_scanout.h', 'Guest/image_export_contract.h', 'Guest/image_framebuffer.h',
        'Guest/kms_format_probe.c', 'Engine/ImagePixelContract.h',
        'tests/GuestImageFormatTests.c', 'tests/ImagePixelContractTests.c', 'Guest/renderer_classification.h',
        'tools/build_guest_image_payload.py', 'tools/make_initramfs.py',
        'tools/run_gpu_kernel_gate.py', 'tools/run_kernel_gate.py', 'Guest/init-gpu-userspace']}
    for name, content in [('init', init.encode()), ('vk-image-gate', binary.read_bytes()),
                          ('kms-format-control', kms_binary.read_bytes())]:
        receipt['inventory'][name] = {'mode': stat.S_IFREG | 0o755, 'bytes': len(content),
                                    'sha256': hashlib.sha256(content).hexdigest()}
    receipt.update(scope='linux-arm64-graphics-payload-image-export-boot-controls',
                   source_commit=os.environ['GITHUB_SHA'], workflow_run=os.environ['GITHUB_RUN_ID'],
                   parent_graphics_source=PARENT_SOURCE, parent_graphics_run=PARENT_RUN,
                   parent_graphics_files=PARENT_FILES, cases=cases, image_gate_compiled=True,
                   image_export_verified=False, host_memory_import_verified=False,
                   export_tiling='drm-format-modifier', required_drm_modifier=0,
                   native_format_contract_tests_passed=True,
                   native_pixel_contract_tests_passed=True, kms_kernel_format_control_passed=True,
                   export_vulkan_format=44, scanout_drm_fourcc=875713112,
                   scanout_virtio_format=2, native_metal_pixel_format=80, channel_order='bgra',
                   software_image_rejected=True, image_gate_dependencies=dependencies,
                   software_control_icd_sha256=hashlib.sha256(lvp.read_bytes()).hexdigest(),
                   image_source_files=source_files,
                   files={n: {'bytes': (payload / n).stat().st_size,
                              'sha256': hashlib.sha256((payload / n).read_bytes()).hexdigest()} for n in PARENT_FILES})
    (payload / 'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    with tarfile.open(output / 'Guest-GPU-Payload.tar.gz', 'w:gz') as archive:
        archive.add(payload, arcname='payload')
    with tarfile.open(output / 'Guest-GPU-Corresponding-Source.tar.gz', 'w:gz') as archive:
        archive.add(parent / 'Guest-GPU-Corresponding-Source.tar.gz', arcname='Parent-Guest-GPU-Corresponding-Source.tar.gz')
        for name in source_files:
            archive.add(PROJECT / name, arcname=name)
        archive.add(output / 'init-image-userspace', arcname='init-image-userspace')
        archive.add(payload / 'payload-receipt.json', arcname='payload-receipt.json')
        archive.add(PROJECT.parent / '.github/workflows/steamos-guest-image-payload.yml', arcname='steamos-guest-image-payload.yml')
        for path in pathlib.Path('/usr/include/libdrm').glob('*.h'):
            archive.add(path, arcname='build-headers/libdrm/' + path.name)
        for path in pathlib.Path('/usr/include/vulkan').glob('*.h'):
            archive.add(path, arcname='build-headers/vulkan/' + path.name)
        for name in ['libdrm-dev', 'libvulkan-dev']:
            archive.add('/usr/share/doc/' + name + '/copyright', arcname='build-headers/' + name + '-copyright')
    print(json.dumps({'scope': receipt['scope'], 'files': receipt['files'], 'phone_tested': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=pathlib.Path)
    build(parser.parse_args().parent.resolve())
