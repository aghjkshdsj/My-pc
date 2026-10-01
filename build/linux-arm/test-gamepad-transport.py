#!/usr/bin/env python3
"""Exercise the actual Swift transport against a fragmented local guest ACK."""
import pathlib
import socket
import struct
import subprocess
import tempfile
import time

source = pathlib.Path('app/Madeira/LinuxVMSession.swift').read_text()
start = source.index('final class LinuxGamepadConnection:')
end = source.index('/// A single serial owner',start)
driver = '''
let connection = LinuxGamepadConnection()
connection.start(path: CommandLine.arguments[1])
connection.offer(Data(repeating: 0x11,count: 128),signature: Data([1]))
Thread.sleep(forTimeInterval: 0.2)
connection.offer(Data(repeating: 0x22,count: 128),signature: Data([2]))
Thread.sleep(forTimeInterval: 1.2)
connection.offer(Data(repeating: 0x33,count: 128),signature: Data([3]))
connection.offer(Data(repeating: 0x44,count: 128),signature: Data([4]))
Thread.sleep(forTimeInterval: 0.5)
precondition(connection.guestMask == 1,"Guest ACK must be delivered")
connection.close()
Thread.sleep(forTimeInterval: 0.1)
print("MYPC_SWIFT_GAMEPAD_TRANSPORT_ACK_FRAGMENTATION_AND_EDGES_OK=1")
'''


def read_exact(connection,count):
    result = b''
    while len(result)<count:
        chunk = connection.recv(count-len(result))
        assert chunk, 'Transport closed before delivering a complete state'
        result += chunk
    return result


with tempfile.TemporaryDirectory(prefix='my-pc-pad-') as temporary:
    folder = pathlib.Path(temporary)
    script,binary = folder/'main.swift',folder/'pad-test'
    script.write_text('import Foundation\nimport Darwin\n'+source[start:end]+driver)
    subprocess.run(['swiftc','-swift-version','5',str(script),'-o',str(binary)],check=True)
    path = str(folder/'s')
    assert len(path.encode())<100
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(path); server.listen(1); server.settimeout(5)
        child = subprocess.Popen([str(binary),path],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            connection,_ = server.accept()
            with connection:
                connection.settimeout(0.45)
                try:
                    unexpected = connection.recv(1)
                except socket.timeout: pass
                else: raise AssertionError('Input was sent before Linux was ready: '+repr(unexpected))
                ack = struct.pack('<4sIII',b'ACK1',1,0,0)
                connection.sendall(ack[:6]); time.sleep(0.1)
                connection.sendall(ack[6:]); connection.settimeout(5)
                assert read_exact(connection,128)==bytes([0x22])*128, 'Pre-boot input must use the latest state'
                connection.sendall(struct.pack('<4sIII',b'ACK1',1,1,0))
                assert read_exact(connection,128)==bytes([0x33])*128, 'First button edge lost'
                assert read_exact(connection,128)==bytes([0x44])*128, 'Second button edge lost'
            output,error = child.communicate(timeout=5)
            assert child.returncode==0,(output+error).decode(errors='replace')[-4000:]
            print(output.decode().strip(),flush=True)
        finally:
            if child.poll() is None: child.kill(); child.communicate(timeout=5)
