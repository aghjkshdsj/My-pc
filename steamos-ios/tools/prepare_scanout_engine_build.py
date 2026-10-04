#!/usr/bin/env python3
"""Fresh native scanout variant, derived from the source-pinned GPU engine."""
import argparse
import hashlib
import json
import pathlib
from prepare_gpu_engine_build import prepare_gpu


def prepare(output):
    prepare_gpu(output)
    path = output / 'scripts/build_gpu_gate.sh'
    source = path.read_text(encoding='utf-8')
    anchor = '" "$QEMU_DIR" "$PWD"\nbuild $QEMU_DIR'
    assert source.count(anchor) == 1
    tool = pathlib.Path(__file__).with_name('patch_qemu_native_scanout.py')
    source = source.replace(anchor, '" "$QEMU_DIR" "$PWD"\npython3 "' + str(tool) +
                            '" "$QEMU_DIR" "$PWD"\nbuild $QEMU_DIR')
    path.write_text(source, encoding='utf-8')
    receipt_path = output / 'recipe-receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt['derived_sha256'] = hashlib.sha256(source.encode()).hexdigest()
    receipt['adapter_scope'] = 'native borrowed-image scanout diagnostic; presentation still required'
    receipt['native_scanout_abi_requested'] = 1
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=pathlib.Path)
    prepare(parser.parse_args().output.resolve())
