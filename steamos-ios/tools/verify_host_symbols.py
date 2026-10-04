#!/usr/bin/env python3
"""Match a retained ARM64 dSYM to the exact packaged host, never phone proof."""
import argparse, hashlib, json, pathlib, plistlib, struct, uuid, zipfile


def macho_uuid(binary, filetype):
    if len(binary)<32:
        raise ValueError('Truncated Mach-O header')
    magic,cpu,subtype,kind,count,size,flags,reserved=struct.unpack_from('<8I',binary)
    if magic!=0xfeedfacf or cpu!=0x100000c or kind!=filetype or count>1024 or 32+size>len(binary):
        raise ValueError('Expected bounded thin ARM64 Mach-O of the correct kind')
    cursor=32;found=[]
    for _ in range(count):
        if cursor+8>32+size: raise ValueError('Truncated command header')
        command,length=struct.unpack_from('<II',binary,cursor)
        if length<8 or cursor+length>32+size: raise ValueError('Invalid command size')
        if command==0x1b:
            if length!=24: raise ValueError('Wrong UUID command size')
            found.append(str(uuid.UUID(bytes=binary[cursor+8:cursor+24])).upper())
        cursor+=length
    if cursor!=32+size or len(found)!=1 or found[0]=='00000000-0000-0000-0000-000000000000':
        raise ValueError('Need exactly one nonzero Mach-O UUID')
    return found[0]


def verify(ipa, dwarf, commit, build):
    with zipfile.ZipFile(ipa) as archive:
        base='Payload/MyPCSteamOSProbe.app/'
        info=plistlib.loads(archive.read(base+'Info.plist'))
        if info['MPCSourceCommit']!=commit or info['CFBundleVersion']!=build:
            raise ValueError('Symbols must identify the intended package source/build')
        binary=archive.read(base+info['CFBundleExecutable'])
    symbols=dwarf.read_bytes()
    host_uuid=macho_uuid(binary,2)
    if macho_uuid(symbols,10)!=host_uuid: raise ValueError('Host and debug-symbol UUIDs differ')
    return dict(schema=1,scope='exact-packaged-arm64-host-debug-symbols',source_commit=commit,build=build,
        binary_uuid=host_uuid,host_executable_sha256=hashlib.sha256(binary).hexdigest(),
        dwarf_bytes=len(symbols),dwarf_sha256=hashlib.sha256(symbols).hexdigest(),phone_tested=False,
        crash_cause_established=False,limitation='Matching host UUID permits host symbolication. It does not establish the crash cause or provide upstream framework dSYMs.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ipa',type=pathlib.Path);parser.add_argument('dwarf',type=pathlib.Path)
    parser.add_argument('commit');parser.add_argument('build');parser.add_argument('--receipt',type=pathlib.Path)
    args=parser.parse_args();result=verify(args.ipa,args.dwarf,args.commit,args.build)
    text=json.dumps(result,indent=2)+'\n'
    if args.receipt:args.receipt.write_text(text,encoding='utf-8')
    print(text)
