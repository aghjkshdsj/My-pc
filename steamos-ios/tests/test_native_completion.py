"""Reject incomplete ABI2 build receipts; execute real adapter with a CPU shim."""
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
PROJECT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'tools'))
from collect_completion_engine_sources import audit_completion
from patch_qemu_native_completion import PINS, patch

class NativeCompletionTests(unittest.TestCase):
    def test_incomplete_export_or_source_rejected(self):
        exports='0001 T _mpc_qemu_configure_native_completion\n0002 T _mpc_qemu_complete_native_read\n'
        commands=[{'file':'../'+n,'command':'clang -c ../'+n} for n in
            ('ui/egl-headless.c','hw/display/virtio-gpu.c','hw/display/virtio-gpu-gl.c','hw/display/virtio-gpu-virgl.c')]
        source={'scope':'native-completion-adapter-source-only','abi':2,
            'files':{'ui/egl-headless.c':{'patched_sha256':'a'*64}}}
        actual={'ui/egl-headless.c':'a'*64}
        self.assertFalse(audit_completion(exports,commands,source,actual)['metal_join_runtime_verified'])
        for bad in ('0001 U _mpc_qemu_configure_native_completion\n0002 T _mpc_qemu_complete_native_read\n',
                    exports.replace(' T ',' t '),exports.splitlines()[0]):
            with self.assertRaises(AssertionError):audit_completion(bad,commands,source,actual)
        with self.assertRaises(AssertionError):audit_completion(exports,commands[:-1],source,actual)
        with self.assertRaises(AssertionError):audit_completion(exports,commands,source,{'ui/egl-headless.c':'b'*64})
        with self.assertRaises(AssertionError):audit_completion(exports,commands,{**source,'abi':1},actual)

    def test_unknown_source_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory(dir=PROJECT/'out',prefix='completion-rejection-') as d:
            root=pathlib.Path(d)
            for n in PINS:
                p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('unsupported source')
            before={n:(root/n).read_bytes() for n in PINS}
            with self.assertRaises(ValueError):patch(root,root)
            self.assertEqual(before,{n:(root/n).read_bytes() for n in PINS})
            self.assertFalse((root/'native-completion-source.json').exists())

    def test_actual_adapter_cpu_control(self):
        compiler=shutil.which('clang') or shutil.which('cc')
        if not compiler:
            if os.environ.get('MPC_REQUIRE_COMPLETION_CPU_CONTROL')=='1':self.fail('Required C compiler unavailable')
            self.skipTest('Local C compiler unavailable; required hosted control remains pending')
        with tempfile.TemporaryDirectory(dir=PROJECT/'out',prefix='completion-cpu-control-') as d:
            root=pathlib.Path(d)
            for name in ['qemu/main-loop.h','qemu/thread.h','system/bql.h','hw/virtio/virtio-gpu.h']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* CPU executor shim */\n')
            (root/'ui').mkdir()
            for src,dst in [('NativeCompletionLedger.h','mpc-native-completion-ledger.h')]:
                text=(PROJECT/'Engine'/src).read_text().replace('"NativeCompletionABI.h"',
                    '"'+(PROJECT/'Engine/NativeCompletionABI.h').as_posix()+'"')
                (root/'ui'/dst).write_text(text)
            for sanitized in (False,True):
                exe=root/('control-sanitized' if sanitized else 'control')
                command=[compiler,'-std=c11','-Wall','-Wextra','-Werror','-pthread','-I'+str(root),
                    str(PROJECT/'tests/native_completion_control.c'),'-o',str(exe)]
                if sanitized:command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g']
                subprocess.run(command,check=True,capture_output=True,text=True)
                result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=15)
                self.assertIn('MPC_NATIVE_COMPLETION_CPU_CONTROL passed',result.stdout)
                print(result.stdout.strip()+(' [ASan/UBSan]' if sanitized else ' [normal]'))

if __name__=='__main__':unittest.main()
