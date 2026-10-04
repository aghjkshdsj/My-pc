"""Bounded defined-export check; a string/private symbol cannot satisfy dlsym."""
import struct


def defined_export(binary, name):
    if len(binary) < 32: raise ValueError('Truncated Mach-O')
    magic, cpu, _, kind, count, size, _, _ = struct.unpack_from('<8I', binary)
    if magic != 0xfeedfacf or cpu != 0x100000c or kind != 6 or count > 1024 or 32 + size > len(binary):
        raise ValueError('Expected bounded thin ARM64 dynamic library')
    cursor = 32; tables = []; ranges = []
    for _ in range(count):
        if cursor + 8 > 32 + size: raise ValueError('Truncated command')
        cmd, length = struct.unpack_from('<II', binary, cursor)
        if length < 8 or cursor + length > 32 + size: raise ValueError('Invalid command')
        if cmd == 2:
            if length != 24: raise ValueError('Invalid symbol table')
            tables.append(struct.unpack_from('<4I', binary, cursor + 8))
        if cmd == 11:
            if length != 80: raise ValueError('Invalid dynamic symbol table')
            ranges.append(struct.unpack_from('<2I', binary, cursor + 16))
        cursor += length
    if cursor != 32 + size or len(tables) != 1 or len(ranges) != 1:
        raise ValueError('Need exact symbol and dynamic definition tables')
    symoff, total, stroff, strsize = tables[0]
    first, length = ranges[0]
    if total > 1000000 or symoff + total * 16 > len(binary) or stroff + strsize > len(binary) or first + length > total:
        raise ValueError('Out-of-bounds symbol table')
    wanted = ('_' + name).encode('ascii')
    matches = []
    for i in range(first, first + length):
        offset, flags, section, _, value = struct.unpack_from('<IBBHQ', binary, symoff + i * 16)
        if offset >= strsize: raise ValueError('Invalid symbol string offset')
        start = stroff + offset
        end = binary.find(b'\0', start, stroff + strsize)
        if end < 0: raise ValueError('Unterminated symbol string')
        if binary[start:end] == wanted:
            matches.append(flags == 15 and section != 0 and value != 0)
    return matches == [True]
