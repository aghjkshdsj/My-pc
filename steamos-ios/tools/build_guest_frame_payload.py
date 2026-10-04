#!/usr/bin/env python3
"""Extend the exact accepted image payload with a separate eight-frame binary.

Hosted checks reject missing 3D and software ICDs. They cannot prove phone GPU
execution, visible animation, frame pacing, SteamOS or game FPS.
"""
import argparse,gzip,hashlib,json,os,pathlib,stat,subprocess,tarfile,uuid
from build_guest_image_payload import extend_newc
from run_gpu_kernel_gate import validate as validate_kernel
PROJECT=pathlib.Path(__file__).resolve().parents[1]
PARENT_RUN=37222125501
PARENT_SOURCE='453a1d1f19c04b5d49328f135db32257a22d8f30'
PARENT_FILES={'Image':'a8f995e831fcfe43807873c1579ab0f80658afb701b80b08047f00c29e1ad166',
              'initramfs.cpio.gz':'781192c1b1a33fc30b1b495868d329a8ad2f7bfb5d52cda6a3be08b139627ec7'}


def build(parent):
    output=PROJECT/'out/guest-frame-payload'; assert not output.exists(), 'Preserve prior builds'
    output.mkdir(); payload=output/'payload'; payload.mkdir()
    receipt=json.loads((parent/'payload/payload-receipt.json').read_text())
    assert receipt['scope']=='linux-arm64-graphics-payload-image-export-boot-controls'
    assert receipt['source_commit']==PARENT_SOURCE and int(receipt['workflow_run'])==PARENT_RUN
    with tarfile.open(parent/'Guest-GPU-Payload.tar.gz') as archive:
        assert json.loads(archive.extractfile('payload/payload-receipt.json').read())==receipt
        inputs={name:archive.extractfile('payload/'+name).read() for name in PARENT_FILES}
    for name,data in inputs.items():
        assert hashlib.sha256(data).hexdigest()==PARENT_FILES[name] and len(data)==receipt['files'][name]['bytes']
    contract=output/'frame-contract-test'
    subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                    str(PROJECT/'tests/FramePixelContractTests.c'),'-o',str(contract)],check=True)
    subprocess.run([str(contract)],check=True)
    binary=output/'vk-frames-gate'
    subprocess.run(['gcc','-O2','-Wall','-Wextra','-Werror','-DMPC_IMAGE_SCANOUT','-DMPC_FRAME_SEQUENCE',
        '-DMPC_SCANOUT_FRAME_COUNT=8','-DMPC_SCANOUT_PREFIX="MPC_FRAME"','-DMPC_SCANOUT_WAIT_NS=125000000UL',
        '-DMPC_VK_DIAGNOSTIC_PREFIX="MPC_VK_FRAME_RENDER "','-I/usr/include/libdrm',
        str(PROJECT/'Guest/vk_gate.c'),'-lvulkan','-ldrm','-o',str(binary)],check=True)
    assert binary.read_bytes()[:4]==b'\x7fELF'
    assert 'AArch64' in subprocess.check_output(['readelf','-h',str(binary)],text=True)
    dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
    dependencies=[line.split('[')[1].split(']')[0] for line in dynamic.splitlines() if '(NEEDED)' in line]
    assert {'libvulkan.so.1','libdrm.so.2','libc.so.6'}<=set(dependencies)<={'libvulkan.so.1','libdrm.so.2','libc.so.6','ld-linux-aarch64.so.1'}
    original=gzip.decompress(inputs['initramfs.cpio.gz'])
    # Bounded parser follows the same accepted record rules; never extract paths.
    position=0; init=None
    while True:
        assert original[position:position+6]==b'070701'
        fields=[int(original[position+6+i:position+14+i],16) for i in range(0,104,8)]
        name=original[position+110:position+110+fields[11]-1].decode()
        start=(position+110+fields[11]+3)&~3
        if name=='init': init=original[start:start+fields[6]].decode()
        position=(start+fields[6]+3)&~3
        if name=='TRAILER!!!': break
    assert init is not None and init.count('/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"')==1
    insert='''frame_requested=0
for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in mpc_frames=1) frame_requested=1;; esac
done
case "$frame_requested" in
1)
    frame_status=99
    case "$vk_status:$abi_status:$gpu_status" in
    0:0:0)
        export MPC_FRAME_RUN="$nonce"
        /vk-frames-gate /vertex.spv /fragment.spv
        frame_status=$?
        ;;
    esac
    /bin/busybox echo "MPC_FRAME_GUEST_EXIT=$frame_status"
    ;;
esac
'''
    init=init.replace('/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"',insert+'/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"')
    cpio=extend_newc(original,{'init':(stat.S_IFREG|0o755,init.encode()),
        'vk-frames-gate':(stat.S_IFREG|0o755,binary.read_bytes())},additions=('vk-frames-gate',))
    (output/'init-frame-userspace').write_text(init)
    (payload/'Image').write_bytes(inputs['Image'])
    (payload/'initramfs.cpio.gz').write_bytes(gzip.compress(cpio,mtime=0))
    cases=[]
    for has_device in (True,False):
        nonce=uuid.uuid4().hex
        cmd=['qemu-system-aarch64','-machine','virt','-cpu','max','-accel','tcg,thread=multi,split-wx=on,tb-size=32',
            '-smp','2','-m','512','-nodefaults','-display','none','-serial','stdio','-monitor','none',
            '-kernel',str(payload/'Image'),'-initrd',str(payload/'initramfs.cpio.gz'),'-append',
            'console=ttyAMA0 rdinit=/init panic=1 mpc_frames=1 mpc_run='+nonce,'-no-reboot']
        if has_device: cmd+=['-device','virtio-gpu-pci']
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        serial=run.stdout+run.stderr; print(serial)
        (payload/('2d-frame-control.log' if has_device else 'missing-frame-control.log')).write_text(serial)
        assert run.returncode==0 and serial.splitlines().count('MPC_GPU_GUEST_EXIT=3')==1
        assert serial.splitlines().count('MPC_FRAME_GUEST_EXIT=99')==1
        assert 'MPC_FRAME_PRODUCER ' not in serial and 'MPC_VK_FRAME_RENDER ' not in serial
        cases.append(dict(run=nonce,has_2d_device=has_device,frame_execution_rejected_before_3d=True,
                          **validate_kernel(serial,nonce,has_device)))
    manifests=list(pathlib.Path('/usr/share/vulkan/icd.d').glob('lvp*.json')); assert len(manifests)==1
    lvp=manifests[0]; assert 'lvp' in json.loads(lvp.read_text())['ICD']['library_path']
    env=dict(os.environ,VK_DRIVER_FILES=str(lvp),VK_ICD_FILENAMES=str(lvp),MPC_FRAME_RUN=uuid.uuid4().hex)
    negative=subprocess.run([str(binary),'/missing.vert','/missing.frag'],env=env,capture_output=True,text=True,timeout=60)
    (output/'software-frames-rejected.log').write_text(negative.stdout+negative.stderr)
    print(negative.stdout+negative.stderr)
    assert negative.returncode==20 and 'MPC_VK_REJECTED software_renderer=' in negative.stdout
    assert 'MPC_FRAME_PRODUCER ' not in negative.stdout and 'MPC_VK_FRAME_RENDER ' not in negative.stdout
    names=['Guest/vk_gate.c','Guest/image_scanout.h','Guest/image_export_contract.h','Guest/image_framebuffer.h',
           'Guest/renderer_classification.h','Engine/ImagePixelContract.h','Engine/FrameSequenceContract.h',
           'tests/FramePixelContractTests.c','tools/build_guest_frame_payload.py','tools/build_guest_image_payload.py',
           'tools/make_initramfs.py','tools/run_gpu_kernel_gate.py','tools/run_kernel_gate.py']
    source_files={name:hashlib.sha256((PROJECT/name).read_bytes()).hexdigest() for name in names}
    receipt['inventory']['init']=dict(mode=stat.S_IFREG|0o755,bytes=len(init.encode()),sha256=hashlib.sha256(init.encode()).hexdigest())
    receipt['inventory']['vk-frames-gate']=dict(mode=stat.S_IFREG|0o755,bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    receipt.update(scope='linux-arm64-graphics-payload-eight-frame-boot-controls',source_commit=os.environ['GITHUB_SHA'],
        workflow_run=os.environ['GITHUB_RUN_ID'],parent_image_source=PARENT_SOURCE,parent_image_run=PARENT_RUN,
        parent_image_files=PARENT_FILES,frame_negative_boot_cases=cases,frame_sequence_compiled=True,
        frame_count=8,frame_phases=list(range(0,120,17)),frame_guest_pixels=7372800,frame_channel_sum=5157519360,
        frame_source_endpoint_pixels=1843200,frame_endpoint_channel_sum=1281269760,frame_synthetic_pixel_contract_passed=True,
        software_frame_renderer_rejected=True,frame_sequence_verified=False,frame_pacing_verified=False,
        frame_gate_dependencies=dependencies,frame_source_files=source_files,
        files={name:dict(bytes=(payload/name).stat().st_size,sha256=hashlib.sha256((payload/name).read_bytes()).hexdigest()) for name in PARENT_FILES})
    (payload/'payload-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(output/'Guest-GPU-Payload.tar.gz','w:gz') as archive: archive.add(payload,arcname='payload')
    with tarfile.open(output/'Guest-GPU-Corresponding-Source.tar.gz','w:gz') as archive:
        archive.add(parent/'Guest-GPU-Corresponding-Source.tar.gz',arcname='Parent-Guest-GPU-Corresponding-Source.tar.gz')
        for name in names: archive.add(PROJECT/name,arcname=name)
        archive.add(output/'init-frame-userspace',arcname='init-frame-userspace')
        archive.add(payload/'payload-receipt.json',arcname='payload-receipt.json')
        archive.add(PROJECT.parent/'.github/workflows/steamos-guest-frame-payload.yml',arcname='steamos-guest-frame-payload.yml')
        for directory in ('libdrm','vulkan'):
            for path in pathlib.Path('/usr/include',directory).glob('*.h'):
                archive.add(path,arcname='build-headers/'+directory+'/'+path.name)
        for name in ('libdrm-dev','libvulkan-dev'):
            archive.add('/usr/share/doc/'+name+'/copyright',arcname='build-headers/'+name+'-copyright')
    print(json.dumps(dict(scope=receipt['scope'],files=receipt['files'],phone_tested=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('parent',type=pathlib.Path)
    build(parser.parse_args().parent.resolve())
