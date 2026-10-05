#!/usr/bin/env python3
"""Bundle exact separately built ABI2 engine, KMS guest and observer; no old app."""
import argparse
import hashlib
import io
import json
import pathlib
import plistlib
import shutil
import tarfile
from bundle_guest_gpu import closure,hashed
from bundle_linux_gate import extract_checked
from bundle_native_vulkan import TRACE_BINARY_SHA,TRACE_FRAMEWORK_SHA,TRACE_SOURCE_SHA,TRACE_RUN,TRACE_RECIPE_COMMIT
from verify_ipa import macho_platform,macho_text
ENGINE_RUN=37338802991
ENGINE_SOURCE='a7fe6de4eb4a8e8a27987f1884a34da1d0e3a2c2'
GUEST_RUN=37338803071
GUEST_SOURCE=ENGINE_SOURCE
FILES={'Image':dict(bytes=3805192,sha256='f5b28031447603bf2c66846cbdb503ccd35fa86106969af628752c733e188ee7'),
       'initramfs.cpio.gz':dict(bytes=10106643,sha256='71809bd8ca89743ddf42dd2eafdbe245e1c022da3cbb273bd2a1a48e476507ed')}
ENGINE_CODE='34ccc088d8dff7075280cb561bb6a92e8396230109739f450a61936fc9ff3327'
ENGINE_SOURCE_ARCHIVE='cedda5dc3bdc0ca53db8a0241da25651d973bf48a52b0258ce52e627a35450b1'
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_inputs(engine,guest,graphics):
    receipt=json.loads((engine/'native-completion-build-receipt.json').read_text())
    assert receipt['scope']=='native-completion-physical-ios-engine-compile-only'
    assert receipt['audit']==dict(abi=2,exported_definitions_verified=True,actual_patched_sources_verified=True,
        physical_ios_compiled=True,metal_join_runtime_verified=False,phone_tested=False)
    base=receipt['base_engine']
    assert base['source_commit']==ENGINE_SOURCE and int(base['workflow_run'])==ENGINE_RUN
    assert base['files']['sysroot-iOS-arm64/Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu']['sha256']==ENGINE_CODE
    assert base['hardware_virtualization'] is False and base['phone_tested'] is False
    assert digest(engine/'GPU-Engine-iOS-Frameworks.tar.gz')==receipt['frameworks_sha256']
    assert digest(engine/'Native-Completion-Corresponding-Source.tar.gz')==ENGINE_SOURCE_ARCHIVE
    payload=json.loads((guest/'payload/payload-receipt.json').read_text())
    assert payload['scope']=='linux-standard-kms-native-completion-payload-rejection-controls'
    assert payload['source_commit']==GUEST_SOURCE and int(payload['workflow_run'])==GUEST_RUN
    assert payload['files']==FILES and payload['arm64_compiled'] is True and payload['frame_count']==8
    assert payload['software_renderer_rejected'] is True and payload['uart_release_used'] is False
    assert payload['phone_tested'] is False and payload['native_completion_verified'] is False
    assert payload['kernel_patch']['opt_in']=='virtio_gpu.mpc_native_display_fences=1'
    assert len(payload['negative_boot_cases'])==2 and all(c['native_execution_rejected_before_3d'] is True for c in payload['negative_boot_cases'])
    assert digest(graphics/'MoltenVK-iOS-Framework.tar.gz')==TRACE_FRAMEWORK_SHA
    assert digest(graphics/'MoltenVK-Corresponding-Source.tar.gz')==TRACE_SOURCE_SHA
    observer=json.loads((graphics/'engine-receipt.json').read_text())
    assert observer['source_commit']==TRACE_RECIPE_COMMIT and int(observer['workflow_run'])==TRACE_RUN
    assert observer['guest_metal_trace_export_compiled'] is True and observer['phone_tested'] is False
    return receipt,payload,observer
