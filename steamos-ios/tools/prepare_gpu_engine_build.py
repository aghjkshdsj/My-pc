#!/usr/bin/env python3
"""Derive a separate GPU QEMU engine recipe; retain the verified CPU recipe."""
import argparse
import hashlib
import json
import pathlib

from prepare_engine_build import prepare


def prepare_gpu(output):
    assert not output.exists(), 'Fresh GPU engine output required'
    prepare(output)
    source = (output / 'scripts/build_cpu_gate.sh').read_text(encoding='utf-8')
    assert source.count('--disable-opengl --disable-virglrenderer') == 1
    source = source.replace('--disable-opengl --disable-virglrenderer', '--enable-opengl --enable-virglrenderer')
    original = 'build_qemu_dependencies\nbuild $QEMU_DIR --cross-prefix=""'
    assert source.count(original) == 1
    tools = pathlib.Path(__file__).resolve().parent
    source = source.replace(original, 'build_qemu_dependencies\n'
                            'test -n "$MPC_GPU_RENDERER_ARTIFACT"\n'
                            'python3 "' + str(tools / 'stage_gpu_engine.py') + '" "$MPC_GPU_RENDERER_ARTIFACT" "$PREFIX"\n'
                            'python3 "' + str(tools / 'patch_qemu_gpu.py') + '" "$QEMU_DIR" "$PWD"\n'
                            'build $QEMU_DIR --cross-prefix=""')
    assert '--enable-hvf-private' not in source and '--disable-hvf' in source
    derived = output / 'scripts/build_gpu_gate.sh'
    derived.write_text(source, encoding='utf-8')
    receipt_path = output / 'recipe-receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt.update(scope='upstream-engine-build-recipe-with-fresh-gpu-adapter', gpu_support=True,
                   derived_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   adapter_scope='headless-diagnostic-only; native paced presentation still required',
                   linux_graphics_verified=False, metal_runtime_verified=False, presentation_verified=False)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(derived)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=pathlib.Path)
    prepare_gpu(parser.parse_args().output.resolve())
