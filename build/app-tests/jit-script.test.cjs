const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/Madeira/madeira-jit.js', 'utf8');
const littleEndian = value => {
    const bytes = Buffer.alloc(8);
    bytes.writeBigUInt64LE(value);
    return bytes.toString('hex');
};
for (const [response, expected] of [['E35', 0n], ['E09', 0n], ['', 0n], ['OK', 0n], ['0', 0n], ['12345', 0n], ['120000000', 0x120000000n]]) {
    let continued = false;
    const commands = [];
    const prepared = [];
    const stop = `T05thread:1;00:${littleEndian(0n)};01:${littleEndian(0x4000n)};10:${littleEndian(1n)};20:${littleEndian(0x4000n)};`;
    vm.runInNewContext(source, {
        get_pid: () => 123,
        log: () => {},
        prepare_memory_region: (address, size) => { prepared.push([address, size]); return true; },
        send_command: command => {
            commands.push(command);
            if (command.startsWith('vAttach')) return 'T11thread:1;';
            if (command.startsWith('QSet')) return 'E35';
            if (command.startsWith('QPass')) return '';
            if (command === 'c') { if (continued) return 'W00'; continued = true; return stop; }
            if (command === 'm4000,4') return 'a0013ed4';
            if (command === '_M4000,rx') return response;
            return 'OK';
        }
    }, { timeout: 1000 });
    assert(commands.includes(`P0=${littleEndian(expected)};thread:1;`), `Wrong allocation result for ${response}`);
    assert.equal(prepared.length, expected === 0n ? 0 : 1, `Prepared invalid address from ${response}`);
}
console.log('JIT allocation protocol tests passed');
