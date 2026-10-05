#!/usr/bin/env python3
"""Derive a separate standard KMS producer; preserve all accepted guest sources."""
import argparse
import hashlib
import json
import pathlib
PROJECT=pathlib.Path(__file__).resolve().parents[1]
PINS={'Guest/vk_gate.c':'356be7439e38db5e927acdb0126fa2ef9ba4375e8b1e7c8db74f5141207437fd',
      'Guest/image_scanout.h':'7c19d495058fc83a4db3f9fe5475e7d51b4a95d375b94b6fe26839ccab1b585b'}
def once(text,old,new):
    assert text.count(old)==1,old[:80]
    return text.replace(old,new)
def prepare(output):
    originals={n:(PROJECT/n).read_text() for n in PINS}
    for n,pin in PINS.items():assert hashlib.sha256(originals[n].encode()).hexdigest()==pin,n
    source=once(originals['Guest/vk_gate.c'],'#include "image_scanout.h"','#include "native_kms_images.h"')
    images=once(originals['Guest/image_scanout.h'],'static int image_install(',
                '#include "native_atomic_scanout.h"\nstatic int image_install(')
    start=images.index('    if (drmModeSetCrtc(scanout_fd, scanout_crtc, target->framebuffer')
    end=images.index('\n    return 0;\n}',start)
    images=images[:start]+'    return native_present(target->framebuffer,pass);'+images[end:].replace('\n    return 0;','',1)
    images=once(images,'    if (drmModeSetCrtc(scanout_fd, scanout_crtc, 0, 0, 0, NULL, 0, NULL))\n'
        '        return image_reject("drm-disable", errno);','    if (native_disable()) return 21;')
    assert 'drmModeSetCrtc' not in images and 'drmModeDirtyFB' not in images and 'nanosleep' not in images
    assert 'frame_release_channel' not in source+images
    output.mkdir(parents=True,exist_ok=False)
    for name,text in [('vk_native_kms_gate.c',source),('native_kms_images.h',images)]:
        (output/name).write_text(text,encoding='utf-8',newline='\n')
    receipt={'schema':1,'scope':'standard-kms-vulkan-producer-source-only','parent_files':PINS,
        'files':{n:hashlib.sha256((output/n).read_bytes()).hexdigest() for n in ['vk_native_kms_gate.c','native_kms_images.h']},
        'uart_release_used':False,'linux_compiled':False,'phone_tested':False,'native_completion_verified':False}
    (output/'native-kms-producer-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=pathlib.Path)
    prepare(parser.parse_args().output.resolve())
