#!/usr/bin/env python3
"""Independently audit private standard-KMS phone reports without uploading them.

Reported observations are not signed hardware attestation. Never infer desktop,
Steam, game FPS or positive display timestamps from this bounded ownership gate.
"""
import argparse
import json
import math
import pathlib
import re
from bundle_native_kms import ENGINE_RUN,ENGINE_SOURCE,GUEST_RUN,GUEST_SOURCE,FILES,ENGINE_CODE
def require(condition,reason):
    if not condition:raise ValueError(reason)
def integer(value,positive=False):
    return type(value) is int and (1 if positive else 0)<=value<=0xffffffffffffffff
def row_list(text,prefix):
    result=[]
    for line in text.splitlines():
        if not line.startswith(prefix):continue
        value=json.loads(line[len(prefix):]);require(type(value) is dict,'Invalid '+prefix+' row');result.append(value)
    return result
def audit(report,expected_source):
    require(type(report) is dict and report.get('scope')=='private-native-kms-device-test','Wrong private report scope')
    require(report.get('build')=='4000028' and report.get('source_commit')==expected_source,'Wrong package build/source')
    run=report.get('test');require(type(run) is dict,'Missing actual Linux test')
    require(run.get('source_commit')==expected_source and run.get('scope')=='standard-linux-kms-native-metal-completion-join','Wrong test/source')
    require(run.get('status')=='passed' and run.get('standard_kms_native_completion_verified') is True,'App did not accept joined path')
    require(run.get('hardware_virtualization') is False,'Unsupported virtualization claim')
    for key in ['engine_finished','engine_worker_joined','engine_init_thread_rcu_unregistered','linux_execution']:
        require(run.get(key) is True,'Missing '+key)
    require(type(run.get('engine_status')) is int and run['engine_status']==0,'Engine failed')
    nonce=run.get('run');require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce),'Invalid nonce')
    device=run.get('device',{})
    require(device.get('device_machine')=='iPhone16,2' and device.get('ios_version')=='27.0.1' and device.get('os_build')=='24A446','Unexpected target device/OS')
    payload=run.get('payload',{});bundle=run.get('engine_bundle',{})
    require(payload.get('files')==FILES and payload.get('source_commit')==GUEST_SOURCE and int(payload.get('workflow_run',0))==GUEST_RUN,'Wrong actual payload provenance')
    require(bundle.get('scope')=='bundled-ios-standard-kms-native-completion' and bundle.get('completion_abi')==2,'Wrong engine variant')
    require((bundle.get('engine_run'),bundle.get('engine_source'),bundle.get('guest_run'),bundle.get('guest_source'))==
        (ENGINE_RUN,ENGINE_SOURCE,GUEST_RUN,GUEST_SOURCE),'Wrong exact upstream builds')
    engine=bundle.get('engine_receipt',{})
    require(engine.get('audit')==dict(abi=2,exported_definitions_verified=True,actual_patched_sources_verified=True,
        physical_ios_compiled=True,metal_join_runtime_verified=False,phone_tested=False),'Wrong engine build audit')
    require(engine.get('base_engine',{}).get('files',{}).get('sysroot-iOS-arm64/Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu',{}).get('sha256')==ENGINE_CODE,'Wrong engine code')
    text=run.get('serial_output');require(type(text) is str and 0<len(text)<2*1024*1024,'Missing/bounded serial output')
    lines=text.splitlines()
    for exact in ['MPC_GPU_GUEST_RUN='+nonce,'MPC_LINUX_EXIT=0','MPC_GPU_KERNEL_EXIT=0','MPC_GPU_GUEST_EXIT=0','MPC_NATIVE_KMS_GUEST_EXIT=0']:
        require(lines.count(exact)==1,'Missing/duplicated '+exact)
    require(not any(p in text for p in ['MPC_NATIVE_KMS_HELD ','MPC_NATIVE_KMS_REJECTED ','MPC_VK_REJECTED ']),'Guest retained/failed ownership')
    abi=row_list(text,'MPC_LINUX_ABI ');require(len(abi)==1,'ABI count')
    a=abi[0];require(all(a.get(k)==v for k,v in dict(schema=1,run=nonce,kernel='6.12.111',machine='aarch64',elf_arch='aarch64',page_bytes=4096,failures=0,checksum='1d250c45a7bbc87e').items()),'Wrong ABI result')
    require(all(a.get(k) is True for k in ['signals','mmap_protection','pthread_tls_futex','fork_exec']),'Failed ABI mechanisms')
    producers=row_list(text,'MPC_NATIVE_KMS_PRODUCER ');flips=row_list(text,'MPC_NATIVE_KMS_FLIP ')
    require(len(producers)==len(flips)==8,'Missing/extra producer or flip')
    native=run.get('native',{});terminals=native.get('recent_terminals',[])
    require(type(terminals) is list and len(terminals)==8,'Missing/extra Metal terminal')
    require(native.get('configured') is True,'Native consumer unconfigured')
    for key in ['accepted_readers','actual_gpu_completed']:require(type(native.get(key)) is int and native[key]==8,'Wrong '+key)
    for key in ['actual_gpu_errors','canceled_before_submission','rejected_events','invalid_completions','pending_readers',
        'completion_callbacks_in_progress','retained_backing_bytes','installed_images']:
        require(type(native.get(key)) is int and native[key]==0,'Outstanding/failed '+key)
    require(all(type(t) is dict for t in terminals),'Malformed terminal')
    sessions={t.get('session') for t in terminals};require(len(sessions)==1 and integer(next(iter(sessions)),True),'Wrong native session')
    tickets=set();generations=set();resources=set();framebuffers=set();crtc=None
    for index,(producer,flip) in enumerate(zip(producers,flips)):
        require(producer.get('schema')==1 and producer.get('run')==nonce and producer.get('phase')==index*17,'Stale or unordered producer')
        require(all(producer.get(k)==v for k,v in dict(width=1280,height=720,tiling='drm-format-modifier',drm_modifier=0,
            memory_plane=0,vulkan_format=44,drm_fourcc=875713112,virtio_format=2,channel_order='bgra').items()),'Wrong exported image layout')
        require(producer.get('producer_fence_completed') is True and producer.get('external_queue_release') is True,'Incomplete Vulkan producer')
        resource=producer.get('resource_id');require(integer(resource,True) and resource not in resources,'Duplicated resource');resources.add(resource)
        matches=[t for t in terminals if t.get('resource_id')==resource];require(len(matches)==1,'Missing/duplicate native resource')
        t=matches[0]
        require(t.get('gpu_command_submitted') is True and t.get('engine_terminal_accepted') is True and t.get('actual_metal_status')==4 and t.get('actual_metal_error_code')==0,'Nonterminal/error/canceled Metal read')
        for key in ['command','reader','generation']:require(integer(t.get(key),True),'Invalid token '+key)
        ticket=(t['session'],t['command'],t['reader']);require(ticket not in tickets and t['generation'] not in generations,'Duplicate reader/generation');tickets.add(ticket);generations.add(t['generation'])
        require(flip.get('schema')==1 and flip.get('run')==nonce and flip.get('index')==index and flip.get('event_count')==int(index>0),'Wrong Linux flip event')
        require(type(flip.get('output_fence_status')) is int and flip['output_fence_status']==1 and flip.get('uart_release_used') is False,'Missing positive standard output fence')
        require(integer(flip.get('framebuffer'),True) and flip['framebuffer'] not in framebuffers,'Duplicate framebuffer');framebuffers.add(flip['framebuffer'])
        if crtc is None:crtc=flip.get('crtc')
        require(integer(crtc,True) and flip.get('crtc')==crtc,'Wrong CRTC')
    cleanup=row_list(text,'MPC_NATIVE_KMS_EXIT ');render=row_list(text,'MPC_VK_NATIVE_KMS_RENDER ')
    require(len(cleanup)==len(render)==1,'Missing/extra cleanup/render')
    require(all(cleanup[0].get(k)==v for k,v in dict(schema=1,run=nonce,status=0,phases=8).items()) and
        cleanup[0].get('scanout_disabled') is True and cleanup[0].get('images_released') is True,'Incomplete Linux teardown')
    r=render[0]
    require(all(r.get(k)==v for k,v in dict(machine='aarch64',width=1280,height=720,shader_phases=8,pixels_checked=7372800,
        mismatches=0,channel_sum=5157519360,validation_errors=0).items()),'Failed Linux rendered pixels')
    require(r.get('software') is False and r.get('validation_enabled') is True and r.get('synchronization_validation_requested') is True,'Software/unvalidated producer')
    trace=run.get('guest_metal_trace',{})
    require(trace.get('scope')=='native-moltenvk-guest-command-completion' and trace.get('run')==nonce,'Unbound guest Metal observer')
    require(trace.get('observer_configured') is True and trace.get('callbacks_drained') is True and trace.get('metal_host_verified') is True and trace.get('adds_gpu_work') is False,'Incomplete real guest Metal trace')
    for key in ['pending','failed','overflow','unknown_callbacks','duplicate_callbacks','identity_errors','initial_errors','invalid_timing']:
        require(type(trace.get(key)) is int and trace[key]==0,'Failed observer '+key)
    samples=trace.get('samples',[]);require(type(samples) is list and len(samples)>0 and trace.get('completed')==len(samples)==trace.get('observed_commit_points'),'Missing actual observer samples')
    require(all(s.get('completion_observed') is True and s.get('status')==4 and s.get('has_error') is False and s.get('error_code')==0 for s in samples),'Failed guest GPU sample')
    expected_device=device.get('metal_device');require(type(expected_device) is str and expected_device and trace.get('expected_device_name')==expected_device,'Wrong observed GPU')
    registries={s.get('device_registry_id') for s in samples};require(len(registries)==1 and integer(next(iter(registries)),True),'Changed guest GPU device')
    tokens=set();timed=0
    for s in samples:
        require(integer(s.get('token'),True) and s['token'] not in tokens and s.get('device_name')==expected_device,'Wrong observer token/device');tokens.add(s['token'])
        start=s.get('gpu_start_seconds');end=s.get('gpu_end_seconds')
        require(type(start) in [int,float] and type(end) in [int,float] and math.isfinite(start) and math.isfinite(end) and 0<=start<=end,'Invalid guest GPU timing')
        timed+=start>0 and end>start
    require(timed>=2 and trace.get('timed_completions')==timed,'Incomplete actual guest GPU timing')
    return dict(schema=1,scope='independent-private-device-standard-kms-completion-audit',source_commit=expected_source,
        build='4000028',reported_target_device_and_os_matched=True,eight_linux_kms_native_completion_joins_verified=True,
        immutable_resources=8,positive_output_fences=8,matching_page_flip_events=7,actual_metal_reader_completions=8,
        engine_same_worker_retirement_and_join_verified=True,display_timing_verified=False,desktop_verified=False,
        steam_verified=False,gameplay_verified=False,game_fps_verified=False,hardware_virtualization=False)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=pathlib.Path);p.add_argument('expected_source')
    p.add_argument('--output',type=pathlib.Path);a=p.parse_args();result=audit(json.loads(a.report.read_text()),a.expected_source)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(text)
    print(text)
