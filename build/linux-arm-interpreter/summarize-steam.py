#!/usr/bin/env python3
"""Fixed-schema diagnostics for the isolated, account-free interpreter CI log."""
import json
import pathlib
import re
import sys

content = pathlib.Path(sys.argv[1]).read_text(errors='replace')
patterns = {
    'oom_events': r'Out of memory:|oom-kill:|Killed process \d+ \(steam',
    'segfaults': r'Segmentation fault|segfault at|signal SIGSEGV',
    'illegal_instructions': r'Illegal instruction|signal SIGILL',
    'loopback_rejections': r'Rejecting connection from|Rejected connection from',
    'missing_lsof': r'lsof: (?:command )?not found',
    'affinity_errors': r'taskset:.*(?:Invalid argument|failed)',
    'kernel_panics': r'Kernel panic',
}
result = {key: len(re.findall(pattern, content)) for key, pattern in patterns.items()}
result['launcher_exit_statuses'] = [int(value) for value in re.findall(
    r'ARM64 Steam exited with status (\d{1,3})', content)][-16:]
result['policy_denials'] = content.count('MYPC_NOJIT_POLICY_DENIED')
result['login_gate_passed'] = 'MYPC_GUEST_STEAM_WINDOW_OK' in content
result['login_gate_failed'] = 'MYPC_GUEST_STEAM_FAILED' in content
result['helper_count'] = None
for match in re.finditer(r'MYPC_STEAM_HEALTH\s+(\{)', content):
    try:
        health, _ = json.JSONDecoder().raw_decode(content[match.start(1):])
        count = health.get('webhelper_processes')
        if type(count) is int and 0 <= count <= 1024:
            result['helper_count'] = count
    except ValueError:
        pass
print('MYPC_INTERPRETER_STEAM_DIAGNOSTIC ' + json.dumps(result, sort_keys=True))
