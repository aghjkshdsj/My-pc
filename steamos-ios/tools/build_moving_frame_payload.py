#!/usr/bin/env python3
"""Compile a three-buffer ARM Linux moving gate while retaining the eight-frame gate.

Positive moving graphics/release behavior needs the actual phone. Hosted boots
reject missing 3D; the software ICD control rejects software graphics.
"""
import argparse,gzip,hashlib,json,os,pathlib,stat,subprocess,tarfile,uuid
from build_guest_image_payload import extend_newc
from build_release_channel_gate import parent_inputs,read_init,PARENT_SOURCE,PARENT_RUN,PARENT_FILES
from run_gpu_kernel_gate import validate as validate_kernel
PROJECT=pathlib.Path(__file__).resolve().parents[1]

def build(parent):
    output=PROJECT/'out/guest-moving-payload';assert not output.exists(),'Preserve prior builds'
    output.mkdir();payload=output/'payload';payload.mkdir()
    receipt,inputs=parent_inputs(parent)
    contract=output/'moving-contract-test'
    subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',str(PROJECT/'tests/MovingFramePixelContractTests.c'),'-o',str(contract)],check=True)
    synthetic=json.loads(subprocess.check_output([str(contract)],text=True))
    assert synthetic['endpoint_pixels']==1843200 and synthetic['distinct_phases']==120 and synthetic['fixed_resources']==3
    binary=output/'vk-moving-gate'
    subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-DMPC_IMAGE_SCANOUT','-DMPC_MOVING_SEQUENCE',
        '-DMPC_VK_DIAGNOSTIC_PREFIX="MPC_VK_MOVING_RENDER "','-I/usr/include/libdrm',
        str(PROJECT/'Guest/vk_gate.c'),'-lvulkan','-ldrm','-o',str(binary)],check=True)
    assert 'AArch64' in subprocess.check_output(['readelf','-h',str(binary)],text=True)
    dependencies=[line.split('[')[1].split(']')[0] for line in subprocess.check_output(['readelf','-d',str(binary)],text=True).splitlines() if '(NEEDED)' in line]
    assert {'libvulkan.so.1','libdrm.so.2','libc.so.6'}<=set(dependencies)<={'libvulkan.so.1','libdrm.so.2','libc.so.6','ld-linux-aarch64.so.1'}
    original=gzip.decompress(inputs['initramfs.cpio.gz']);init=read_init(original)
    anchor='/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"';assert init.count(anchor)==1
    insert='''moving_requested=0
for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in mpc_moving=1) moving_requested=1;; esac
done
if [ "$moving_requested" = 1 ]; then
    moving_status=99
    case "$vk_status:$abi_status:$gpu_status" in
    0:0:0)
        export MPC_MOVE_RUN="$nonce"
        /vk-moving-gate /vertex.spv /fragment.spv
        moving_status=$?
        ;;
    esac
    /bin/busybox echo "MPC_MOVE_GUEST_EXIT=$moving_status"
fi
'''
    init=init.replace(anchor,insert+anchor)
    cpio=extend_newc(original,{'init':(stat.S_IFREG|0o755,init.encode()),
        'vk-moving-gate':(stat.S_IFREG|0o755,binary.read_bytes())},additions=('vk-moving-gate',))
    (payload/'Image').write_bytes(inputs['Image']);(payload/'initramfs.cpio.gz').write_bytes(gzip.compress(cpio,mtime=0))
    (output/'init-moving-userspace').write_text(init,encoding='utf-8')
    cases=[]
    for has_device in (True,False):
        nonce=uuid.uuid4().hex
        cmd=['qemu-system-aarch64','-machine','virt','-cpu','max','-accel','tcg,thread=multi,split-wx=on,tb-size=32',
            '-smp','2','-m','512','-nodefaults','-display','none','-serial','stdio','-monitor','none',
            '-kernel',str(payload/'Image'),'-initrd',str(payload/'initramfs.cpio.gz'),'-append',
            'console=ttyAMA0 rdinit=/init panic=1 mpc_moving=1 mpc_run='+nonce,'-no-reboot']
        if has_device:cmd+=['-device','virtio-gpu-pci']
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        serial=run.stdout+run.stderr
        (payload/('2d-moving-control.log' if has_device else 'missing-moving-control.log')).write_text(serial,encoding='utf-8')
        assert run.returncode==0 and serial.splitlines().count('MPC_MOVE_GUEST_EXIT=99')==1
        assert 'MPC_MOVE_CTL ' not in serial and 'MPC_VK_MOVING_RENDER ' not in serial
        cases.append(dict(has_2d_device=has_device,moving_execution_rejected_before_3d=True,**validate_kernel(serial,nonce,has_device)))
    manifests=list(pathlib.Path('/usr/share/vulkan/icd.d').glob('lvp*.json'));assert len(manifests)==1
    env=dict(os.environ,VK_DRIVER_FILES=str(manifests[0]),VK_ICD_FILENAMES=str(manifests[0]),MPC_MOVE_RUN=uuid.uuid4().hex)
    rejected=subprocess.run([str(binary),'/missing.vert','/missing.frag'],env=env,capture_output=True,text=True,timeout=60)
    (output/'software-moving-rejected.log').write_text(rejected.stdout+rejected.stderr,encoding='utf-8')
    assert rejected.returncode==20 and 'MPC_VK_REJECTED software_renderer=' in rejected.stdout
    assert 'MPC_MOVE_CTL ' not in rejected.stdout and 'MPC_VK_MOVING_RENDER ' not in rejected.stdout
    names=['Guest/vk_gate.c','Guest/moving_scanout.h','Guest/frame_release_channel.h','Guest/image_export_contract.h',
           'Guest/image_framebuffer.h','Guest/renderer_classification.h','Engine/ImagePixelContract.h',
           'Engine/MovingFrameContract.h','Engine/FrameReleaseWire.h','tests/MovingFramePixelContractTests.c',
           'tools/build_moving_frame_payload.py','tools/build_release_channel_gate.py',
           'tools/build_guest_image_payload.py','tools/make_initramfs.py','tools/run_gpu_kernel_gate.py','tools/run_kernel_gate.py']
    sources={name:hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() for name in names}
    receipt['inventory']['init']=dict(mode=stat.S_IFREG|0o755,bytes=len(init.encode()),sha256=hashlib.sha256(init.encode()).hexdigest())
    receipt['inventory']['vk-moving-gate']=dict(mode=stat.S_IFREG|0o755,bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    receipt.update(scope='linux-arm64-graphics-payload-moving-frames-boot-controls',source_commit=os.environ['GITHUB_SHA'],
        workflow_run=os.environ['GITHUB_RUN_ID'],parent_frame_source=PARENT_SOURCE,parent_frame_run=PARENT_RUN,
        parent_frame_files=PARENT_FILES,moving_frame_count=120,moving_buffer_count=3,moving_buffer_reuses=117,
        moving_reacquisitions_with_final_drain=120,moving_endpoint_pixels=1843200,moving_endpoint_channel_sum=synthetic['channel_sum'],
        moving_guest_readbacks=2,moving_native_readbacks=2,moving_synthetic_contract=synthetic,
        moving_negative_boot_cases=cases,moving_sequence_compiled=True,software_moving_renderer_rejected=True,
        moving_buffer_reuse_verified=False,moving_display_timing_verified=False,game_fps_verified=False,
        moving_gate_dependencies=dependencies,moving_source_files=sources,
        release_channel_scope='Explicit diagnostic UART handoff; production Linux KMS/WSI remains unfinished.',
        files={name:dict(bytes=(payload/name).stat().st_size,sha256=hashlib.sha256((payload/name).read_bytes()).hexdigest()) for name in PARENT_FILES})
    (payload/'payload-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    with tarfile.open(output/'Guest-GPU-Payload.tar.gz','w:gz') as archive:archive.add(payload,arcname='payload')
    with tarfile.open(output/'Guest-GPU-Corresponding-Source.tar.gz','w:gz') as archive:
        archive.add(parent/'Guest-GPU-Corresponding-Source.tar.gz',arcname='Parent-Guest-GPU-Corresponding-Source.tar.gz')
        for name in names:archive.add(PROJECT/name,arcname=name)
        archive.add(output/'init-moving-userspace',arcname='init-moving-userspace')
        archive.add(payload/'payload-receipt.json',arcname='payload-receipt.json')
        archive.add(PROJECT.parent/'.github/workflows/steamos-guest-moving-payload.yml',arcname='steamos-guest-moving-payload.yml')
        for directory in ('libdrm','vulkan'):
            for path in pathlib.Path('/usr/include',directory).glob('*.h'):archive.add(path,arcname='build-headers/'+directory+'/'+path.name)
        for name in ('libdrm-dev','libvulkan-dev'):
            archive.add('/usr/share/doc/'+name+'/copyright',arcname='build-headers/'+name+'-copyright')
    print(json.dumps(dict(scope=receipt['scope'],files=receipt['files'],compiled_moving_gate=True,phone_verified=False)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('parent',type=pathlib.Path)
    build(parser.parse_args().parent.resolve())
