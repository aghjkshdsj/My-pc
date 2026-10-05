#!/usr/bin/env python3
"""Compile a separate actual ARM standard-KMS producer with pinned kernel.

Hosted rejection controls are not positive Metal/phone evidence. Preserve the
old image and producer; no private user images or Valve binaries are inputs.
"""
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
from build_guest_image_payload import extend_newc
from build_release_channel_gate import parent_inputs,read_init,PARENT_RUN,PARENT_SOURCE,PARENT_FILES
from prepare_native_kms_guest import prepare
from run_gpu_kernel_gate import validate as validate_kernel
PROJECT=pathlib.Path(__file__).resolve().parents[1]
KERNEL_RUN=37327189927
KERNEL_SOURCE='a3455de052b85b994de9341d6d74081ea31dd6b0'
KERNEL_SHA='f5b28031447603bf2c66846cbdb503ccd35fa86106969af628752c733e188ee7'
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def build(parent,kernel):
    output=PROJECT/'out/native-kms-payload';output.mkdir(exist_ok=False)
    generated=output/'generated';prepare(generated)
    image=kernel/'payload/Image'
    assert sha(image)==KERNEL_SHA and image.stat().st_size==3805192
    kernel_receipt=json.loads((kernel/'payload/payload-receipt.json').read_text())
    assert kernel_receipt['files']['Image']['sha256']==KERNEL_SHA
    patch=json.loads((kernel/'display-patch/patch-receipt.json').read_text())
    assert patch['scope']=='linux-exact-display-response-completion-source'
    assert patch['opt_in']=='virtio_gpu.mpc_native_display_fences=1'
    _,inputs=parent_inputs(parent)
    binary=output/'vk-native-kms-gate'
    command=['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror',
        '-DMPC_IMAGE_SCANOUT','-DMPC_FRAME_SEQUENCE','-DMPC_SCANOUT_FRAME_COUNT=8',
        '-DMPC_SCANOUT_PREFIX="MPC_NATIVE_KMS"','-DMPC_VK_DIAGNOSTIC_PREFIX="MPC_VK_NATIVE_KMS_RENDER "',
        '-I'+str(PROJECT/'Guest'),'-I/usr/include/libdrm',str(generated/'vk_native_kms_gate.c'),
        '-lvulkan','-ldrm','-o',str(binary)]
    subprocess.run(command,check=True)
    assert 'AArch64' in subprocess.check_output(['readelf','-h',str(binary)],text=True)
    dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
    dependencies=[l.split('[')[1].split(']')[0] for l in dynamic.splitlines() if '(NEEDED)' in l]
    assert {'libvulkan.so.1','libdrm.so.2','libc.so.6'}<=set(dependencies)<={'libvulkan.so.1','libdrm.so.2','libc.so.6','ld-linux-aarch64.so.1'}
    original=gzip.decompress(inputs['initramfs.cpio.gz']);init=read_init(original)
    anchor='/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"';assert init.count(anchor)==1
    insert='''native_requested=0
for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in mpc_native_kms=1) native_requested=1;; esac
done
case "$native_requested" in
1)
    native_status=99
    case "$vk_status:$abi_status:$gpu_status" in
    0:0:0)
        export MPC_NATIVE_KMS_RUN="$nonce"
        /vk-native-kms-gate /vertex.spv /fragment.spv
        native_status=$?
        ;;
    esac
    /bin/busybox echo "MPC_NATIVE_KMS_GUEST_EXIT=$native_status"
    ;;
esac
'''
    init=init.replace(anchor,insert+anchor)
    payload=output/'payload';payload.mkdir()
    cpio=extend_newc(original,{'init':(stat.S_IFREG|0o755,init.encode()),
        'vk-native-kms-gate':(stat.S_IFREG|0o755,binary.read_bytes())},additions=('vk-native-kms-gate',))
    (payload/'Image').write_bytes(image.read_bytes());(payload/'initramfs.cpio.gz').write_bytes(gzip.compress(cpio,mtime=0))
    cases=[]
    for has_device in (True,False):
        nonce=uuid.uuid4().hex
        cmd=['qemu-system-aarch64','-machine','virt','-cpu','max','-accel','tcg,thread=multi,split-wx=on,tb-size=32',
            '-smp','2','-m','512','-nodefaults','-display','none','-serial','stdio','-monitor','none',
            '-kernel',str(payload/'Image'),'-initrd',str(payload/'initramfs.cpio.gz'),'-no-reboot','-append',
            'console=ttyAMA0 rdinit=/init panic=1 virtio_gpu.mpc_native_display_fences=1 mpc_native_kms=1 mpc_run='+nonce]
        if has_device:cmd+=['-device','virtio-gpu-pci']
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        serial=result.stdout+result.stderr;print(serial)
        (payload/('2d-rejected.log' if has_device else 'missing-rejected.log')).write_text(serial)
        assert result.returncode==0 and serial.splitlines().count('MPC_NATIVE_KMS_GUEST_EXIT=99')==1
        assert 'MPC_NATIVE_KMS_FLIP ' not in serial and 'MPC_NATIVE_KMS_PRODUCER ' not in serial
        cases.append({'run':nonce,'has_device':has_device,'native_execution_rejected_before_3d':True,
            **validate_kernel(serial,nonce,has_device)})
    manifests=list(pathlib.Path('/usr/share/vulkan/icd.d').glob('lvp*.json'));assert len(manifests)==1
    env=dict(os.environ,VK_DRIVER_FILES=str(manifests[0]),VK_ICD_FILENAMES=str(manifests[0]),MPC_NATIVE_KMS_RUN=uuid.uuid4().hex)
    negative=subprocess.run([str(binary),'/missing.vert','/missing.frag'],env=env,capture_output=True,text=True,timeout=60)
    assert negative.returncode==20 and 'MPC_VK_REJECTED software_renderer=' in negative.stdout
    assert 'MPC_NATIVE_KMS_PRODUCER ' not in negative.stdout and 'MPC_NATIVE_KMS_FLIP ' not in negative.stdout
    (output/'software-rejected.log').write_text(negative.stdout+negative.stderr)
    receipt={'schema':1,'scope':'linux-standard-kms-native-completion-payload-rejection-controls',
        'source_commit':os.environ.get('GITHUB_SHA'),'workflow_run':os.environ.get('GITHUB_RUN_ID'),
        'parent_run':PARENT_RUN,'parent_source':PARENT_SOURCE,'parent_files':PARENT_FILES,
        'kernel_run':KERNEL_RUN,'kernel_source':KERNEL_SOURCE,'kernel_sha256':KERNEL_SHA,
        'kernel_patch':patch,'producer':json.loads((generated/'native-kms-producer-source.json').read_text()),
        'arm64_compiled':True,'dependencies':dependencies,'frame_count':8,'uart_release_used':False,
        'software_renderer_rejected':True,'negative_boot_cases':cases,
        'phone_tested':False,'native_completion_verified':False,'desktop_verified':False,'gameplay_verified':False,
        'files':{n:{'bytes':(payload/n).stat().st_size,'sha256':sha(payload/n)} for n in ['Image','initramfs.cpio.gz']}}
    (payload/'payload-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (output/'init-native-kms').write_text(init)
    with tarfile.open(output/'Native-KMS-Payload.tar.gz','w:gz') as t:t.add(payload,arcname='payload')
    with tarfile.open(output/'Native-KMS-Corresponding-Source.tar.gz','w:gz') as t:
        t.add(parent/'Guest-GPU-Corresponding-Source.tar.gz',arcname='Parent-Guest-Corresponding-Source.tar.gz')
        t.add(kernel/'Display-Completion-Kernel-Corresponding-Source.tar.gz',arcname='Display-Completion-Kernel-Corresponding-Source.tar.gz')
        for name in ['Guest/native_atomic_scanout.h','Guest/vk_gate.c','Guest/image_scanout.h',
                     'Guest/image_export_contract.h','Guest/image_framebuffer.h','Guest/renderer_classification.h',
                     'Engine/ImagePixelContract.h','Engine/FrameSequenceContract.h','tools/prepare_native_kms_guest.py',
                     'tools/build_native_kms_payload.py','tools/build_guest_image_payload.py','tools/build_release_channel_gate.py',
                     'tools/run_gpu_kernel_gate.py','tools/run_kernel_gate.py','tools/make_initramfs.py','tests/test_native_kms_producer.py']:
            t.add(PROJECT/name,arcname=name)
        t.add(generated,arcname='actual-generated-producer');t.add(output/'init-native-kms',arcname='init-native-kms')
        t.add(payload/'payload-receipt.json',arcname='payload-receipt.json')
        t.add(PROJECT.parent/'.github/workflows/steamos-native-kms-payload.yml',arcname='steamos-native-kms-payload.yml')
        for directory in ['libdrm','vulkan']:
            for f in pathlib.Path('/usr/include',directory).glob('*.h'):t.add(f,arcname='build-headers/'+directory+'/'+f.name)
        for name in ['libdrm-dev','libvulkan-dev']:
            t.add('/usr/share/doc/'+name+'/copyright',arcname='build-headers/'+name+'-copyright')
    print(json.dumps({'scope':receipt['scope'],'files':receipt['files'],'phone_tested':False}))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('parent',type=pathlib.Path);parser.add_argument('kernel',type=pathlib.Path)
    args=parser.parse_args();build(args.parent.resolve(),args.kernel.resolve())
