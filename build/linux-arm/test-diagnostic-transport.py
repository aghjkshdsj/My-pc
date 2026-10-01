#!/usr/bin/env python3
"""Run the actual Swift diagnostic socket with fragmented ACK/state records."""
import json
import pathlib
import socket
import subprocess
import tempfile
import time

source = pathlib.Path('app/Madeira/LinuxVMSession.swift').read_text()
start = source.index('final class LinuxDiagnosticConnection:')
end = source.index('/// Only the latest frame', start)
driver = '''
let connection = LinuxDiagnosticConnection()
let lock = NSLock()
var gotACK = false, gotState = false, gotCancel = false
connection.start(path: CommandLine.arguments[1]) { message in
    lock.lock(); defer { lock.unlock() }
    switch message {
    case let .ack(id, command, status):
        if id == String(repeating: "a", count: 32) && command == "cpu" && status == "accepted" { gotACK = true }
        if id == String(repeating: "b", count: 32) && command == "cancel" && status == "accepted" { gotCancel = true }
    case let .state(id, observation, _):
        if id == String(repeating: "a", count: 32) && observation.heartbeatSeq == 1 { gotState = true }
    default: break
    }
}
func waitFor(_ condition: () -> Bool) {
    let deadline = Date().addingTimeInterval(5)
    while !condition() && Date() < deadline { Thread.sleep(forTimeInterval: 0.01) }
    precondition(condition(), "Diagnostic transport deadline")
}
func flags(_ select: () -> Bool) -> Bool { lock.lock(); defer { lock.unlock() }; return select() }
waitFor { connection.ready }
connection.send(id: String(repeating: "a", count: 32), command: "cpu")
waitFor { flags { gotACK && gotState } }
connection.send(id: String(repeating: "b", count: 32), command: "cancel", target: String(repeating: "a", count: 32))
waitFor { flags { gotCancel } }
connection.close()
Thread.sleep(forTimeInterval: 0.2)
precondition(!connection.ready, "Disconnect clears live readiness")
print("MYPC_SWIFT_DIAGNOSTIC_ACK_STATE_FRAGMENTATION_AND_SCOPED_STOP_OK=1")
'''

def send_fragmented(connection, value):
    data = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    connection.sendall(data[:7]); time.sleep(0.02)
    connection.sendall(data[7:31]); time.sleep(0.02)
    connection.sendall(data[31:])

with tempfile.TemporaryDirectory(prefix='my-pc-test-') as temporary:
    folder = pathlib.Path(temporary)
    script, binary = folder/'main.swift', folder/'diagnostic-test'
    script.write_text('import Foundation\nimport Darwin\n' + source[start:end] + driver)
    subprocess.run(['swiftc', '-swift-version', '5', 'app/Madeira/LinuxVMCore.swift', str(script), '-o', str(binary)], check=True)
    path = str(folder/'s')
    assert len(path.encode()) < 100
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(path); server.listen(1); server.settimeout(8)
        child = subprocess.Popen([str(binary), path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(8)
                stream = connection.makefile('rb')
                send_fragmented(connection, {'schema':1, 'type':'ready', 'ready':True, 'busy':False})
                status = json.loads(stream.readline())
                assert status['command'] == 'status'
                request = json.loads(stream.readline())
                assert request == {'schema':1, 'id':'a'*32, 'command':'cpu'}
                send_fragmented(connection, {'schema':1, 'type':'ack', **{k:request[k] for k in ('id','command')}, 'status':'accepted'})
                send_fragmented(connection, {'schema':1, 'type':'state', 'id':'a'*32, 'state':{
                    'schema':1, 'run':'F898533A-6F4A-47B9-824F-9A76574D0847', 'kind':'cpu',
                    'status':'running', 'stage':'sampling-idle', 'heartbeat_seq':1, 'results':[]}})
                cancel = json.loads(stream.readline())
                assert cancel == {'schema':1, 'id':'b'*32, 'command':'cancel', 'target':'a'*32}
                send_fragmented(connection, {'schema':1, 'type':'ack', 'id':'b'*32, 'command':'cancel', 'status':'accepted'})
                output, error = child.communicate(timeout=8)
                assert child.returncode == 0, (output+error).decode(errors='replace')[-4000:]
                print(output.decode().strip(), flush=True)
        finally:
            if child.poll() is None: child.kill(); child.communicate(timeout=5)
