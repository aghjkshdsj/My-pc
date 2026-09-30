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
check(LinuxExecutionMode.defaultCPUSelection == 2, "Interpreter retains the tested two-core default")
check(LinuxGraphicsMode.initial(metalAvailable: true, saved: nil) == .software, "Interpreter cannot enable Metal")
check(argv.contains("tcg,thread=multi,tb-size=128,split-wx=off"), "Interpreter translation storage must not be executable")
#else
check(LinuxExecutionMode.requiresJIT, "Sideload build must retain JIT preflight")
check(LinuxExecutionMode.defaultCPUSelection == 0, "JIT defaults to all available cores")
check(LinuxGraphicsMode.initial(metalAvailable: true, saved: nil) == .software, "GPU preview retains Software until device validation")
check(LinuxGraphicsMode.initial(metalAvailable: true, saved: "invalid") == .software, "Invalid stored choice should allow software recovery")
check(LinuxGraphicsMode.initial(metalAvailable: true, saved: "metal") == .metal, "An explicit Metal choice must be preserved")
check(argv.contains("tcg,thread=multi,tb-size=256,split-wx=on"), "JIT must require split W/X")
#endif
let block = try JSONSerialization.jsonObject(with: Data(argv[argv.firstIndex(of: "-blockdev")! + 1].utf8)) as! [String: Any]
let cache = block["cache"] as! [String: Bool]
check(cache["no-flush"] == false, "Performance changes must preserve guest flushes")
check(argv.contains("virtio-blk-pci,drive=linux-root,iothread=linux-disk-io"), "Disk processing must use its own IOThread")
check(LinuxGraphicsMode.initial(metalAvailable: true, saved: "software") == .software, "Explicit software recovery must be preserved")
check(LinuxGraphicsMode.initial(metalAvailable: false, saved: "metal") == .software, "A software-only runtime cannot request Metal")
let graphicsLine = #"MYPC_GUEST_GRAPHICS {"schema":1,"renderer":"virgl","readback_ok":true,"accelerated":true}"#
check(LinuxGuestGraphics.observation(in: graphicsLine)?.verifiedVirgl == true, "Actual virgl pixel readback should verify the guest driver")
check(LinuxGuestGraphics.observation(in: graphicsLine.replacingOccurrences(of: "virgl", with: "virgl llvmpipe"))?.verifiedVirgl == false, "Software fallback must not be reported as accelerated")
check(LinuxGuestGraphics.observation(in: graphicsLine.replacingOccurrences(of: "\"readback_ok\":true", with: "\"readback_ok\":false"))?.verifiedVirgl == false, "A renderer name alone cannot pass")
check(LinuxGuestGraphics.observation(in: "MYPC_GUEST_GRAPHICS invalid") == nil, "Malformed graphics report stays unverified")
check(LinuxGuestGraphics.observation(in: graphicsLine.replacingOccurrences(of: "\"schema\":1", with: "\"schema\":2")) == nil, "Unknown graphics schemas cannot verify acceleration")
check(block["filename"] as? String == guest.appendingPathComponent("rootfs.raw").path, "Disk path must survive spaces and commas without option injection")
check(LinuxCPUSelection.resolve(0, hostCount: 6) == 6, "Automatic mode must expose all six iPhone cores")
check(LinuxCPUSelection.resolve(2, hostCount: 6) == 2, "A smaller manual selection must remain available")
check(LinuxCPUSelection.resolve(8, hostCount: 6) == 6, "Stored preferences must not oversubscribe this phone")
check(LinuxCPUSelection.resolve(-1, hostCount: 6) == 6, "Invalid automatic preference must be safe")
check(LinuxCPUSelection.resolve(0, hostCount: 0) == 1, "At least one CPU must remain usable")
config.cpuCount = LinuxCPUSelection.resolve(0, hostCount: 6)
let sixCoreArguments = try config.arguments()
check(sixCoreArguments[sixCoreArguments.firstIndex(of: "-smp")! + 1] == "6", "Launch must actually request six virtual CPUs")
check(sixCoreArguments.contains("virtio-gpu-pci,xres=1280,yres=800"), "Guest desktop must fit the normal Steam window")
config.cpuCount = 65
rejects { _ = try config.arguments() }
config.cpuCount = 0
rejects { _ = try config.arguments() }
config.cpuCount = 6
config.graphics = .metal
rejects { _ = try config.arguments() }
config.graphicsInitrd = guest.appendingPathComponent("initrd.img")
#if MYPC_INTERPRETER
rejects { _ = try config.arguments() }
#else
let metalArguments = try config.arguments()
check(metalArguments.contains("virtio-gpu-gl-pci,xres=1280,yres=800"), "Metal must use the accelerated virtio GPU")
check(metalArguments.contains("egl-headless,gl=es"), "Metal must select the tested GLES display backend")
check(metalArguments[metalArguments.firstIndex(of: "-append")! + 1].contains("my_pc_graphics=virgl"), "Metal must update existing guest startup scripts")
#endif
config.graphics = .software
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

let mailbox = LinuxPointerMailbox()
check(mailbox.offer(.init(x: 0, y: 0, down: false)), "First motion schedules one drain")
let inflight = mailbox.take()!
check(inflight.x == 0, "First request is in flight")
for index in 1...10_000 {
    check(!mailbox.offer(.init(x: Double(index), y: 1, down: false)), "Stalled control must not queue another drain for each movement")
}
check(mailbox.finish(), "Latest motion needs one more turn after the click queue")
check(mailbox.take()?.x == 10_000, "Drop stale movements rather than playing them back")
check(!mailbox.finish(), "Drain becomes idle after the latest position")
check(mailbox.offer(.init(x: 1, y: 1, down: true)), "Motion after idle restarts drain")
mailbox.discard()
check(mailbox.take() == nil, "Press/release cancels any older pending motion")
check(!mailbox.finish(), "Cancelled drain must become idle")
check(mailbox.offer(.init(x: 2, y: 2, down: false)), "Motion after release restarts safely")
check(mailbox.take()?.down == false, "Release state must survive motion coalescing")
check(!mailbox.finish(), "No empty drain spin")
print("PASS: 10,000 motions during a stalled request retain one latest position")
