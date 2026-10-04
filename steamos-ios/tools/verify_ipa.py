#!/usr/bin/env python3
"""Verify exact identity and ARM64 iOS Mach-O; explicitly mark probe scope."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import struct
import zipfile

def macho_platform(binary, filetype):
    magic, cpu, subtype, actual_type, ncmds, sizeofcmds, flags, reserved = struct.unpack_from('<8I', binary)
    assert magic == 0xfeedfacf and cpu == 0x100000c and actual_type == filetype, 'Expected ARM64 Mach-O kind'
    assert 32 + sizeofcmds <= len(binary) and ncmds <= 1024
    offset, ios = 32, False
    imports = []
    for _ in range(ncmds):
        command, size = struct.unpack_from('<II', binary, offset)
        assert size >= 8 and offset + size <= 32 + sizeofcmds
        if command == 0x32:
            ios = struct.unpack_from('<I', binary, offset + 8)[0] == 2
        if command in [0xc, 0x80000018, 0x8000001f]:
            name_offset = struct.unpack_from('<I', binary, offset + 8)[0]
            assert 24 <= name_offset < size
            imports.append(binary[offset + name_offset:offset + size].split(b'\0', 1)[0].decode())
        offset += size
    assert ios, 'Mach-O must target physical iOS'
    return imports

def macho_text(binary):
    macho_platform(binary, 6)
    ncmds, sizeofcmds = struct.unpack_from('<II', binary, 16)
    cursor, found = 32, []
    for _ in range(ncmds):
        command, size = struct.unpack_from('<II', binary, cursor)
        if command == 0x19:
            assert size >= 72
            count = struct.unpack_from('<I', binary, cursor + 64)[0]
            assert count <= 1024 and 72 + count * 80 <= size
            for index in range(count):
                section = cursor + 72 + index * 80
                name, segment = struct.unpack_from('<16s16s', binary, section)
                if name.rstrip(b'\0') != b'__text' or segment.rstrip(b'\0') != b'__TEXT': continue
                length = struct.unpack_from('<Q', binary, section + 40)[0]
                offset = struct.unpack_from('<I', binary, section + 48)[0]
                assert length > 0 and offset >= 32 + sizeofcmds and offset + length <= len(binary)
                found.append({'bytes': length, 'sha256': hashlib.sha256(binary[offset:offset + length]).hexdigest()})
        cursor += size
    assert len(found) == 1, 'Expected one executable text section'
    return found[0]


def verify(path, commit, linux_gate=False, expected_build=None, native_vulkan=False, guest_gpu=False):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, 'IPA ZIP CRC failed'
        prefix = 'Payload/MyPCSteamOSProbe.app/'
        info = plistlib.loads(z.read(prefix + 'Info.plist'))
        assert info['CFBundleIdentifier'] == 'com.aghjkshdsj.mypc.steamos.probe'
        assert info['MPCSourceCommit'] == commit
        if expected_build is not None:
            assert info['CFBundleVersion'] == expected_build, 'IPA build differs from the intended prerelease'
        binary = z.read(prefix + info['CFBundleExecutable'])
        macho_platform(binary, 2)
        assert not any('Madeira' in p or 'NativeSteam' in p for p in z.namelist()), 'Old app contamination'
        engine = prefix + 'Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu'
        frameworks = []
        if linux_gate:
            assert engine in z.namelist(), 'Missing Linux engine'
            for name in z.namelist():
                if not name.startswith(prefix + 'Frameworks/') or not name.endswith('.framework/Info.plist'): continue
                metadata = plistlib.loads(z.read(name))
                executable = name.rsplit('/', 1)[0] + '/' + metadata['CFBundleExecutable']
                imports = macho_platform(z.read(executable), 6)
                assert not any(any(word in dep for word in ['IOKit', 'Hypervisor', '/PrivateFrameworks/']) for dep in imports)
                for dependency in imports:
                    if dependency.startswith('/usr/lib/') or dependency.startswith('/System/Library/'): continue
                    assert dependency.startswith('@rpath/') and 'Hypervisor' not in dependency, dependency
                    assert prefix + 'Frameworks/' + dependency[len('@rpath/'):] in z.namelist(), dependency
                frameworks.append(executable)
            payload = prefix + 'LinuxGate/'
            receipt = json.loads(z.read(payload + 'payload-receipt.json'))
            assert receipt['kind'] == 'disposable-linux-abi-gate' and receipt['steamos'] is False
            for name in ['Image', 'initramfs.cpio.gz']:
                data = z.read(payload + name)
                assert len(data) == receipt['files'][name]['bytes']
                assert hashlib.sha256(data).hexdigest() == receipt['files'][name]['sha256']
            assert z.read(payload + 'Image')[56:60] == b'ARMd'
        else:
            assert engine not in z.namelist(), 'Engine-bearing IPA needs explicit Linux gate verification'
        if native_vulkan:
            from bundle_native_vulkan import BINARY_SHA, SHADERS, TRACE_BINARY_SHA, TRACE_RUN, TRACE_RECIPE_COMMIT, TRACE_SOURCE_SHA
            assert b'Missing Vulkan export:' in binary, 'Native draw adapter was not compiled with Vulkan headers'
            vk = prefix + 'NativeVulkan/'
            inputs = json.loads(z.read(vk + 'payload-receipt.json'))
            assert inputs['scope'] == 'bundled-native-ios-vulkan-diagnostic'
            observer = info['CFBundleVersion'] in ['4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']
            if info['CFBundleVersion'] in ['4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert b'capture_limit_bytes' in binary, 'Structured recovery export limit was not compiled'
            assert inputs['engine_run'] == (TRACE_RUN if observer else 37056046870)
            molten = z.read(prefix + 'Frameworks/MoltenVK.framework/MoltenVK')
            expected_molten = TRACE_BINARY_SHA if observer else BINARY_SHA
            assert hashlib.sha256(molten).hexdigest() == expected_molten
            assert not any('IOKit' in x for x in macho_platform(molten, 6))
            for name, sha in SHADERS.items():
                assert hashlib.sha256(z.read(vk + name)).hexdigest() == sha
                assert len(z.read(vk + name)) == inputs['files'][name]['bytes']
            assert inputs['files']['MoltenVK']['sha256'] == expected_molten
            assert inputs['engine_text_section'] == macho_text(molten)
            if observer:
                assert inputs['engine_recipe_commit'] == TRACE_RECIPE_COMMIT and inputs['source_archive_sha256'] == TRACE_SOURCE_SHA
                assert b'_mpc_mvk_configure_guest_trace' in molten
                native_receipt = inputs['guest_metal_trace_engine_receipt']
                assert native_receipt['scope'] == 'source-built-native-ios-moltenvk-guest-metal-observer-compile-only'
                assert native_receipt['physical_ios_macho'] is True and native_receipt['phone_tested'] is False
                assert native_receipt['binary_sha256'] == TRACE_BINARY_SHA
                assert native_receipt['source_commit'] == TRACE_RECIPE_COMMIT and int(native_receipt['workflow_run']) == TRACE_RUN
                assert native_receipt['guest_metal_trace_export_compiled'] is True
                trace = native_receipt['guest_metal_trace_observer']
                assert trace['abi'] == 1 and trace['actual_command_submission_site'] is True
                assert trace['native_adapter_fixtures_passed'] is True
                for field in ['adds_gpu_work', 'changes_submission_result', 'success_override', 'phone_tested',
                              'metal_execution_verified', 'host_memory_import_verified', 'presentation_verified']:
                    assert trace[field] is False
                for marker in [b'mpc_mvk_configure_guest_trace', b'native-moltenvk-guest-command-completion',
                               b'linux-guest-metal-observer-configured', b'linux-guest-metal-completion-checked']:
                    assert marker in binary
        if guest_gpu:
            from bundle_guest_gpu import ENGINE_PINS, GUEST_PINS, closure, hashed
            assert linux_gate and native_vulkan and info['CFBundleVersion'] in ENGINE_PINS
            engine_run, engine_source = ENGINE_PINS[info['CFBundleVersion']]
            guest_run, guest_source = GUEST_PINS[info['CFBundleVersion']]
            for marker in [b'virtio-gpu-gl-pci,blob=on,venus=on,hostmem=128M', b'egl-headless,gl=es',
                           b'MPC_GPU_GUEST_RUN=', b'tcg,thread=multi,split-wx=on,tb-size=32']:
                assert marker in binary, 'Required guest GPU/JIT adapter was not compiled'
            gpu = prefix + 'LinuxGuestGPU/'
            bundled = json.loads(z.read(gpu + 'engine-bundle.json'))
            assert bundled['scope'] == 'bundled-physical-ios-linux-guest-gpu-gate'
            assert bundled['engine_run'] == engine_run and bundled['engine_source'] == engine_source
            assert bundled['guest_run'] == guest_run and bundled['guest_source'] == guest_source
            assert bundled['hardware_virtualization'] is False and bundled['root_gles_version_requested'] == 3
            original = bundled['engine_receipt']
            if info['CFBundleVersion'] in ['4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert bundled['guest_metal_trace_engine_receipt'] == inputs['guest_metal_trace_engine_receipt']
            if info['CFBundleVersion'] in ['4000012', '4000013', '4000014', '4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert b'mpc_qemu_register_egl_headless' in binary
                assert b'_mpc_qemu_register_egl_headless' in z.read(engine)
                assert bundled['display_backend_compiled'] is True and bundled['display_registration_preflight_required'] is True
                for field in ['pixman_enabled', 'egl_headless_builtin_compiled', 'egl_headless_registration_export']:
                    assert original['display_backend_build_audit'][field] is True
            if info['CFBundleVersion'] in ['4000013', '4000014', '4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert b'MPC_GPU_CONTEXT_CREATE' in z.read(engine)
                assert b'output-flush-failed' in binary and b'tail_truncated' in binary
                assert b'guest_errors' in binary
                renderer = z.read(prefix + 'Frameworks/virglrenderer.1.framework/virglrenderer.1')
                for marker in [b'MPC_GPU_ALLOC_FAIL', b'MPC_GPU_SHMEM_FAIL', b'MPC_GPU_BLOB_FAIL']:
                    assert marker in renderer
                assert original['adapter']['context_create_result_checked'] is True
                diagnostics = original['graphics_dependency']['failure_diagnostics']
                assert diagnostics['failure_errno_and_stage_compiled'] is True
                assert diagnostics['allocator_policy_changed'] is False and diagnostics['success_override'] is False
            if info['CFBundleVersion'] in ['4000014', '4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert b'linux-private-file-directory-prepared' in binary and b'MPC_GPU_SHM_DIR' in binary
                renderer = z.read(prefix + 'Frameworks/virglrenderer.1.framework/virglrenderer.1')
                for marker in [b'MPC_GPU_PRIVATE_FILE_OPENED', b'MPC_GPU_PRIVATE_FILE_FAIL', b'MPC_GPU_SHM_DIR']:
                    assert marker in renderer
                private_file = original['graphics_dependency']['private_file_backing']
                for field in ['allocator_policy_changed', 'explicit_app_private_directory_required',
                              'atomic_exclusive_create', 'mode_0600', 'unlink_before_mapping',
                              'close_on_exec', 'hosted_native_tests_passed']:
                    assert private_file[field] is True
                assert private_file['phone_tested'] is False and private_file['success_override'] is False
                assert private_file['host_memory_import_verified'] is False
            expected = closure(original) | {'MoltenVK.framework/MoltenVK'}
            assert set(bundled['engine_text_sections']) == expected
            for relative in expected:
                data = z.read(prefix + 'Frameworks/' + relative)
                assert macho_text(data) == bundled['engine_text_sections'][relative]
                if not relative.startswith('MoltenVK.'):
                    hashed(data, original['files']['sysroot-iOS-arm64/Frameworks/' + relative])
            payload = json.loads(z.read(gpu + 'payload-receipt.json'))
            assert payload['scope'] == ('linux-arm64-graphics-payload-eight-frame-boot-controls' if info['CFBundleVersion'] == '4000023' else 'linux-arm64-graphics-payload-image-export-boot-controls' if info['CFBundleVersion'] in ('4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023') else 'linux-arm64-graphics-payload-missing-3d-boot-controls')
            if info['CFBundleVersion'] in ('4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023'):
                assert original['native_scanout_adapter_export'] is True
                assert original['native_scanout_adapter']['abi'] == 1
                assert original['native_scanout_adapter']['phone_tested'] is False
                assert b'_mpc_qemu_configure_native_scanout' in z.read(engine)
                for marker in [b'mpc_qemu_configure_native_scanout', b'linux-native-image-adapter-configured', b'linux-native-import-before-consumer', b'MPC_IMAGE_PRODUCER ', b'MPC_IMAGE_EXIT ', b'mpc_image=1']:
                    assert marker in binary, 'Required image adapter was not compiled'
                assert payload['image_gate_compiled'] is True and payload['software_image_rejected'] is True
                assert payload['image_export_verified'] is False and payload['host_memory_import_verified'] is False
            if info['CFBundleVersion'] in ('4000018', '4000019', '4000020', '4000021', '4000022', '4000023'):
                assert payload['export_tiling'] == 'drm-format-modifier' and payload['required_drm_modifier'] == 0
                assert payload['native_format_contract_tests_passed'] is True
                assert 'Guest/image_export_contract.h' in payload['image_source_files']
            if info['CFBundleVersion'] in ('4000019', '4000020', '4000021', '4000022', '4000023'):
                expected_formats = dict(export_vulkan_format=44, scanout_drm_fourcc=875713112,
                    scanout_virtio_format=2, native_metal_pixel_format=80, channel_order='bgra')
                assert all(type(payload.get(k)) is type(v) and payload[k] == v for k,v in expected_formats.items())
                assert payload['native_pixel_contract_tests_passed'] is True and payload['kms_kernel_format_control_passed'] is True
                assert payload['cases'][0]['kms_format_control'][0]['xrgb_framebuffer_created'] is True
                assert payload['cases'][0]['kms_format_control'][0]['host_memory_import_verified'] is False
                for name in ['Engine/ImagePixelContract.h', 'Guest/image_framebuffer.h', 'Guest/kms_format_probe.c', 'tests/ImagePixelContractTests.c']:
                    assert name in payload['image_source_files']
                assert 'kms-format-control' in payload['inventory']
            assert payload['source_commit'] == guest_source and int(payload['workflow_run']) == guest_run
            if info['CFBundleVersion'] in ['4000013', '4000014', '4000015', '4000016', '4000017', '4000018', '4000019', '4000020', '4000021', '4000022', '4000023']:
                assert payload['cases'][0]['kernel_gpu']['resource_bind_flags'] == 2
            assert payload['runtime_dependency_closure_verified'] and payload['linux_runtime_boot_verified']
            for name in ['Image', 'initramfs.cpio.gz']:
                hashed(z.read(gpu + name), payload['files'][name])
            for field in ['guest_shader_verified', 'metal_host_verified', 'host_memory_import_verified',
                          'presentation_verified', 'steamos_verified', 'gameplay_verified']:
                assert bundled[field] is False
        if info['CFBundleVersion'] in ('4000021', '4000022', '4000023'):
            for marker in [b'linux-screen-before-submit', b'linux-screen-drawable-presented', b'physical-ios-linux-two-image-screen-gate', b'Show Linux-rendered images']:
                assert marker in binary, 'Missing compiled guest screen presentation boundary'
        if info['CFBundleVersion'] in ('4000022','4000023'):
            for marker in [b'linux-screen-transaction-present-enqueued', b'linux-screen-lifecycle', b'scheduled-main-thread-core-animation-transaction', b'presented_seconds_later_query']:
                assert marker in binary, 'Missing compiled transaction presenter diagnostics'
        if info['CFBundleVersion'] == '4000023':
            from bundle_guest_gpu import verify_frame_payload
            verify_frame_payload(payload)
            for marker in [b'linux-eight-frame-adapter-configured', b'linux-eight-frame-sequence-checked', b'MPC_FRAME_PRODUCER ',
                           b'MPC_FRAME_EXIT ', b'MPC_VK_FRAME_RENDER ', b'mpc_frames=1', b'Show eight Linux-rendered frames',
                           b'physical-ios-linux-eight-frame-screen-gate']:
                assert marker in binary, 'Missing compiled eight-frame guest boundary'
        return {'schema': 1, 'kind': 'ios-linux-kernel-gate' if linux_gate else 'ios-host-probe-only', 'commit': commit, 'build': info['CFBundleVersion'],
                'bundle_id': info['CFBundleIdentifier'], 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(),
                'bytes': path.stat().st_size, 'zip_crc': 'passed', 'arm64_ios': True,
                'linux_gate_bundled': linux_gate, 'native_vulkan_bundled': native_vulkan, 'guest_gpu_bundled': guest_gpu, 'engine_frameworks_checked': frameworks,
                'linux_boot_verified': False, 'game_graphics_verified': False, 'phone_performance_verified': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('ipa', type=pathlib.Path)
    parser.add_argument('commit')
    parser.add_argument('--receipt', type=pathlib.Path)
    parser.add_argument('--linux-gate', action='store_true')
    parser.add_argument('--build', help='Require the intended app build number')
    parser.add_argument('--native-vulkan', action='store_true')
    parser.add_argument('--guest-gpu', action='store_true')
    args = parser.parse_args()
    result = verify(args.ipa, args.commit, args.linux_gate, args.build, args.native_vulkan, args.guest_gpu)
    text = json.dumps(result, indent=2) + '\n'
    if args.receipt:
        args.receipt.write_text(text, encoding='utf-8')
    print(text)
