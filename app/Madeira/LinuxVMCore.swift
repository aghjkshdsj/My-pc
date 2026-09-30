import Foundation

/// A build-time choice: the interpreter app never falls back to native JIT.
enum LinuxExecutionMode {
    #if MYPC_INTERPRETER
    static let requiresJIT = false
    static let defaultCPUSelection = 2
    static let accelerator = "tcg,thread=multi,tb-size=128,split-wx=off"
    static let setupHelp = "Set up Linux, then open Steam. This version runs without JIT and may be very slow. The full ARM64 client downloads from Valve on its first launch."
    static let installedStatus = "Linux runtime installed. Open Steam to start."
    #else
    static let requiresJIT = true
    static let defaultCPUSelection = 0
    // Six emulated CPUs and Chromium share this cache. Avoid repeatedly
    // discarding translated code while keeping a bounded phone memory budget.
    static let accelerator = "tcg,thread=multi,tb-size=256,split-wx=on"
    static let setupHelp = "Set up Linux, enable JIT, then open Steam. The ARM64 client downloads from Valve on its first launch. Select Metal before startup to test experimental GPU graphics; Software is the recovery option."
    static let installedStatus = "Linux runtime installed. Enable JIT, then open Steam."
    #endif
}

enum LinuxVMError: LocalizedError {
    case invalid(String)
    var errorDescription: String? { if case .invalid(let message) = self { return message }; return nil }
}

/// Zero is automatic. Resolve against the cores iOS currently makes available,
/// without pinning host threads or pretending to control iOS scheduling.
enum LinuxCPUSelection {
    static let maximum = 64
    static func available(_ hostCount: Int) -> Int { min(maximum, max(1, hostCount)) }
    static func resolve(_ selection: Int, hostCount: Int) -> Int {
        let count = available(hostCount)
        return selection > 0 ? min(count, selection) : count
    }
}

enum LinuxDesktopSize {
    // Steam's normal desktop window extends beyond the old 960x540 guest.
    static let width = 1280
    static let height = 800
}

enum LinuxGraphicsMode: String, CaseIterable {
    case software, metal
    var title: String { self == .metal ? "Metal (experimental)" : "Software" }
    static func initial(metalAvailable: Bool, saved: String?) -> Self {
        guard LinuxExecutionMode.requiresJIT, metalAvailable else { return .software }
        return saved.flatMap(Self.init(rawValue:)) ?? .software
    }
}

struct LinuxGuestGraphics: Decodable {
    let schema: Int
    let renderer: String
    let readbackOK: Bool
    let accelerated: Bool
    enum CodingKeys: String, CodingKey {
        case schema, renderer, accelerated
        case readbackOK = "readback_ok"
    }
    var verifiedVirgl: Bool {
        let name = renderer.lowercased()
        return readbackOK && accelerated && name.contains("virgl") &&
            !["llvmpipe", "softpipe", "swiftshader", "software"].contains(where: name.contains)
    }
    static func observation(in text: String) -> Self? {
        for line in text.split(separator: "\n").reversed() {
            guard let marker = line.range(of: "MYPC_GUEST_GRAPHICS ") else { continue }
            let payload = line[marker.upperBound...].trimmingCharacters(in: .whitespacesAndNewlines)
            guard payload.utf8.count <= 1024, let value = try? JSONDecoder().decode(Self.self, from: Data(payload.utf8)),
                  value.schema == 1, value.renderer.utf8.count <= 1024 else { continue }
            return value
        }
        return nil
    }
}

struct LinuxGraphicsManifest: Decodable {
    let schema: Int
    let backend: String
    let kernelSHA256: String
    let initrdSHA256: String
    let initrdBytes: Int
}

enum LinuxHardwareTestKind: String, CaseIterable, Decodable {
    case cpu, gpu
    var title: String { self == .cpu ? "CPU comparison" : "FEX GPU comparison" }
    var key: String { self == .cpu ? "f8" : "f9" }
    static func shortcut(_ key: String) -> [[String: Any]] {
        [LinuxQMP.key("ctrl", down: true), LinuxQMP.key("shift", down: true),
         LinuxQMP.key(key, down: true), LinuxQMP.key(key, down: false),
         LinuxQMP.key("shift", down: false), LinuxQMP.key("ctrl", down: false)]
    }
}

