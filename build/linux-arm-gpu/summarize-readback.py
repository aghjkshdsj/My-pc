#!/usr/bin/env python3
"""Summarize controlled, account-free GPU CI output using fixed labels only."""
import importlib.util
import json
import pathlib
import sys

spec = importlib.util.spec_from_file_location('readback', pathlib.Path(__file__).with_name('probe-guest.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
folder = pathlib.Path(sys.argv[1])
content = (folder / 'guest/gpu-boot.log').read_text(errors='replace')
print('MYPC_PREVIOUS_GPU_RESULT ' + json.dumps({
    'shader_passed': 'MYPC_GUEST_GPU_SHADER_OK' in content,
    'glx_visual_error': any(term in content for term in ('couldn\'t get an RGB', 'could not get an RGB', 'BadMatch', 'glXCreateContext failed')),
    'traceback_count': content.count('Traceback (most recent call last)'),
    'callback': module.frame_stats(folder / 'guest/gpu-frame.bgra'),
}))
