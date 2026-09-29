import Foundation

func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
func rejects(_ body: () throws -> Void) {
    do { try body(); fatalError("Expected rejection") } catch { }
}
let root = FileManager.default.temporaryDirectory.resolvingSymlinksInPath().appendingPathComponent(UUID().uuidString)
try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: root) }
let guest = root.appendingPathComponent("guest, with spaces")
try FileManager.default.createDirectory(at: guest, withIntermediateDirectories: true)
var image = Data(repeating: 0, count: 64)
image.replaceSubrange(56..<60, with: [0x41, 0x52, 0x4d, 0x64])
try image.write(to: guest.appendingPathComponent("Image"))
try Data([1, 2]).write(to: guest.appendingPathComponent("initrd.img"))
var disk = Data(repeating: 0, count: 2048)
disk.replaceSubrange(1080..<1082, with: [0x53, 0xef])
try disk.write(to: guest.appendingPathComponent("rootfs.raw"))
var config = LinuxVMConfiguration(directory: guest, log: root.appendingPathComponent("serial.log"), control: root.appendingPathComponent("q.sock"))
let argv = try config.arguments()
#if MYPC_INTERPRETER
check(!LinuxExecutionMode.requiresJIT, "Interpreter must not request JIT")
check(argv.contains("tcg,thread=multi,tb-size=128,split-wx=off"), "Interpreter translation storage must not be executable")
#else
check(LinuxExecutionMode.requiresJIT, "Sideload build must retain JIT preflight")
check(argv.contains("tcg,thread=multi,tb-size=128,split-wx=on"), "JIT must require split W/X")
#endif
let block = try JSONSerialization.jsonObject(with: Data(argv[argv.firstIndex(of: "-blockdev")! + 1].utf8)) as! [String: String]
check(block["filename"] == guest.appendingPathComponent("rootfs.raw").path, "Disk path must survive spaces and commas without option injection")
config.memoryMiB = 8192
rejects { _ = try config.arguments() }
config.memoryMiB = 2048
try Data([0, 0]).write(to: guest.appendingPathComponent("Image"))
rejects { _ = try config.arguments() }
try image.write(to: guest.appendingPathComponent("Image"))
try FileManager.default.removeItem(at: guest.appendingPathComponent("rootfs.raw"))
try FileManager.default.createSymbolicLink(at: guest.appendingPathComponent("rootfs.raw"), withDestinationURL: root.appendingPathComponent("outside"))
rejects { _ = try config.arguments() }
let eventReply = try LinuxQMP.reply(Data(#"{"event":"SHUTDOWN"}"#.utf8), id: 1)
let otherReply = try LinuxQMP.reply(Data(#"{"return":{},"id":2}"#.utf8), id: 1)
let matchedReply = try LinuxQMP.reply(Data(#"{"return":{},"id":1}"#.utf8), id: 1)
check(!eventReply, "Event is not reply")
check(!otherReply, "Wrong id is not reply")
check(matchedReply, "Matched reply")
rejects { _ = try LinuxQMP.reply(Data(#"{"error":{"desc":"failure"},"id":1}"#.utf8), id: 1) }
rejects { _ = try LinuxQMP.command("human-monitor-command", id: 1) }
let pointer = LinuxQMP.pointer(x: .infinity, y: -1, down: true)
check(JSONSerialization.isValidJSONObject(pointer), "Pointer event must handle invalid input")
let typed = try LinuxQMP.text("aA@! ")
let events = typed["events"] as! [[String: Any]]
check(events.count == 16, "Each character must release its key and any shift modifier")
check(JSONSerialization.isValidJSONObject(typed), "Keyboard must form valid QMP events")
rejects { _ = try LinuxQMP.text("password🙂") }
rejects { _ = try LinuxQMP.text(String(repeating: "a", count: 1025)) }
print("PASS: Linux launch validation, disk paths, JIT options, control replies and input bounds")

var meter = LinuxPerformanceCounter()
check(meter.sample(time: 10, cpuSeconds: 4, frames: 0) == nil, "First sample must not invent a CPU rate")
let busy = meter.sample(time: 12, cpuSeconds: 7, frames: 30)!
check(busy.cpuPercent == 150, "CPU must include multiple cores and normalize by elapsed time")
check(busy.displayFPS == 15, "FPS must count new frames rather than timer ticks")
let idle = meter.sample(time: 14, cpuSeconds: 7, frames: 0)!
check(idle.cpuPercent == 0 && idle.displayFPS == 0, "Idle screen must not report synthetic refresh FPS")
let missing = meter.sample(time: 15, cpuSeconds: nil, frames: 1)!
check(missing.cpuPercent == nil, "Failed CPU query must remain unavailable")
let recovered = meter.sample(time: 16, cpuSeconds: 8, frames: 0)!
check(recovered.cpuPercent == nil, "CPU requires two valid consecutive readings")
let reset = meter.sample(time: 17, cpuSeconds: 1, frames: 0)!
check(reset.cpuPercent == nil, "Counter reset must not report negative CPU use")
check(meter.sample(time: 17, cpuSeconds: 1, frames: 0) == nil, "Zero-duration interval must not divide by zero")
let right = LinuxQMP.pointer(x: 0.5, y: 0.5, down: true, button: .right)
let rightEvents = right["events"] as! [[String: Any]]
check((rightEvents[2]["data"] as! [String: Any])["button"] as? String == "right", "Context clicks must use the right mouse button")
print("PASS: CPU accounting, display frame rates, missing metrics and right-click input")