struct LinuxHardwareResult: Decodable {
    let mode: String
    let kind: String
    let status: String
    let workers: Int?
    let wallMedianMs: Double?
    let millionIterationsS: Double?
    let renderFps: Double?
    let renderer: String?
    let readbackOk: Bool?
    let accelerated: Bool?
    let submitMedianMs: Double?
    let finishMedianMs: Double?
    let swapMedianMs: Double?
    let stage: String?
    var summary: String {
        let name = mode == "fex" ? "x86-64 through FEX" : "ARM64 inside Linux"
        guard status == "passed" else { return "\(name): \(status)\(stage.map { " (\($0))" } ?? "")" }
        if kind == "cpu", let rate = millionIterationsS, let workers {
            return String(format: "%@: %d workers · %.2f M iterations/s", name, workers, rate)
        }
        return String(format: "%@: %.1f render FPS · %@", name, renderFps ?? 0,
                      accelerated == true ? "virgl pixel check passed" : "software or unverified")
    }
}

struct LinuxHardwareObservation: Decodable {
    let schema: Int
    let run: String
    let kind: LinuxHardwareTestKind
    let status: String
    let stage: String
    let results: [LinuxHardwareResult]
    let progressPercent: Double?
    let heartbeatSeq: Int?
    let elapsedS: Double?
    let stageElapsedS: Double?
    let workDone: Int?
    let workTotal: Int?
    let workUnit: String?
    let workStage: String?
    var stageTitle: String {
        if stage == "sampling-idle" { return "Checking Linux CPU activity" }
        if stage == "finished" { return "Tests finished" }
        if stage == "cancelled" { return "Test stopped" }
        if stage.hasPrefix("arm64-cpu-") { return "ARM64 Linux CPU · \(stage.hasSuffix("-1") ? "one worker" : "all guest cores")" }
        if stage.hasPrefix("fex-cpu-") { return "FEX CPU · \(stage.hasSuffix("-1") ? "one worker" : "all guest cores")" }
        if stage.hasPrefix("arm64-gpu-") { return "ARM64 graphics" }
        if stage.hasPrefix("fex-gpu-") { return "FEX graphics" }
        return "Diagnostic test failed"
    }
    var workTitle: String? {
        switch workStage {
        case "libraries", "launching": return "Loading the test runtime"
        case "EGL", "shader": return "Preparing graphics and shaders"
        case "pixel": return "Checking rendered pixels"
        case "warmup": return "Warming up the CPU workload"
        case "frames", "samples":
            if let workDone, let workTotal, let workUnit { return "\(workDone) of \(workTotal) \(workUnit) finished" }
            return nil
        default: return nil
        }
    }
    static func observation(in text: String) -> (Self, String)? {
        for line in text.split(separator: "\n").reversed() {
            guard let marker = line.range(of: "MYPC_HARDWARE_TEST ") else { continue }
            let json = line[marker.upperBound...].trimmingCharacters(in: .whitespacesAndNewlines)
            guard json.utf8.count <= 16_384 else { continue }
            let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
            guard let value = try? decoder.decode(Self.self, from: Data(json.utf8)),
                  value.schema == 1, UUID(uuidString: value.run) != nil,
                  ["running", "complete", "failed", "cancelled"].contains(value.status),
                  value.progressPercent.map({ $0.isFinite && (0...100).contains($0) }) ?? true,
                  value.heartbeatSeq.map({ (0...10_000_000).contains($0) }) ?? true,
                  value.elapsedS.map({ $0.isFinite && $0 >= 0 }) ?? true,
                  value.stageElapsedS.map({ $0.isFinite && $0 >= 0 }) ?? true,
                  value.workDone.map({ (0...60).contains($0) }) ?? true,
                  value.workTotal.map({ (1...60).contains($0) }) ?? true,
                  value.workUnit.map({ ["samples", "frames"].contains($0) }) ?? true,
                  value.workStage.map({ $0.utf8.count <= 32 }) ?? true,
                  value.stage.utf8.count <= 64, value.results.count <= 4,
                  value.results.allSatisfy({ ["arm64", "fex"].contains($0.mode) &&
                      $0.kind == value.kind.rawValue && ["passed", "failed", "timeout"].contains($0.status) &&
                      ($0.renderer?.utf8.count ?? 0) <= 256 && ($0.stage?.utf8.count ?? 0) <= 32 }) else { continue }
            return (value, json)
        }
        return nil
    }
}

