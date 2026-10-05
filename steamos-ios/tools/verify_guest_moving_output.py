#!/usr/bin/env python3
"""Independently join moving-frame receipts; no device attestation or game FPS."""
import json,math
from verify_device_report import require

def phase(index):return index*17%120
def channel_sum(p):return 720*sum((x+p)&255 for x in range(1280))+1280*sum((y+p)&255 for y in range(720))+921600*((165^p)+255)
def fixed(row,expected,message):
    require(isinstance(row,dict) and all(type(row.get(k)) is type(v) and row[k]==v for k,v in expected.items()),message)
def rows(serial,prefix):
    return [json.loads(line[len(prefix):]) for line in serial.splitlines() if line.startswith(prefix)]

def validate(receipt,serial,nonce):
    fixed(receipt,dict(schema=1,scope='physical-ios-linux-three-buffer-moving-output',run=nonce,
        buffer_reuse_verified=True,production_kms_wsi_verified=False,compositor_verified=False,
        frame_pacing_verified=False,game_fps_verified=False,gameplay_verified=False,
        steady_state_full_image_readbacks=0),'Wrong or incomplete moving scope')
    n=receipt['native'];screen=receipt['screen'];registry=n['registry_id']
    require(type(registry) is int and registry>0,'Wrong native registry')
    fixed(n,dict(schema=1,scope='native-explicit-linux-moving-release',run=nonce,errors=0,finished=True,
        active=False,ledger_drained=True,ledger_faulted=False,pending_consumers=0,reader_joined=True,
        channel_eof=True,diagnostic_full_image_readbacks=2,binary_replies_sent=364,final_submission_fence=240,
        source_release='actual-metal-gpu-terminal-callback',production_kms_wsi_verified=False),'Incomplete native lifecycle')
    fixed(screen,dict(schema=1,scope='native-metal-three-buffer-changing-linux-screen',run=nonce,
        registry_id=registry,errors=0,pending=0,interrupted=False,surface_visible=True,maximum_inflight=1,
        drawable_limit=2,diagnostic_source_readbacks=2,drawable_cpu_readbacks=0),'Incomplete screen lifecycle')
    for key,count in [('buffers',3),('offers',120),('releases',120),('reacquisitions',120),('images',120)]:
        require(isinstance(n[key],list) and len(n[key])==count,'Wrong bounded count: '+key)
    require(isinstance(screen['frames'],list) and len(screen['frames'])==120,'Wrong screen count')
    controls=rows(serial,'MPC_MOVE_CTL ');received=rows(serial,'MPC_MOVE_RELEASE_RECEIVED ')
    require(controls==receipt['guest_controls'] and received==receipt['guest_releases'],'Saved serial and receipts differ')
    require(len(controls)==244 and len(received)==120 and not rows(serial,'MPC_MOVE_REJECTED '),'Wrong guest/control count')
    require(serial.splitlines().count('MPC_MOVE_GUEST_EXIT=0')==1,'Missing guest exit')
    resources=[r['resource_id'] for r in n['buffers']]
    require(len(set(resources))==3 and all(type(r) is int and r>0 for r in resources),'Resources are not three distinct identities')
    leases={};fence=0;offer_index=0;acquire_index=0;drained=set()
    for i,row in enumerate(controls):
        fixed(row,dict(schema=1,run=nonce),'Stale control')
        if i<3:
            fixed(row,dict(type='register',slot=i,resource_id=resources[i],incarnation=1,width=1280,height=720,format=80),'Wrong registration')
            require(all(n['buffers'][i].get(k)==v for k,v in row.items()),'Native registration differs')
        elif row['type']=='offer':
            require(offer_index<120,'Offer overflow');fence+=1;r=resources[offer_index%3];serial_id=offer_index+1
            fixed(row,dict(resource_id=r,incarnation=1,serial=serial_id,phase=phase(offer_index),producer_fence=fence,
                producer_fence_completed=True,external_queue_release=True),'Wrong producer fence or content')
            require(r not in leases,'Guest reused a buffer before reacquisition');leases[r]=serial_id
            offer=n['offers'][offer_index]
            require(all(type(offer.get(k)) is type(v) and offer[k]==v for k,v in row.items()),'Native offer differs')
            fixed(offer,dict(native_consumed=True,release_sent=True,terminal_status=4,terminal_error=False),'Missing native consumer')
            offer_index+=1
        elif row['type']=='reacquired':
            fence+=1;r=row['resource_id'];serial_id=row['serial']
            require(leases.get(r)==serial_id and serial_id not in drained,'Stale or duplicate acquire')
            fixed(row,dict(incarnation=1,release=serial_id,acquire_fence=fence,acquire_fence_completed=True),'Wrong acquisition fence')
            require(acquire_index<120 and row==n['reacquisitions'][acquire_index],'Acquire receipt differs')
            del leases[r];drained.add(serial_id);acquire_index+=1
        else:
            fixed(row,dict(type='finish',frames=120,buffers=3),'Unknown control')
            require(i==243 and not leases,'Finish with live buffers')
    require(offer_index==acquire_index==len(drained)==120 and fence==240,'Undrained moving schedule')
    events=n['events'];require(isinstance(events,list) and 360<=len(events)<=2048,'Unbounded native events')
    active=None;generation=0;installs={};flushed=set()
    for index,event in enumerate(events,1):
        fixed(event,dict(sequence=index),'Event order');g=event['generation'];r=event['resource_id']
        if event['kind']==1:
            require(active is None and type(g) is int and g>generation and r in resources,'Install order')
            active=(g,r);generation=g;installs[g]=r
        elif event['kind'] in (2,3):
            require(active==(g,r),'Wrong active event identity')
            if event['kind']==2:flushed.add(g)
            else:active=None
        else:raise ValueError('Unknown native event')
    require(active is None and len(installs)==len(flushed)==120,'Incomplete generation lifecycle')
    generations=set();drawable_ids=set();total_pixels=0;total_sum=0;missing=0;previous=0
    for i,(image,draw,release,guest) in enumerate(zip(n['images'],screen['frames'],n['releases'],received)):
        serial_id=i+1;p=phase(i);r=resources[i%3];g=image['generation'];endpoint=i in(0,119)
        require(g in flushed and g not in generations and installs[g]==r and n['offers'][i]['generation']==g,'Wrong frame generation')
        generations.add(g)
        fixed(image,dict(serial=serial_id,incarnation=1,resource_id=r,phase=p,width=1280,height=720,
            native_registry_id=registry,native_pixel_format=80,virtio_format=2,channel_order='bgra',
            native_buffer_alias_verified=True,pixel_verification_performed=endpoint,
            pixels_checked=921600 if endpoint else 0,mismatches=0,channel_sum=channel_sum(p) if endpoint else 0),'Wrong native source/pixels')
        stride=image['row_pitch'];offset=image['offset'];size=image['backing_bytes'];align=image['linear_alignment']
        require(all(type(x) is int for x in (stride,offset,size,align)) and 5120<=stride<=1<<20 and 0<align<=65536 and not align&(align-1)
            and stride%align==offset%align==0 and 0<=offset<=size<=64*1024*1024 and stride*720<=size-offset,'Invalid native memory layout')
        require(stride==n['buffers'][i%3]['row_pitch'] and offset==n['buffers'][i%3]['offset'],'Alias layout differs')
        if endpoint:fixed(image,dict(endpoint_consumer_status=4,endpoint_consumer_error=False),'Endpoint GPU failed')
        fixed(draw,dict(resource_id=r,generation=g,phase=p,frame_index=serial_id,source_registry_id=registry,
            drawable_registry_id=registry,source_is_imported_guest_texture=True,source_width=1280,source_height=720,
            source_pixel_format=80,drawable_pixel_format=80,gpu_submitted=True,gpu_completed=True,consumer_status=4,
            consumer_error=False,completion_join_retired=True,drawable_presented=True,presents_with_transaction=True,
            presentation_on_main_thread=True,presentation_application_state=0,presentation_call_completed=True),'Incomplete screen draw')
        require('error' not in image and 'error' not in draw and draw.get('presentation_aborted') is not True,'Screen error')
        require(type(draw['drawable_id']) is int and draw['drawable_id']>0,'Missing drawable identity')
        drawable_ids.add(draw['drawable_id'])
        start,end=draw['gpu_start_seconds'],draw['gpu_end_seconds']
        require(all(type(v) in (int,float) and math.isfinite(v) for v in (start,end)) and 0<start<=end,'Invalid screen GPU timing')
        shown=draw.get('presented_seconds',0)
        if type(shown) not in (int,float) or not math.isfinite(shown) or shown<=max(previous,0) or shown<end:missing+=1
        if type(shown) in (int,float) and math.isfinite(shown) and shown>0:previous=shown
        fixed(release,dict(serial=serial_id,incarnation=1,resource_id=r,release=serial_id,status=4,
            has_error=False,registry_id=registry,wire_sent=True,actual_gpu_terminal_callback=True),'Wrong native release')
        fixed(guest,dict(schema=1,run=nonce,serial=serial_id,incarnation=1,resource_id=r,release=serial_id,
            code=4,native_registry_id=registry),'Guest did not receive matching release')
        total_pixels+=image['pixels_checked'];total_sum+=image['channel_sum']
    render=rows(serial,'MPC_VK_MOVING_RENDER ');exit=rows(serial,'MPC_MOVE_EXIT ');base=rows(serial,'MPC_VK_DIAGNOSTIC ')
    require(len(render)==len(exit)==len(base)==1 and exit==receipt['guest_exits'] and render[0]==receipt['guest_render'],'Render/exit differs from serial')
    fixed(exit[0],dict(schema=1,run=nonce,status=0,frames=120,buffers=3,scanout_disabled=True,images_released=True),'Missing cleanup')
    fixed(render[0],dict(machine='aarch64',shader_phases=120,pixels_checked=1843200,width=1280,height=720,
        mismatches=0,validation_errors=0,software=False,metal_host_verified=False,presentation_verified=False,game_fps_verified=False,
        channel_sum=total_sum),'Wrong guest shader endpoint result')
    require(render[0]['device_type'] in (1,2,3) and all(render[0].get(k)==base[0].get(k) for k in ('renderer','api_version','driver_version','vendor_id','device_id','device_type')),'Guest GPU identity differs')
    fixed(receipt,dict(pixels_checked=total_pixels,channel_sum=total_sum,missing_or_nonmonotonic_display_timestamps=missing,
        presentation_verified=missing==0),'Reported timing/pixel verdict differs')
    require(total_pixels==1843200 and total_sum==channel_sum(0)+channel_sum(phase(119)),'Endpoint checksum differs')
    return dict(scope='three-buffer-moving-receipt-consistency-only',buffer_reuse_verified=True,presentation_verified=missing==0,
        frames=120,buffers=3,buffer_reuses=117,reacquisitions=120,endpoint_pixels=total_pixels,
        game_fps_verified=False,production_kms_wsi_verified=False,cryptographic_device_attestation=False)
