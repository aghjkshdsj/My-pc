#!/usr/bin/env python3
"""Boot the exact ARM Linux payload with a real bidirectional UART descriptor.

Channel verification is independent of Metal, mutable buffer reuse and iOS.
"""
import argparse,gzip,hashlib,json,os,pathlib,socket,stat,struct,subprocess,tarfile,time,uuid,zlib
from build_guest_image_payload import extend_newc
PROJECT=pathlib.Path(__file__).resolve().parents[1]
PARENT_SOURCE='8759ffe84d360ca61e0d7de7b2f3347682916cde'
PARENT_RUN=37233435975
PARENT_FILES={'Image':'a8f995e831fcfe43807873c1579ab0f80658afb701b80b08047f00c29e1ad166',
              'initramfs.cpio.gz':'40e92bcd95cb4877ae23e259d1edf7aee9c33c314a5843be8179e9fe95208989'}

def read_init(data):
    assert len(data)<128*1024*1024
    position=0
    while True:
        assert data[position:position+6]==b'070701'
        fields=[int(data[position+6+i:position+14+i],16) for i in range(0,104,8)]
        assert 1<fields[11]<4096 and fields[6]<64*1024*1024
        name=data[position+110:position+110+fields[11]-1].decode()
        start=(position+110+fields[11]+3)&~3
        assert start+fields[6]<=len(data)
        if name=='init': return data[start:start+fields[6]].decode()
        position=(start+fields[6]+3)&~3
        assert name!='TRAILER!!!', 'Missing init'

def parent_inputs(parent):
    with tarfile.open(parent/'Guest-GPU-Payload.tar.gz') as archive:
        receipt=json.loads(archive.extractfile('payload/payload-receipt.json').read())
        assert receipt['scope']=='linux-arm64-graphics-payload-eight-frame-boot-controls'
        assert receipt['source_commit']==PARENT_SOURCE and int(receipt['workflow_run'])==PARENT_RUN
        inputs={name:archive.extractfile('payload/'+name).read() for name in PARENT_FILES}
    for name,data in inputs.items():
        assert hashlib.sha256(data).hexdigest()==PARENT_FILES[name] and len(data)==receipt['files'][name]['bytes']
    return receipt,inputs

def response(nonce,kind=6,serial=1,resource=7,release=0):
    data=struct.pack('>II6QIIQ',0x4d504352,65536|kind,int(nonce[:16],16),int(nonce[16:],16),
                     serial,1,release,0,resource,0,0)
    return data+struct.pack('>II',zlib.crc32(data),80)

