#!/usr/bin/env python3
"""Audit the actual device-iOS ABI2 exports and retain complete fork source."""
import argparse
import json
import pathlib
import re
import subprocess
import tarfile
from collect_gpu_engine_sources import collect, digest, PROJECT

def audit_completion(exports, commands, source, actual):
    assert source['scope']=='native-completion-adapter-source-only' and source['abi']==2
    for symbol in ('mpc_qemu_configure_native_completion','mpc_qemu_complete_native_read'):
        assert re.search(r'^[0-9a-fA-F]+[ \t]+T[ \t]+_'+symbol+r'[ \t]*$',exports,re.M),symbol
    for path in ('/ui/egl-headless.c','/hw/display/virtio-gpu.c','/hw/display/virtio-gpu-gl.c','/hw/display/virtio-gpu-virgl.c'):
        rows=[c for c in commands if c.get('file','').endswith(path)]
        assert len(rows)==1 and '-c' in rows[0]['command'].split(),path
    for path,row in source['files'].items():
        assert actual.get(path)==row['patched_sha256'],path
    return {'abi':2,'exported_definitions_verified':True,'actual_patched_sources_verified':True,
        'physical_ios_compiled':True,'metal_join_runtime_verified':False,'phone_tested':False}

def collect_completion(root, graphics):
    collect(root,graphics)
    build=root/'build-iOS-arm64'
    qemus=[p for p in build.glob('qemu-*') if p.is_dir()]
    assert len(qemus)==1
    qemu=qemus[0]
    engine=root/'sysroot-iOS-arm64/Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu'
    exports=subprocess.check_output(['xcrun','nm','-gU',str(engine)],text=True)
    configs=list(qemu.rglob('config-host.h')); assert len(configs)==1
    commands=json.loads((configs[0].parent/'compile_commands.json').read_text())
    source=json.loads((root/'native-completion-source.json').read_text())
    actual={n:digest(qemu/n) for n in source['files']}
    audit=audit_completion(exports,commands,source,actual)
    receipt={'schema':1,'scope':'native-completion-physical-ios-engine-compile-only',
        'audit':audit,'source':source,'base_engine':json.loads((root/'gpu-engine-receipt.json').read_text()),
        'frameworks_sha256':digest(root/'GPU-Engine-iOS-Frameworks.tar.gz')}
    (root/'native-completion-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(root/'Native-Completion-Corresponding-Source.tar.gz','w:gz') as t:
        for name in ['GPU-Engine-Corresponding-Source.tar.gz','native-completion-build-receipt.json',
                     'native-completion-source.json','qemu-native-completion.patch']:
            t.add(root/name,arcname=name)
        for name in ['Engine/NativeCompletionABI.h','Engine/NativeCompletionLedger.h','Engine/QEMUNativeCompletion.inc',
                     'tools/patch_qemu_native_completion.py','tools/prepare_completion_engine_build.py',
                     'tools/collect_completion_engine_sources.py','tests/native_completion_control.c',
                     'tests/test_native_completion.py']:
            t.add(PROJECT/name,arcname='fresh-recipes/'+name)
        t.add(PROJECT.parent/'.github/workflows/steamos-ios-completion-engine.yml',arcname='steamos-ios-completion-engine.yml')
        for name in source['files']:
            t.add(qemu/name,arcname='actual-patched-source/'+name)
    print(json.dumps({'scope':receipt['scope'],'audit':audit,'source_sha256':digest(root/'Native-Completion-Corresponding-Source.tar.gz')},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=pathlib.Path);parser.add_argument('graphics',type=pathlib.Path)
    args=parser.parse_args();collect_completion(args.root.resolve(),args.graphics.resolve())
