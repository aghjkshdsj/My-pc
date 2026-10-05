#!/usr/bin/env python3
"""Independent complete package/closure/source identity checks, not phone proof."""
import argparse
import hashlib
import json
import pathlib
import plistlib
import zipfile
from bundle_native_kms import ENGINE_RUN,ENGINE_SOURCE,GUEST_RUN,GUEST_SOURCE,FILES,ENGINE_CODE
from bundle_native_vulkan import TRACE_BINARY_SHA
from verify_ipa import macho_platform,macho_text
from verify_host_symbols import macho_uuid
def verify(path,commit,dwarf=None):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        assert all(not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts for n in z.namelist())
        prefix='Payload/MyPCSteamOSNativeKMS.app/'
        info=plistlib.loads(z.read(prefix+'Info.plist'))
        assert info['CFBundleIdentifier']=='com.aghjkshdsj.mypc.steamos.nativekms' and info['CFBundleVersion']=='4000029'
        assert info['MPCSourceCommit']==commit and info['CFBundleExecutable']=='MyPCSteamOSNativeKMS'
        host=z.read(prefix+info['CFBundleExecutable']);macho_platform(host,2)
        for marker in [b'mpc_qemu_configure_native_completion',b'mpc_qemu_complete_native_read',b'mpc_qemu_cancel_native_read',
            b'virtio_gpu.mpc_native_display_fences=1 mpc_native_kms=1',b'native-kms-worker-retired',b'completion_callbacks_in_progress']:
            assert marker in host,marker
        assert not any(s in n for n in z.namelist() for s in ['Madeira','NativeSteam','LinuxGuestGPU/','LinuxGate/'])
        root=prefix+'LinuxNativeKMS/'
        receipt=json.loads(z.read(root+'payload-receipt.json'));assert receipt['files']==FILES
        metadata=json.loads(z.read(root+'engine-bundle.json'))
        assert metadata['scope']=='bundled-ios-standard-kms-native-completion' and metadata['completion_abi']==2
        assert (metadata['engine_run'],metadata['engine_source'],metadata['guest_run'],metadata['guest_source'])==(ENGINE_RUN,ENGINE_SOURCE,GUEST_RUN,GUEST_SOURCE)
        assert metadata['phone_tested'] is False and metadata['hardware_virtualization'] is False
        for n,expected in FILES.items():
            data=z.read(root+n);assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
        assert z.read(root+'Image')[56:60]==b'ARMd'
        identities=metadata['engine_text_sections'];assert 8<=len(identities)<=32
        present=set()
        for n in z.namelist():
            if not n.startswith(prefix+'Frameworks/') or not n.endswith('.framework/Info.plist'):continue
            framework=plistlib.loads(z.read(n));binary=n.rsplit('/',1)[0]+'/'+framework['CFBundleExecutable']
            relative=binary.removeprefix(prefix+'Frameworks/');present.add(relative);data=z.read(binary)
            assert macho_text(data)==identities[relative]
            for dep in macho_platform(data,6):
                assert not any(s in dep for s in ['IOKit','Hypervisor','/PrivateFrameworks/'])
                assert dep.startswith(('/usr/lib/','/System/Library/')) or (dep.startswith('@rpath/') and prefix+'Frameworks/'+dep.removeprefix('@rpath/') in z.namelist())
        assert present==set(identities)
        engine=z.read(prefix+'Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu')
        assert hashlib.sha256(engine).hexdigest()==ENGINE_CODE
        assert hashlib.sha256(z.read(prefix+'Frameworks/MoltenVK.framework/MoltenVK')).hexdigest()==TRACE_BINARY_SHA
        for n in ['QEMU-COPYING','Fresh-Source-LICENSE','UPSTREAM-NOTICES.txt']:assert len(z.read(prefix+n))>100
        symbol=macho_uuid(host,2)
        if dwarf:assert macho_uuid(dwarf.read_bytes(),10)==symbol
    return dict(schema=1,scope='physical-ios-standard-linux-kms-package-only',source_commit=commit,build='4000029',
        ipa_bytes=path.stat().st_size,ipa_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),host_uuid=symbol,
        framework_count=len(present),exact_debug_symbols_verified=bool(dwarf),phone_tested=False,
        standard_kms_native_completion_verified=False,desktop_verified=False,steam_verified=False,gameplay_verified=False)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('ipa',type=pathlib.Path);p.add_argument('commit')
    p.add_argument('--dwarf',type=pathlib.Path);p.add_argument('--receipt',type=pathlib.Path);a=p.parse_args()
    r=verify(a.ipa,a.commit,a.dwarf);text=json.dumps(r,indent=2)+'\n'
    if a.receipt:a.receipt.write_text(text)
    print(text)
