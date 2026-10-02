#!/usr/bin/env python3
"""Real hosted error interception; software fixture, never phone/Metal evidence."""
import hashlib
import json
import os
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
output = root / 'out/native-vulkan-adapter-tests'
output.mkdir(parents=True, exist_ok=False)
original = (root / 'Host/NativeVulkanDraw.c').read_text()
adapted = original.replace('#include "../Guest/vk_gate.c"', '#include "' + (root / 'Guest/vk_gate.c').as_posix() + '"')
old = 'char *arguments[] = {"native-vulkan-diagnostic", (char *)vertex, (char *)fragment};'
assert adapted.count(old) == 1 and adapted.count('mpc_shared_vulkan_main(3, arguments)') == 1
# Test fixture only: allow software so missing/broken shaders reach exit().
# The original product source and hardware-rejection behavior remain unchanged.
adapted = adapted.replace(old, 'char *arguments[] = {"hosted-fixture", (char *)vertex, (char *)fragment, "--allow-software-diagnostic"};')
adapted = adapted.replace('mpc_shared_vulkan_main(3, arguments)', 'mpc_shared_vulkan_main(4, arguments)')
(output / 'adapter.c').write_text(adapted)
(output / 'main.c').write_text('''#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int MPCNativeVulkanDraw(void *, const char *, const char *, const char *);
int main(int argc, char **argv) {
 if (argc != 5) return 2;
 void *lib = dlopen("libvulkan.so.1", RTLD_NOW | RTLD_LOCAL);
 if (!lib) return 3;
 /* Engine logging can contain non-UTF8 bytes or unrelated receipt-like lines. */
 fputs("MPC_VK_DIAGNOSTIC unrelated-engine-log", stdout); fputc(255, stdout); fputc(10, stdout);
 int code = MPCNativeVulkanDraw(lib, argv[1], argv[2], argv[3]);
 printf("MPC_ADAPTER_RETURNED=%d\\n", code);
 return code == atoi(argv[4]) ? 0 : 4;
}
''')
binary = output / 'adapter-test'
subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(output / 'adapter.c'),
                str(output / 'main.c'), '-ldl', '-o', str(binary)], check=True)
lvp = list(pathlib.Path('/usr/share/vulkan/icd.d').glob('lvp_icd*.json'))
assert len(lvp) == 1
env = dict(os.environ, VK_DRIVER_FILES=str(lvp[0]))
shaders = pathlib.Path('/tmp/mpc-vulkan')
broken = output / 'bad.spv'; broken.write_bytes(bytes(20))
existing = output / 'existing.json'; existing.write_text('preserve-existing-receipt')
cases = [(output / 'absent.spv', shaders / 'fragment.spv', output / 'case-0-diagnostic.json', 5),
         (broken, shaders / 'fragment.spv', output / 'case-1-diagnostic.json', 5),
         (shaders / 'vertex.spv', shaders / 'fragment.spv', output / 'case-2-diagnostic.json', 0),
         (shaders / 'vertex.spv', shaders / 'fragment.spv', existing, 92),
         (shaders / 'vertex.spv', shaders / 'fragment.spv', output / 'absent-dir/receipt.json', 92)]
results = []
for index, (vertex, fragment, diagnostic, expected) in enumerate(cases):
 row = subprocess.run([str(binary), str(vertex), str(fragment), str(diagnostic), str(expected)], env=env,
                       capture_output=True, text=True, errors='replace', timeout=45)
 (output / f'case-{index}.stdout').write_text(row.stdout)
 (output / f'case-{index}.stderr').write_text(row.stderr)
 assert row.returncode == 0 and f'MPC_ADAPTER_RETURNED={expected}' in row.stdout, (row.returncode, row.stdout, row.stderr)
 if expected == 0:
  draw = json.loads(diagnostic.read_text())
  assert draw['software'] is True and draw['mismatches'] == 0
  assert draw['pixels_checked'] == 1843200 and draw['channel_sum'] == 1219256320 and draw['validation_errors'] == 0
  assert '\ufffd' in row.stdout and 'unrelated-engine-log' in row.stdout
 elif expected == 5:
  assert diagnostic.read_bytes() == b''  # An aborted draw cannot leave a passing receipt.
 assert existing.read_text() == 'preserve-existing-receipt'
 results.append({'case': index, 'expected_adapter_return': expected, 'process_survived': True,
                 'dedicated_receipt_passed': expected == 0})
receipt = {'scope': 'hosted-software-native-adapter-error-and-shader-check', 'results': results,
           'original_adapter_sha256': hashlib.sha256(original.encode()).hexdigest(),
           'fixture_policy': 'Only hosted fixture adds allow-software argument; production source unchanged',
           'dedicated_receipt_independent_of_invalid_utf8_stdout': True,
           'phone_verified': False, 'metal_verified': False, 'guest_graphics_verified': False, 'gameplay_verified': False}
(output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
