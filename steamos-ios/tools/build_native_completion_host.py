#!/usr/bin/env python3
"""Compile the standalone asynchronous consumer for device iOS; no IPA claim."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tarfile
from verify_ipa import macho_platform
PROJECT=pathlib.Path(__file__).resolve().parents[1]
def run(args):
    subprocess.run(args,check=True)
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def shader_source(source):
    start=source.index('NSString *source=@"')+len('NSString *source=')
    end=source.index('\n    NSError *buildError',start)
    literals=re.findall(r'@?"(?:[^"\\]|\\.)*"',source[start:end])
    assert literals and source[start:end].strip().endswith(';')
    return ''.join(json.loads(s.removeprefix('@')) for s in literals)
def build(output):
    output.mkdir(parents=True,exist_ok=True)
    sdk=subprocess.check_output(['xcrun','--sdk','iphoneos','--show-sdk-path'],text=True).strip()
    host=PROJECT/'Host/NativeDisplayCompletion.mm'
    dylib=output/'MPCNativeDisplayCompletion.dylib'
    command=['xcrun','--sdk','iphoneos','clang++','-target','arm64-apple-ios26.0',
        '-isysroot',sdk,'-std=c++17','-fobjc-arc','-Wall','-Wextra','-Werror',
        '-dynamiclib',str(host),'-framework','Foundation','-framework','Metal',
        '-framework','QuartzCore','-install_name','@rpath/MPCNativeDisplayCompletion.dylib','-o',str(dylib)]
    run(command)
    imports=macho_platform(dylib.read_bytes(),6)
    assert not any('/PrivateFrameworks/' in n or 'Hypervisor' in n or 'IOKit' in n for n in imports)
    symbols=subprocess.check_output(['xcrun','nm','-gU',str(dylib)],text=True)
    for name in ['MPCNativeDisplayCompletionBegin','MPCNativeDisplayCompletionReport']:
        assert re.search(r'^[0-9a-fA-F]+[ \t]+T[ \t]+_'+name+r'[ \t]*$',symbols,re.M),name
    shader=output/'NativeDisplayShader.metal'
    shader.write_text(shader_source(host.read_text()),encoding='utf-8')
    run(['xcrun','--sdk','iphoneos','metal','-c',str(shader),'-o',str(output/'NativeDisplayShader.air')])
    run(['xcrun','--sdk','iphoneos','metallib',str(output/'NativeDisplayShader.air'),'-o',str(output/'NativeDisplayShader.metallib')])
    receipt={'schema':1,'scope':'native-completion-host-device-ios-compile-only',
        'source_commit':os.environ.get('GITHUB_SHA'),'workflow_run':os.environ.get('GITHUB_RUN_ID'),
        'physical_ios_arm64':True,'defined_exports_verified':True,'shader_offline_compiled':True,
        'phone_tested':False,'producer_dependency_verified':False,'metal_join_runtime_verified':False,
        'desktop_verified':False,'gameplay_verified':False,'imports':imports,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in [dylib,shader,output/'NativeDisplayShader.metallib']}}
    (output/'native-completion-host-build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(output/'Native-Completion-Host-Source.tar.gz','w:gz') as t:
        for name in ['Host/NativeDisplayCompletion.h','Host/NativeDisplayCompletion.mm',
                     'Engine/NativeCompletionABI.h','Engine/NativeScanoutABI.h','tools/build_native_completion_host.py',
                     'tools/verify_ipa.py','docs/NATIVE-DISPLAY-COMPLETION.md']:
            t.add(PROJECT/name,arcname=name)
        t.add(PROJECT.parent/'.github/workflows/steamos-ios-completion-host.yml',arcname='steamos-ios-completion-host.yml')
        t.add(shader,arcname='extracted-exact-inline-shader.metal')
        t.add(output/'native-completion-host-build.json',arcname='native-completion-host-build.json')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=pathlib.Path)
    build(parser.parse_args().output.resolve())
