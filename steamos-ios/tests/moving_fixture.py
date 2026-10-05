"""Synthetic receipt oracle for rejection tests. It never constitutes GPU proof."""
import copy,json
NONCE='0123456789abcdef0123456789abcdef'
def phase(i):return i*17%120
def channel_sum(p):
    return 720*sum((x+p)&255 for x in range(1280))+1280*sum((y+p)&255 for y in range(720))+921600*((165^p)+255)
def fixture():
    buffers=[];offers=[];releases=[];acquires=[];images=[];draws=[];controls=[];received=[];events=[];fence=0
    for i in range(3):
        row=dict(schema=1,type='register',run=NONCE,slot=i,resource_id=7+i,incarnation=1,width=1280,height=720,format=80,row_pitch=5120,offset=0,backing_bytes=3686400)
        controls.append(row);buffers.append(dict(row,last_generation=118+i,serial=118+i,release=118+i))
    def acquire(serial):
        nonlocal fence
        fence+=1
        row=dict(schema=1,type='reacquired',run=NONCE,resource_id=7+(serial-1)%3,serial=serial,incarnation=1,release=serial,acquire_fence=fence,acquire_fence_completed=True)
        controls.append(row);acquires.append(row)
    for i in range(120):
        n=i+1;r=7+i%3;p=phase(i);endpoint=i in(0,119)
        if i>=3:acquire(n-3)
        fence+=1
        offer=dict(schema=1,type='offer',run=NONCE,resource_id=r,incarnation=1,serial=n,phase=p,producer_fence=fence,producer_fence_completed=True,external_queue_release=True)
        controls.append(offer);offers.append(dict(offer,native_consumed=True,release_sent=True,generation=n,terminal_status=4,terminal_error=False))
        releases.append(dict(serial=n,incarnation=1,resource_id=r,release=n,status=4,has_error=False,registry_id=99,wire_sent=True,actual_gpu_terminal_callback=True,host_seconds=10+n))
        received.append(dict(schema=1,run=NONCE,serial=n,incarnation=1,resource_id=r,release=n,code=4,native_registry_id=99))
        image=dict(serial=n,incarnation=1,resource_id=r,generation=n,phase=p,width=1280,height=720,row_pitch=5120,offset=0,backing_bytes=3686400,linear_alignment=512,native_pixel_format=80,native_registry_id=99,virtio_format=2,channel_order='bgra',native_buffer_alias_verified=True,pixel_verification_performed=endpoint,pixels_checked=921600 if endpoint else 0,channel_sum=channel_sum(p) if endpoint else 0,mismatches=0)
        if endpoint:image.update(endpoint_consumer_status=4,endpoint_consumer_error=False)
        images.append(image)
        draw=dict(resource_id=r,generation=n,phase=p,frame_index=n,source_registry_id=99,drawable_registry_id=99,source_is_imported_guest_texture=True,source_width=1280,source_height=720,source_pixel_format=80,drawable_pixel_format=80,gpu_submitted=True,gpu_completed=True,consumer_status=4,consumer_error=False,completion_join_retired=True,drawable_presented=True,presents_with_transaction=True,presentation_on_main_thread=True,presentation_application_state=0,presentation_call_completed=True,drawable_id=n,gpu_start_seconds=10+n,gpu_end_seconds=10.001+n,presented_seconds=10.01+n)
        draws.append(draw)
        if i:events.append(dict(kind=3,sequence=len(events)+1,generation=n-1,resource_id=7+(i-1)%3))
        events.append(dict(kind=1,sequence=len(events)+1,generation=n,resource_id=r))
        events.append(dict(kind=2,sequence=len(events)+1,generation=n,resource_id=r))
    for n in range(118,121):acquire(n)
    controls.append(dict(schema=1,type='finish',run=NONCE,frames=120,buffers=3))
    events.append(dict(kind=3,sequence=len(events)+1,generation=120,resource_id=9))
    base=dict(machine='aarch64',renderer='synthetic-gpu-fixture',api_version=1,driver_version=2,vendor_id=3,device_id=4,device_type=2)
    render=dict(base,shader_phases=120,pixels_checked=1843200,width=1280,height=720,mismatches=0,validation_errors=0,software=False,metal_host_verified=False,presentation_verified=False,game_fps_verified=False,channel_sum=channel_sum(0)+channel_sum(phase(119)))
    exit=dict(schema=1,run=NONCE,frames=120,buffers=3,status=0,scanout_disabled=True,images_released=True,presentation_verified=False)
    cap=dict(schema=1,run=NONCE,result=0,tiling='drm-format-modifier',drm_modifier=0,external_features=2,compatible_handles=512,max_width=1280,max_height=720)
    lines=['MPC_VK_DIAGNOSTIC '+json.dumps(base),'MPC_MOVE_CAPABILITIES '+json.dumps(cap)]
    for row in controls:
        lines.append('MPC_MOVE_CTL '+json.dumps(row))
        if row['type']=='offer':lines.append('MPC_MOVE_RELEASE_RECEIVED '+json.dumps(received[row['serial']-1]))
    lines+=['MPC_MOVE_EXIT '+json.dumps(exit),'MPC_VK_MOVING_RENDER '+json.dumps(render),'MPC_MOVE_GUEST_EXIT=0']
    native=dict(schema=1,scope='native-explicit-linux-moving-release',run=NONCE,registry_id=99,buffers=buffers,offers=offers,releases=releases,reacquisitions=acquires,images=images,events=events,errors=0,finished=True,active=False,ledger_drained=True,ledger_faulted=False,pending_consumers=0,reader_joined=True,channel_eof=True,diagnostic_full_image_readbacks=2,repeated_flushes_skipped=0,binary_replies_sent=364,final_submission_fence=240,source_release='actual-metal-gpu-terminal-callback',production_kms_wsi_verified=False)
    screen=dict(schema=1,scope='native-metal-three-buffer-changing-linux-screen',run=NONCE,registry_id=99,frames=draws,errors=0,pending=0,interrupted=False,surface_visible=True,surface_geometry=1,maximum_inflight=1,drawable_limit=2,lifecycle_events=[],diagnostic_source_readbacks=2,drawable_cpu_readbacks=0)
    return copy.deepcopy(dict(nonce=NONCE,native=native,screen=screen,serial='\n'.join(lines)+'\n'))
if __name__=='__main__':
    import pathlib,sys
    pathlib.Path(sys.argv[1]).write_text(json.dumps(fixture()),encoding='utf-8')
