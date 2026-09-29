"""Bounded process-state diagnostics for disposable, account-free CI guests.

Never emit command arguments, environment, paths, addresses, URLs or input.
"""
import pathlib
import re


def helper_started(processes):
    return re.search(r'^\s*\d+\s+\d+\s+steamwebhelper(?:\s|$)', processes, re.M) is not None


def wait_category(value):
    value = value.strip()
    if value == '0':
        return 'running_or_unavailable'
    for pattern, label in [('futex', 'futex'), ('pipe', 'pipe'), ('poll', 'poll'),
                           ('random', 'entropy'), ('accept', 'accept'),
                           ('sleep', 'sleep'), ('wait_for_completion', 'completion')]:
        if pattern in value:
            return label
    return 'other'


def process_health(root=pathlib.Path('/proc')):
    report = {'steam': [], 'webhelper_processes': 0, 'entropy_bits': None}
    try:
        entropy = int((root / 'sys/kernel/random/entropy_avail').read_text())
        report['entropy_bits'] = min(4096, max(0, entropy))
    except (OSError, ValueError):
        pass
    for path in root.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            role = (path / 'comm').read_text().strip()
            if role == 'steamwebhelper':
                report['webhelper_processes'] += 1
            if role != 'steam' or len(report['steam']) >= 8:
                continue
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            state = fields[0] if fields[0] in {'R', 'S', 'D', 'T', 'Z', 'I'} else 'other'
            status = (path / 'status').read_text()
            def number(name):
                match = re.search(r'^' + name + r':\s+(\d+)', status, re.M)
                return int(match[1]) if match else None
            report['steam'].append({
                'state': state,
                'cpu_ticks': int(fields[11]) + int(fields[12]),
                'main_wait': wait_category((path / 'wchan').read_text()),
                'rss_kib': number('VmRSS'), 'threads': number('Threads'),
            })
        except (OSError, ValueError, IndexError):
            # A child can exit between reads; a missing snapshot is not a crash.
            continue
    return report