/// Host time and fresh guest records are distinct from work completion. An
/// unchanged serial record must not be treated as a fresh heartbeat.
struct LinuxHardwareHeartbeat {
    private(set) var startedAt: Double?
    private(set) var updatedAt: Double?
    private(set) var cancellationAt: Double?
    private var lastJSON: String?
    mutating func start(now: Double) {
        startedAt = now; updatedAt = nil; cancellationAt = nil; lastJSON = nil
    }
    mutating func receive(_ json: String, now: Double) -> Bool {
        guard json != lastJSON else { return false }
        lastJSON = json; updatedAt = now
        return true
    }
    func elapsed(now: Double) -> Double { max(0, now - (startedAt ?? now)) }
    func age(now: Double) -> Double { max(0, now - (updatedAt ?? startedAt ?? now)) }
    func needsCancellation(now: Double) -> Bool {
        startedAt != nil && cancellationAt == nil && (age(now: now) >= 45 || elapsed(now: now) >= 180)
    }
    mutating func cancel(now: Double) { if cancellationAt == nil { cancellationAt = now } }
    func unresponsive(now: Double) -> Bool { cancellationAt.map { now - $0 >= 15 } ?? false }
    mutating func excludeBackgroundTime(_ seconds: Double) {
        if let time = startedAt { startedAt = time + seconds }
        if let time = updatedAt { updatedAt = time + seconds }
        if let time = cancellationAt { cancellationAt = time + seconds }
    }
}

enum LinuxAppVisibility { case active, inactive, background }
enum LinuxPausePolicy {
    static func change(for visibility: LinuxAppVisibility) -> Bool? {
        switch visibility {
        case .active: return false
        case .background: return true
        case .inactive: return nil // Temporary menus/system UI must not stop Linux.
        }
    }
}

/// Same dependent-integer workload as hardware-bench.c, outside the Linux VM.
/// A compiler/language comparison as well as an emulation comparison; timings
/// are recorded under the current Steam load, never claimed as a CPU clock.
enum LinuxNativeCPUBenchmark {
    static let iterations = 1_000_000
    @inline(never) static func checksum(seed: UInt64, iterations: Int) -> UInt64 {
        var value = seed
        for _ in 0..<iterations {
            value ^= value >> 12; value ^= value << 25; value ^= value >> 27
            value = value &* 2_685_821_657_736_338_717
        }
        return value
    }
    static func run() -> (milliseconds: Double, checksum: String) {
        _ = checksum(seed: 1, iterations: 5_000)
        var times = [Double](); var results = [UInt64]()
        // Different seeds and observable results keep an optimizing compiler
        // from reusing one pure function result for all timed samples.
        for sample in 1...3 {
            let start = ProcessInfo.processInfo.systemUptime
            results.append(checksum(seed: UInt64(sample), iterations: iterations))
            times.append((ProcessInfo.processInfo.systemUptime - start) * 1_000)
        }
        return (times.sorted()[1], results.map { String(format: "%016llx", $0) }.joined(separator: ","))
    }
}

/// Arguments passed directly to QEMU, never through a shell.
struct LinuxVMConfiguration {
    let directory: URL
    let log: URL
    let control: URL
    var memoryMiB = 2048
    var cpuCount = 2
    var resources: URL?
    var graphics: LinuxGraphicsMode = .software
    var graphicsInitrd: URL?