def bundle(engine,guest,graphics,app):
    receipt,payload,observer=verify_inputs(engine,guest,graphics)
    base=receipt['base_engine'];selected=closure(base);names={p.split('/')[0] for p in selected}
    frames=app/'Frameworks';frames.mkdir(exist_ok=False)
    with tarfile.open(engine/'GPU-Engine-iOS-Frameworks.tar.gz') as t:
        seen=set()
        for m in t.getmembers():
            if m.isdir():continue
            p=pathlib.PurePosixPath(m.name)
            assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='Frameworks'
            assert m.isfile() and m.size<256*1024*1024 and m.name not in seen;seen.add(m.name)
            if p.parts[1] not in names:continue
            target=app.joinpath(*p.parts);assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True)
            data=t.extractfile(m).read()
            if p.name!='Info.plist':
                hashed(data,base['files']['sysroot-iOS-arm64/'+m.name]);macho_platform(data,6)
            target.write_bytes(data)
    # Observer uses the same exact source-built physical iOS engine accepted by
    # the earlier diagnostic. It observes actual guest submission, never fakes it.
    observer_stage=app.parent/'native-kms-observer-stage'
    extract_checked(graphics/'MoltenVK-iOS-Framework.tar.gz',observer_stage)
    shutil.copytree(observer_stage/'Frameworks/MoltenVK.framework',frames/'MoltenVK.framework')
    molten=frames/'MoltenVK.framework/MoltenVK';assert digest(molten)==TRACE_BINARY_SHA
    selected.add('MoltenVK.framework/MoltenVK')
    identities={}
    for relative in sorted(selected):
        binary=frames/relative;binary.chmod(0o755)
        info=plistlib.loads((binary.parent/'Info.plist').read_bytes());assert info['CFBundleExecutable']==binary.name
        for dep in macho_platform(binary.read_bytes(),6):
            assert not any(s in dep for s in ['IOKit','Hypervisor','/PrivateFrameworks/'])
            assert dep.startswith(('/usr/lib/','/System/Library/')) or (dep.startswith('@rpath/') and (frames/dep.removeprefix('@rpath/')).is_file())
        identities[relative]=macho_text(binary.read_bytes())
    root=app/'LinuxNativeKMS';root.mkdir(exist_ok=False)
    for name,expected in FILES.items():
        data=(guest/'payload'/name).read_bytes();hashed(data,expected);(root/name).write_bytes(data)
    assert (root/'Image').read_bytes()[56:60]==b'ARMd'
    (root/'payload-receipt.json').write_text(json.dumps(payload,indent=2)+'\n')
    metadata=dict(schema=1,scope='bundled-ios-standard-kms-native-completion',completion_abi=2,
        engine_run=ENGINE_RUN,engine_source=ENGINE_SOURCE,guest_run=GUEST_RUN,guest_source=GUEST_SOURCE,
        engine_receipt=receipt,observer_receipt=observer,engine_text_sections=identities,
        hardware_virtualization=False,phone_tested=False,desktop_verified=False,steam_verified=False,gameplay_verified=False)
    (root/'engine-bundle.json').write_text(json.dumps(metadata,indent=2)+'\n')
    # Copy the original QEMU license from the authenticated full source closure.
    with tarfile.open(engine/'Native-Completion-Corresponding-Source.tar.gz') as outer:
        with tarfile.open(fileobj=io.BytesIO(outer.extractfile('GPU-Engine-Corresponding-Source.tar.gz').read())) as base_source:
            candidates=[m for m in base_source.getmembers() if m.isfile() and m.name.endswith('/qemu-10.0.12-utm.tar.xz')]
            assert len(candidates)==1
            with tarfile.open(fileobj=io.BytesIO(base_source.extractfile(candidates[0]).read())) as qemu:
                licenses=[m for m in qemu.getmembers() if m.isfile() and m.name.endswith('/COPYING') and len(pathlib.PurePosixPath(m.name).parts)==2]
                assert len(licenses)==1;(app/'QEMU-COPYING').write_bytes(qemu.extractfile(licenses[0]).read())
    project=pathlib.Path(__file__).resolve().parents[1]
    (app/'Fresh-Source-LICENSE').write_bytes((project/'LICENSE').read_bytes())
    (app/'UPSTREAM-NOTICES.txt').write_text('QEMU/Linux/BusyBox GPL; glibc LGPL; GCC runtime exceptions; ANGLE BSD and per-file licenses; virgl/epoxy/Mesa MIT and per-file licenses; MoltenVK/Vulkan loader Apache-2.0 and dependency licenses. Exact corresponding source, patches, configuration, build recipes and original notices accompany this release. Fresh host MIT terms do not replace upstream licenses. No Valve client, rootfs, game or user data is distributed.\n')
    print(json.dumps(dict(scope=metadata['scope'],frameworks=sorted(identities),files=FILES,phone_tested=False),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['engine','guest','graphics','app']:p.add_argument(name,type=pathlib.Path)
    a=p.parse_args();bundle(a.engine,a.guest,a.graphics,a.app)
