#!/usr/bin/env python3
"""Derive a separate native completion engine; preserve the accepted engine."""
import argparse
import hashlib
import json
import pathlib
from prepare_scanout_engine_build import prepare as prepare_scanout

def prepare_completion(output):
    prepare_scanout(output)
    recipe=output / 'scripts/build_gpu_gate.sh'
    source=recipe.read_text(encoding='utf-8')
    anchor=' "$QEMU_DIR" "$PWD"\nbuild $QEMU_DIR'
    assert source.count(anchor) == 1
    helper=pathlib.Path(__file__).resolve().parent / 'patch_qemu_native_completion.py'
    source=source.replace(anchor, ' "$QEMU_DIR" "$PWD"\npython3 "'+str(helper)+'" "$QEMU_DIR" "$PWD"\nbuild $QEMU_DIR')
    recipe.write_text(source,encoding='utf-8')
    receipt_path=output/'recipe-receipt.json'
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt.update(scope='upstream-engine-build-recipe-with-fresh-native-completion-adapter',
        native_completion_abi=2, derived_sha256=hashlib.sha256(source.encode()).hexdigest(),
        metal_join_runtime_verified=False, phone_tested=False)
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=pathlib.Path)
    prepare_completion(parser.parse_args().output.resolve())
