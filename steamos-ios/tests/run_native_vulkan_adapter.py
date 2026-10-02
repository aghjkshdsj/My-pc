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
int MPCNativeVulkanDraw(void *, const char *, const char *);
int main(int argc, char **argv) {
 if (argc != 4) return 2;
 void *lib = dlopen("libvulkan.so.1", RTLD_NOW | RTLD_LOCAL);
 if (!lib) return 3;
 int code = MPCNativeVulkanDraw(lib, argv[1], argv[2]);
 printf("MPC_ADAPTER_RETURNED=%d\\n", code);
 return code == atoi(argv[3]) ? 0 : 4;
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
cases = [(output / 'absent.spv', shaders / 'fragment.spv', 5),
         (broken, shaders / 'fragment.spv', 5), (shaders / 'vertex.spv', shaders / 'fragment.spv', 0)]
results = []
for index, (vertex, fragment, expected) in enumerate(cases):
 row = subprocess.run([str(binary), str(vertex), str(fragment), str(expected)], env=env,
                       capture_output=True, text=True, timeout=45)
 (output / f'case-{index}.stdout').write_text(row.stdout)
 (output / f'case-{index}.stderr').write_text(row.stderr)
 assert row.returncode == 0 and f'MPC_ADAPTER_RETURNED={expected}' in row.stdout, (row.returncode, row.stdout, row.stderr)
 if expected == 0:
  draws = [json.loads(x.removeprefix('MPC_VK_DIAGNOSTIC ')) for x in row.stdout.splitlines() if x.startswith('MPC_VK_DIAGNOSTIC ')]
  assert len(draws) == 1 and draws[0]['software'] is True and draws[0]['mismatches'] == 0
  assert draws[0]['pixels_checked'] == 1843200 and draws[0]['channel_sum'] == 1219256320 and draws[0]['validation_errors'] == 0
 results.append({'case': index, 'expected_adapter_return': expected, 'process_survived': True})
receipt = {'scope': 'hosted-software-native-adapter-error-and-shader-check', 'results': results,
           'original_adapter_sha256': hashlib.sha256(original.encode()).hexdigest(),
           'fixture_policy': 'Only hosted fixture adds allow-software argument; production source unchanged',
           'phone_verified': False, 'metal_verified': False, 'guest_graphics_verified': False, 'gameplay_verified': False}
(output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