    func arguments() throws -> [String] {
        guard (512...3072).contains(memoryMiB), (1...LinuxCPUSelection.maximum).contains(cpuCount) else {
            throw LinuxVMError.invalid("Linux requires 512–3072 MB RAM and 1–64 CPU cores.")
        }
        // QEMU's Unix socket chardev uses the platform sockaddr_un path limit.
        guard control.isFileURL, control.path.utf8.count < 100,
              !control.path.contains(","), !control.path.contains("\n"),
              log.isFileURL, !log.path.contains(","), !log.path.contains("\n") else {
            throw LinuxVMError.invalid("The Linux control or log path is invalid or too long.")
        }
        let files = try ["Image", "initrd.img", "rootfs.raw"].map { try asset($0) }
        var initrd = files[1]
        if graphics == .metal {
            #if MYPC_INTERPRETER
            throw LinuxVMError.invalid("This interpreter build supports software graphics only.")
            #else
            guard let override = graphicsInitrd,
                  override.isFileURL,
                  override.resolvingSymlinksInPath() == override.standardizedFileURL,
                  try override.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else {
                throw LinuxVMError.invalid("Metal requires the verified graphics boot update.")
            }
            initrd = override
            #endif
        }
        let kernel = try FileHandle(forReadingFrom: files[0])
        defer { try? kernel.close() }
        let header = try kernel.read(upToCount: 64) ?? Data()
        // Linux's uncompressed ARM64 Image magic, at offset 0x38.
        guard header.count == 64, Array(header[56..<60]) == [0x41, 0x52, 0x4d, 0x64] else {
            throw LinuxVMError.invalid("The Linux kernel is not an ARM64 Image.")
        }
        let disk = try FileHandle(forReadingFrom: files[2])
        defer { try? disk.close() }
        try disk.seek(toOffset: 1080)
        guard try disk.read(upToCount: 2) == Data([0x53, 0xef]) else {
            throw LinuxVMError.invalid("The Linux disk is not a raw ext4 filesystem.")
        }
        // Preserve guest flushes; never use cache=unsafe to speed up downloads.
        let storage = try json(["driver": "file", "filename": files[2].path, "node-name": "linux-file", "aio": "threads", "cache": ["direct": false, "no-flush": false]])
        let raw = try json(["driver": "raw", "file": "linux-file", "node-name": "linux-root"])
        var arguments = ["qemu-system-aarch64", "-no-user-config", "-nodefaults",
                // Steam's current ARM client faults on the older Cortex-A72
                // instruction set. TCG supplies newer scalar/NEON features;
                // disable scalable vectors to avoid unused emulation overhead.
                "-machine", "virt-10.0,highmem=off", "-cpu", "max,sve=off,sme=off",
                "-accel", LinuxExecutionMode.accelerator,
                "-smp", String(cpuCount), "-m", String(memoryMiB),
                "-kernel", files[0].path, "-initrd", initrd.path,
                "-append", "console=ttyAMA0 root=/dev/vda rw quiet loglevel=3 my_pc_graphics=\(graphics == .metal ? "virgl" : "software")",
                "-object", "iothread,id=linux-disk-io,poll-max-ns=0",
                "-blockdev", storage, "-blockdev", raw,
                "-device", "virtio-blk-pci,drive=linux-root,iothread=linux-disk-io",
                "-netdev", "user,id=linux-net", "-device", "virtio-net-pci,netdev=linux-net,romfile=",
                "-device", "\(graphics == .metal ? "virtio-gpu-gl-pci" : "virtio-gpu-pci"),xres=\(LinuxDesktopSize.width),yres=\(LinuxDesktopSize.height)",
                "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd",
                "-display", graphics == .metal ? "egl-headless,gl=es" : "none", "-monitor", "none", "-no-reboot",
                "-chardev", "file,id=linux-serial,path=\(log.path)", "-serial", "chardev:linux-serial",
                "-chardev", "socket,id=linux-control,path=\(control.path),server=on,wait=off",
                "-mon", "chardev=linux-control,mode=control"]
        if let resources { arguments += ["-L", resources.path] }
        return arguments
    }

    private func asset(_ name: String) throws -> URL {
        let root = directory.standardizedFileURL
        let file = root.appendingPathComponent(name)
        guard root.isFileURL, root.resolvingSymlinksInPath() == root,
              file.resolvingSymlinksInPath() == file else {
            throw LinuxVMError.invalid("Linux runtime files cannot be symbolic links.")
        }
        let values = try file.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard values.isRegularFile == true, (values.fileSize ?? 0) > 0 else {
            throw LinuxVMError.invalid("Missing Linux runtime file: \(name)")
        }
        return file
    }

    private func json(_ object: [String: Any]) throws -> String {
        String(decoding: try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]), as: UTF8.self)
    }
}

/// One pending motion plus one in-flight request, even if the VM is stalled.
/// Button transitions use the serial control queue separately and are never
/// replaced. The owner yields to queued clicks after each motion request.
final class LinuxPointerMailbox: @unchecked Sendable {
    struct Position { let x: Double; let y: Double; let down: Bool }
    private let lock = NSLock()
    private var pending: Position?
    private var scheduled = false
    func offer(_ value: Position) -> Bool {
        lock.lock(); defer { lock.unlock() }
        pending = value
        guard !scheduled else { return false }
        scheduled = true
        return true
    }
    func take() -> Position? {
        lock.lock(); defer { lock.unlock() }
        let value = pending; pending = nil
        return value
    }
    func finish() -> Bool {
        lock.lock(); defer { lock.unlock() }
        if pending != nil { return true }
        scheduled = false
        return false
    }
    func discard() {
        lock.lock(); pending = nil; lock.unlock()
    }
}

