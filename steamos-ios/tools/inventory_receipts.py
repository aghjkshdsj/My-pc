#!/usr/bin/env python3
import csv
import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
audit = json.loads((root / 'evidence/archive-audit.json').read_text(encoding='utf-8'))
summary = {k: v for k, v in audit.items() if k not in ('files_detail', 'external_references')}
(root / 'evidence/archive-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
with (root / 'evidence/archive-files.csv').open('w', encoding='utf-8', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['path', 'component', 'bytes', 'sha256'])
    writer.writeheader()
    writer.writerows({k: row[k] for k in writer.fieldnames} for row in audit['files_detail'])
