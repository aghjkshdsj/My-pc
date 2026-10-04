#!/usr/bin/env python3
"""Package the separate observer engine with actual exports and source closure."""
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tarfile
from prepare_moltenvk import package

output = pathlib.Path(sys.argv[1]).resolve()
trace = json.loads((output / 'metal-trace-source-receipt.json').read_text())
assert trace['abi'] == 1 and trace['actual_command_submission_site'] is True
assert trace['native_adapter_fixtures_passed'] is True
for field in ['adds_gpu_work', 'changes_submission_result', 'success_override',
              'phone_tested', 'metal_execution_verified', 'host_memory_import_verified', 'presentation_verified']:
    assert trace[field] is False
with contextlib.redirect_stdout(io.StringIO()):
    package(output)
assert '_mpc_mvk_configure_guest_trace' in (output / 'engine-exports.txt').read_text()
source_dir = output / 'corresponding-source'
for name in ['metal-trace-source-receipt.json', 'guest-metal-completion-observer.patch',
             'MetalGuestTraceABI.h', 'MoltenVKGuestTrace.h', 'MoltenTraceAdapterTests.mm']:
    shutil.copy2(output / name, source_dir)
project = pathlib.Path(__file__).resolve().parents[1]
for path in [project / 'tools/patch_molten_trace.py', pathlib.Path(__file__),
             project.parent / '.github/workflows/steamos-ios-metal-trace.yml']:
    shutil.copy2(path, source_dir)
with tarfile.open(output / 'MoltenVK-Corresponding-Source.tar.gz', 'w:gz') as archive:
    archive.add(source_dir, arcname='corresponding-source')
receipt = json.loads((output / 'engine-receipt.json').read_text())
receipt['scope'] = 'source-built-native-ios-moltenvk-guest-metal-observer-compile-only'
receipt['guest_metal_trace_observer'] = trace
receipt['guest_metal_trace_export_compiled'] = True
p = output / 'MoltenVK-Corresponding-Source.tar.gz'
receipt['files'][p.name] = {'bytes': p.stat().st_size,
    'sha256': hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()}
(output / 'engine-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
(output / 'SHA256SUMS').write_text(''.join(f"{entry['sha256']}  {name}\n" for name, entry in receipt['files'].items()))
print(json.dumps(receipt, indent=2))