def boot(payload,output,case):
    nonce=uuid.uuid4().hex
    host,engine=socket.socketpair();host.settimeout(0.2)
    cmd=['qemu-system-aarch64','-machine','virt','-cpu','max','-accel','tcg,thread=multi,split-wx=on,tb-size=32',
         '-smp','2','-m','512','-nodefaults','-display','none','-chardev',
         f'socket,id=serial0,fd={engine.fileno()},server=off,wait=off','-serial','chardev:serial0','-monitor','none',
         '-kernel',str(payload/'Image'),'-initrd',str(payload/'initramfs.cpio.gz'),'-append',
         'console=ttyAMA0 rdinit=/init panic=1 mpc_channel=1 mpc_run='+nonce,'-no-reboot','-device','virtio-gpu-pci']
    child=subprocess.Popen(cmd,pass_fds=(engine.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    engine.close();serial=bytearray();pending=bytearray();requests=[];deadline=time.monotonic()+180
    try:
        while time.monotonic()<deadline:
            try: data=host.recv(8192)
            except socket.timeout:
                if child.poll() is not None: break
                continue
            except ConnectionResetError: break
            if not data: break
            serial.extend(data);pending.extend(data)
            assert len(serial)<8*1024*1024 and len(pending)<1024*1024
            while b'\n' in pending:
                raw,_,remaining=pending.partition(b'\n');pending=bytearray(remaining)
                if not raw.startswith(b'MPC_CHANNEL_REQUEST '): continue
                request=json.loads(raw[len(b'MPC_CHANNEL_REQUEST '):].rstrip(b'\r'))
                assert request==dict(schema=1,run=nonce,serial=1,incarnation=1,resource_id=7)
                requests.append(request);assert len(requests)==1
                packet=response(nonce)
                if case=='wrong-session': packet=response(uuid.uuid4().hex)
                elif case=='wrong-resource': packet=response(nonce,resource=8)
                elif case=='corrupt-integrity': packet=packet[:20]+bytes([packet[20]^1])+packet[21:]
                elif case=='partial-packet': packet=packet[:20]
                elif case=='missing-response': continue
                if case=='fragmented-response':
                    for byte in packet: host.sendall(bytes([byte]))
                else: host.sendall(packet)
        assert time.monotonic()<deadline, 'Channel boot deadline'
        stdout,stderr=child.communicate(timeout=10)
        assert child.returncode==0,(child.returncode,stderr.decode(errors='replace'))
    finally:
        host.close()
        if child.poll() is None: child.kill();child.communicate()
    text=serial.decode('utf-8',errors='strict')
    (output/(case+'.log')).write_text(text+stdout.decode()+stderr.decode(),encoding='utf-8')
    rows=[json.loads(line.removeprefix('MPC_CHANNEL_RESULT ')) for line in text.splitlines()
          if line.startswith('MPC_CHANNEL_RESULT ')]
    assert len(requests)==len(rows)==1 and rows[0]['run']==nonce
    positive=case in ('valid-response','fragmented-response')
    assert rows[0]==dict(schema=1,run=nonce,binary_response_verified=positive,native_gpu_verified=False,buffer_reuse_verified=False)
    assert text.splitlines().count('MPC_CHANNEL_EXIT='+('0' if positive else '4'))==1
    assert text.splitlines().count('MPC_LINUX_EXIT=0')==1
    return dict(case=case,guest_response_verified=positive,negative_rejected=not positive,
                complete_kernel_exit=True,actual_linux_uart=True,native_gpu_verified=False)

def build(parent):
    output=PROJECT/'out/release-channel-gate';assert not output.exists(),'Preserve earlier outputs'
    output.mkdir();payload=output/'payload';payload.mkdir()
    receipt,inputs=parent_inputs(parent)
    executable=output/'release-channel-probe'
    subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror',str(PROJECT/'Guest/release_channel_probe.c'),
                    '-o',str(executable)],check=True)
    assert 'AArch64' in subprocess.check_output(['readelf','-h',str(executable)],text=True)
    original=gzip.decompress(inputs['initramfs.cpio.gz']);init=read_init(original)
    anchor='/bin/busybox echo "MPC_LINUX_EXIT=$abi_status"';assert init.count(anchor)==1
    insert='''channel_requested=0
for token in $(/bin/busybox cat /proc/cmdline); do
    case "$token" in mpc_channel=1) channel_requested=1;; esac
done
if [ "$channel_requested" = 1 ]; then
    export MPC_CHANNEL_RUN="$nonce"
    /release-channel-probe
    channel_status=$?
    /bin/busybox echo "MPC_CHANNEL_EXIT=$channel_status"
fi
'''
    init=init.replace(anchor,insert+anchor)
    cpio=extend_newc(original,{'init':(stat.S_IFREG|0o755,init.encode()),
        'release-channel-probe':(stat.S_IFREG|0o755,executable.read_bytes())},additions=('release-channel-probe',))
    (payload/'Image').write_bytes(inputs['Image']);(payload/'initramfs.cpio.gz').write_bytes(gzip.compress(cpio,mtime=0))
    cases=[boot(payload,output,case) for case in ['valid-response','fragmented-response','wrong-session',
        'wrong-resource','corrupt-integrity','partial-packet','missing-response']]
    result=dict(schema=1,scope='hosted-arm-linux-actual-bidirectional-uart-release-channel',
        source_commit=os.environ['GITHUB_SHA'],workflow_run=os.environ['GITHUB_RUN_ID'],
        parent_source=PARENT_SOURCE,parent_run=PARENT_RUN,parent_files=PARENT_FILES,cases=cases,
        native_gpu_verified=False,mutable_buffer_reuse_verified=False,phone_verified=False,
        channel_scope='Diagnostic explicit release handshake; production KMS/WSI remains separate.')
    (output/'channel-receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('parent',type=pathlib.Path)
    build(parser.parse_args().parent.resolve())
