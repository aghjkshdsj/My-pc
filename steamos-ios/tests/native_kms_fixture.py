"""Synthetic receipt rejection fixture; never device/runtime evidence."""
import copy
import json
import pathlib
import sys
NONCE='1'*32
def fixture():
    lines=['MPC_LINUX_ABI '+json.dumps(dict(schema=1,run=NONCE,machine='aarch64',elf_arch='aarch64',page_bytes=4096,
        failures=0,checksum='1d250c45a7bbc87e',signals=True,mmap_protection=True,pthread_tls_futex=True,fork_exec=True))]
    terminals=[]
    for i in range(8):
        lines.append('MPC_NATIVE_KMS_PRODUCER '+json.dumps(dict(schema=1,run=NONCE,phase=i*17,resource_id=i+10,width=1280,height=720,
            producer_fence_completed=True,external_queue_release=True,vulkan_format=44,drm_fourcc=875713112,virtio_format=2,
            drm_modifier=0,memory_plane=0,tiling='drm-format-modifier',channel_order='bgra')))
        lines.append('MPC_NATIVE_KMS_FLIP '+json.dumps(dict(schema=1,run=NONCE,index=i,crtc=5,framebuffer=20+i,
            event_count=int(i>0),output_fence_status=1,uart_release_used=False)))
        terminals.append(dict(session=1,command=100+i,reader=1,generation=i+1,resource_id=i+10,actual_metal_status=4,
            actual_metal_error_code=0,gpu_command_submitted=True,engine_terminal_accepted=True))
    lines.append('MPC_NATIVE_KMS_EXIT '+json.dumps(dict(schema=1,run=NONCE,status=0,phases=8,scanout_disabled=True,images_released=True)))
    lines.append('MPC_VK_NATIVE_KMS_RENDER '+json.dumps(dict(machine='aarch64',software=False,width=1280,height=720,shader_phases=8,
        pixels_checked=7372800,mismatches=0,channel_sum=5157519360,validation_enabled=True,synchronization_validation_requested=True,validation_errors=0)))
    lines+=['MPC_LINUX_EXIT=0','MPC_GPU_KERNEL_EXIT=0','MPC_GPU_GUEST_EXIT=0','MPC_NATIVE_KMS_GUEST_EXIT=0']
    native=dict(configured=True,accepted_readers=8,actual_gpu_completed=8,recent_terminals=terminals)
    native.update({k:0 for k in ['actual_gpu_errors','canceled_before_submission','rejected_events','invalid_completions',
        'pending_readers','completion_callbacks_in_progress','retained_backing_bytes','installed_images']})
    return dict(nonce=NONCE,serial='\n'.join(lines)+'\n',native=native)
def mutations(base):
    for key in ['actual_gpu_errors','canceled_before_submission','rejected_events','invalid_completions','pending_readers',
        'completion_callbacks_in_progress','retained_backing_bytes','installed_images']:
        f=copy.deepcopy(base);f['native'][key]=1;yield f
    for key,val in [('resource_id',999),('actual_metal_status',5),('engine_terminal_accepted',False),('gpu_command_submitted',False),
                    ('actual_metal_error_code',1),('session',2),('reader',0),('generation',0),('command',0)]:
        f=copy.deepcopy(base);f['native']['recent_terminals'][3][key]=val;yield f
    f=copy.deepcopy(base);f['native']['recent_terminals'].pop();yield f
    for key in ['generation','command']:
        f=copy.deepcopy(base);f['native']['recent_terminals'][3][key]=f['native']['recent_terminals'][2][key];yield f
    for old,new in [('"output_fence_status": 1','"output_fence_status": 0'),('"event_count": 1','"event_count": 0'),
        ('"producer_fence_completed": true','"producer_fence_completed": false'),('"mismatches": 0','"mismatches": 1'),
        ('"software": false','"software": true'),('"images_released": true','"images_released": false'),
        ('"validation_errors": 0','"validation_errors": 1'),('"resource_id": 10','"resource_id": 11')]:
        f=copy.deepcopy(base);f['serial']=f['serial'].replace(old,new,1);yield f
    f=copy.deepcopy(base);f['nonce']='2'*32;yield f
    f=copy.deepcopy(base);f['serial']+='MPC_NATIVE_KMS_HELD {}\n';yield f
    f=copy.deepcopy(base);f['serial']+='MPC_NATIVE_KMS_FLIP {}\n';yield f
    f=copy.deepcopy(base);f['serial']+='MPC_NATIVE_KMS_GUEST_EXIT=0\n';yield f
if __name__=='__main__':
    b=fixture();pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(valid=b,invalid=list(mutations(b))),indent=2)+'\n')