/// QMP envelopes use explicit ids so asynchronous events never count as replies.
enum LinuxQMP {
    static let maxMessageBytes = 1_048_576
    static func command(_ name: String, id: Int, arguments: [String: Any] = [:]) throws -> Data {
        guard ["qmp_capabilities", "query-status", "stop", "cont", "system_powerdown", "input-send-event"].contains(name) else {
            throw LinuxVMError.invalid("Unsupported Linux control command.")
        }
        var object: [String: Any] = ["execute": name, "id": id]
        if !arguments.isEmpty { object["arguments"] = arguments }
        var data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        data.append(contentsOf: [13, 10])
        return data
    }

    static func reply(_ data: Data, id: Int) throws -> Bool {
        guard data.count <= maxMessageBytes,
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw LinuxVMError.invalid("Invalid Linux control response.")
        }
        guard object["id"] as? Int == id else { return false }
        if let error = object["error"] as? [String: Any] {
            throw LinuxVMError.invalid(error["desc"] as? String ?? "Linux control command failed.")
        }
        guard object["return"] != nil else { throw LinuxVMError.invalid("Linux returned an incomplete control response.") }
        return true
    }

    static func pointer(x: Double, y: Double, down: Bool, button: LinuxMouseButton = .left) -> [String: Any] {
        func coordinate(_ value: Double) -> Int { value.isFinite ? Int(min(1, max(0, value)) * 32767) : 0 }
        return ["events": [
            ["type": "abs", "data": ["axis": "x", "value": coordinate(x)]],
            ["type": "abs", "data": ["axis": "y", "value": coordinate(y)]],
            ["type": "btn", "data": ["button": button.rawValue, "down": down]]
        ]]
    }

    static func key(_ code: String, down: Bool) -> [String: Any] {
        ["type": "key", "data": ["down": down, "key": ["type": "qcode", "data": code]]]
    }

    /// Guest keyboard layout is US. Validate the whole string before typing any
    /// character, so an unsupported pasted password is never partially entered.
    static func text(_ text: String) throws -> [String: Any] {
        guard text.count <= 1024 else { throw LinuxVMError.invalid("Paste at most 1,024 characters at a time.") }
        let plain = Array("`1234567890-=[]\\;',./")
        let shifted = Array("~!@#$%^&*()_+{}|:\"<>?")
        let codes = ["grave_accent", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "minus", "equal", "bracket_left", "bracket_right", "backslash", "semicolon", "apostrophe", "comma", "dot", "slash"]
        var events = [[String: Any]]()
        for character in text {
            let code: String
            var shift = false
            if let ascii = character.asciiValue, (65...90).contains(ascii) {
                code = String(character).lowercased(); shift = true
            } else if let ascii = character.asciiValue, (97...122).contains(ascii) {
                code = String(character)
            } else if let index = plain.firstIndex(of: character) { code = codes[index] }
            else if let index = shifted.firstIndex(of: character) { code = codes[index]; shift = true }
            else {
                switch character {
                case " ": code = "spc"
                case "\n", "\r": code = "ret"
                case "\t": code = "tab"
                default: throw LinuxVMError.invalid("The Linux keyboard currently supports the US English character set.")
                }
            }
            if shift { events.append(key("shift", down: true)) }
            events += [key(code, down: true), key(code, down: false)]
            if shift { events.append(key("shift", down: false)) }
        }
        return ["events": events]
    }
}

enum LinuxMouseButton: String {
    case left, right
    case wheelUp = "wheel-up", wheelDown = "wheel-down"
}

/// Process CPU time is cumulative across all threads. 100% means one busy
/// core; the value may exceed 100%. Frames count new guest images consumed by
/// the display, not screen refreshes or a game's internal rendering rate.
struct LinuxPerformanceCounter {
    private var previousTime: Double?
    private var previousCPU: Double?

    mutating func sample(time: Double, cpuSeconds: Double?, frames: Int) -> (cpuPercent: Double?, displayFPS: Double)? {
        defer { previousTime = time; previousCPU = cpuSeconds }
        guard let previousTime, time.isFinite, time > previousTime else { return nil }
        let elapsed = time - previousTime
        var cpu: Double?
        if let cpuSeconds, let previousCPU, cpuSeconds.isFinite,
           previousCPU.isFinite, cpuSeconds >= previousCPU {
            cpu = (cpuSeconds - previousCPU) / elapsed * 100
        }
        return (cpu, Double(max(0, frames)) / elapsed)
    }
}
