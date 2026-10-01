#!/usr/bin/env python3
"""Keep the optional CPU trace buildable with the public iOS 26 SDK."""
from pathlib import Path

path = Path('build/ntdll-unix/server_ios.c')
source = path.read_text()
field = 'XP_MS( ru.ri_page_wait_time_mach - pru.ri_page_wait_time_mach ),'
label = 'pgw=%.1f'
if source.count(field) != 1 or source.count(label) != 1:
    raise SystemExit('Wine optional page-wait diagnostic markers changed')
# This member is absent from the public SDK's rusage_info_v6. Remove the
# unsupported measurement, stating that it is unavailable instead of emitting
# a made-up zero. Other native CPU, memory and I/O trace fields stay intact.
source = source.replace(field, '', 1).replace(label, 'pgw=unavailable', 1)
path.write_text(source)
