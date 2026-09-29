import Foundation
import SwiftUI
import UIKit
import Darwin
import CryptoKit

/// A single serial owner for the local QMP socket. No listener is exposed on LAN.
final class LinuxQMPConnection: @unchecked Sendable {
    private let queue = DispatchQueue(label: "my-pc.linux.qmp")
    private var descriptor: Int32 = -1
    private var requestID = 0

    func connect(path: String, completion: @escaping (Result<Void, Error>) -> Void) {
        queue.async {
            do {
                guard path.utf8.count < 100 else { throw LinuxVMError.invalid("Linux control path is too long.") }
                let deadline = Date().addingTimeInterval(30)
                while Date() < deadline {
                    let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
                    guard fd >= 0 else { throw LinuxVMError.invalid("Cannot create Linux control socket.") }
                    var address = sockaddr_un()
                    address.sun_family = sa_family_t(AF_UNIX)
                    address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
                    _ = withUnsafeMutableBytes(of: &address.sun_path) { pathBytes in
                        path.withCString { strlcpy(pathBytes.baseAddress!.assumingMemoryBound(to: CChar.self), $0, pathBytes.count) }
                    }
                    let result = withUnsafePointer(to: &address) {
                        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
                    }
                    if result == 0 { self.descriptor = fd; break }
                    Darwin.close(fd)
                    Thread.sleep(forTimeInterval: 0.1)
                }
                guard self.descriptor >= 0 else { throw LinuxVMError.invalid("Linux did not open its control socket. Check the boot log.") }
                var seconds = timeval(tv_sec: 3, tv_usec: 0)
                var enabled: Int32 = 1
                setsockopt(self.descriptor, SOL_SOCKET, SO_RCVTIMEO, &seconds, socklen_t(MemoryLayout<timeval>.size))
                setsockopt(self.descriptor, SOL_SOCKET, SO_SNDTIMEO, &seconds, socklen_t(MemoryLayout<timeval>.size))
                setsockopt(self.descriptor, SOL_SOCKET, SO_NOSIGPIPE, &enabled, socklen_t(MemoryLayout<Int32>.size))
                let greeting = try JSONSerialization.jsonObject(with: self.line()) as? [String: Any]
                guard greeting?["QMP"] != nil else { throw LinuxVMError.invalid("Unexpected Linux control greeting.") }
                try self.request("qmp_capabilities", arguments: [:])
                completion(.success(()))
            } catch {
                if self.descriptor >= 0 { Darwin.close(self.descriptor); self.descriptor = -1 }
                completion(.failure(error))
            }
        }
    }

    func send(_ command: String, arguments: [String: Any] = [:], completion: @escaping (Result<Void, Error>) -> Void = { _ in }) {
        queue.async {
            do { try self.request(command, arguments: arguments); completion(.success(())) }
            catch { completion(.failure(error)) }
        }
    }

    func close() {
        queue.async {
            if self.descriptor >= 0 { Darwin.close(self.descriptor); self.descriptor = -1 }
        }
    }

    func sendKeyboard(_ events: [[String: Any]], completion: @escaping (Result<Void, Error>) -> Void) {
        queue.async {
            do {
                for event in events {
                    try self.request("input-send-event", arguments: ["events": [event]])
                    // USB HID has a bounded event queue. Give the guest time to
                    // consume each transition, including during a long paste.
                    Thread.sleep(forTimeInterval: 0.01)
                }
                completion(.success(()))
            } catch { completion(.failure(error)) }
        }
    }

    func click(x: Double, y: Double, button: LinuxMouseButton) {
        queue.async {
            do {
                try self.request("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: true, button: button))
                Thread.sleep(forTimeInterval: 0.01)
                try self.request("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: false, button: button))
            } catch { /* A disconnected session cannot accept pointer input. */ }
        }
    }

    private func request(_ command: String, arguments: [String: Any]) throws {
        guard descriptor >= 0 else { throw LinuxVMError.invalid("Linux control is not connected.") }
        requestID += 1
        let data = try LinuxQMP.command(command, id: requestID, arguments: arguments)
        try data.withUnsafeBytes { bytes in
            var sent = 0
            while sent < data.count {
                let count = Darwin.send(descriptor, bytes.baseAddress!.advanced(by: sent), data.count - sent, 0)
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else { throw LinuxVMError.invalid("Linux control write failed.") }
                sent += count
            }
        }
        let deadline = Date().addingTimeInterval(5)
        while Date() < deadline {
            if try LinuxQMP.reply(line(), id: requestID) { return }
        }
        throw LinuxVMError.invalid("Linux control reply timed out.")
    }

    private func line() throws -> Data {
        var result = Data()
        while result.count < LinuxQMP.maxMessageBytes {
            var byte: UInt8 = 0
            let count = Darwin.recv(descriptor, &byte, 1, 0)
            if count < 0 && errno == EINTR { continue }
            guard count == 1 else { throw LinuxVMError.invalid("Linux control connection closed or timed out.") }
            result.append(byte)
            if byte == 10 { return result }
        }
        throw LinuxVMError.invalid("Linux control response exceeds its size limit.")
    }
}

/// Only the latest frame is retained, so a slow UI cannot build an unbounded queue.
final class LinuxFrameInbox: @unchecked Sendable {
    static let shared = LinuxFrameInbox()
    private let lock = NSLock()
    private var frame: (Data, Int, Int, Int)?
    func push(_ pixels: UnsafeRawPointer, width: Int, height: Int, stride: Int) {
        guard width > 0, width <= 4096, height > 0, height <= 4096,
              stride >= width * 4, stride <= 4096 * 4 else { return }
        let copy = Data(bytes: pixels, count: stride * height)
        lock.lock(); frame = (copy, width, height, stride); lock.unlock()
    }
    func take() -> CGImage? {
        lock.lock(); let value = frame; frame = nil; lock.unlock()
        guard let (data, width, height, stride) = value,
              let provider = CGDataProvider(data: data as CFData) else { return nil }
        return CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
                       bytesPerRow: stride, space: CGColorSpaceCreateDeviceRGB(),
                       bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedFirst.rawValue).union(.byteOrder32Little),
                       provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent)
    }
}

private let linuxFrameCallback: @convention(c) (UnsafeMutableRawPointer?, UnsafeRawPointer?, Int32, Int32, Int32) -> Void = { _, pixels, width, height, stride in
    guard let pixels else { return }
    LinuxFrameInbox.shared.push(pixels, width: Int(width), height: Int(height), stride: Int(stride))
}

private enum LinuxProcessMetrics {
    static func cpuSeconds() -> Double? {
        var usage = rusage()
        guard getrusage(RUSAGE_SELF, &usage) == 0 else { return nil }
        return Double(usage.ru_utime.tv_sec) + Double(usage.ru_utime.tv_usec) / 1_000_000
            + Double(usage.ru_stime.tv_sec) + Double(usage.ru_stime.tv_usec) / 1_000_000
    }

    static func footprintMiB() -> Double? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        return Double(info.phys_footprint) / 1_048_576
    }
}

@MainActor final class LinuxVMSession: ObservableObject {
    static let shared = LinuxVMSession()
    static var framework: URL? {
        let file = Bundle.main.bundleURL.appendingPathComponent("Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu")
        return FileManager.default.fileExists(atPath: file.path) ? file : nil
    }
    static let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].resolvingSymlinksInPath().appendingPathComponent("LinuxARM")
    static var bundledRuntime: URL? {
        let folder = Bundle.main.bundleURL.appendingPathComponent("LinuxRuntime")
        return FileManager.default.fileExists(atPath: folder.appendingPathComponent("manifest.json").path) ? folder : nil
    }
    @Published private(set) var status = "Import the ARM64 Linux runtime folder to begin."
    @Published private(set) var running = false
    @Published private(set) var started = false
    @Published private(set) var connected = false
    @Published private(set) var installing = false
    @Published private(set) var installProgress = 0.0
    @Published private(set) var image: CGImage?
    @Published private(set) var cpuPercent: Double?
    @Published private(set) var memoryMiB: Double?
    @Published private(set) var displayFPS = 0.0
    @Published private(set) var paused = false
    let guestCPUCount = 2
    let guestMemoryMiB = 2048
    var hostCPUCount: Int { ProcessInfo.processInfo.activeProcessorCount }
    var thermalStatus: String {
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: return "Normal"
        case .fair: return "Warm"
        case .serious: return "Hot"
        case .critical: return "Critical"
        @unknown default: return "Unknown"
        }
    }
    @Published var error: String?
    private var timer: Timer?
    private var performance = LinuxPerformanceCounter()
    private var sampleTime = 0.0
    private var displayedFrames = 0
    private var pointerDown = false
    private var lastPointer = (x: 0.5, y: 0.5)
    private var pendingPointer: (x: Double, y: Double, down: Bool)?
    private let qmp = LinuxQMPConnection()
    var installed: Bool { FileManager.default.fileExists(atPath: Self.directory.appendingPathComponent("rootfs.raw").path) }
    private var otherRuntimeStarted: Bool {
        #if MYPC_INTERPRETER
        return false
        #else
        return GameLibrary.shared.sessionStarted || wine_process_is_running() != 0 || wineserver_is_running() != 0
        #endif
    }

    func installBundledRuntime() {
        guard !started, !installing, !otherRuntimeStarted, let source = Self.bundledRuntime else { return }
        installing = true; installProgress = 0
        status = "Installing Linux runtime… Keep My-pc open."
        let destination = Self.directory
        Task {
            do {
                try await Task.detached(priority: .userInitiated) {
                    try LinuxRuntimeInstaller.install(from: source, to: destination) { fraction in
                        Task { @MainActor in self.installProgress = fraction }
                    }
                }.value
                status = LinuxExecutionMode.installedStatus
            } catch { self.error = error.localizedDescription; status = "Linux installation failed." }
            installing = false
        }
    }

    func importRuntime(_ source: URL) {
        guard !started, !installing, !otherRuntimeStarted else { error = "Restart My-pc before importing a Linux runtime."; return }
        guard !installed else { error = "A Linux disk already exists. Import does not overwrite your installed games or account."; return }
        installing = true
        status = "Verifying and copying Linux runtime…"
        let destination = Self.directory
        Task {
            do {
                try await Task.detached(priority: .userInitiated) {
                    let scoped = source.startAccessingSecurityScopedResource()
                    defer { if scoped { source.stopAccessingSecurityScopedResource() } }
                    let fm = FileManager.default
                    let parent = destination.deletingLastPathComponent()
                    let stage = parent.appendingPathComponent("LinuxARM-staging-\(UUID().uuidString)")
                    try fm.createDirectory(at: stage, withIntermediateDirectories: true)
                    defer { try? fm.removeItem(at: stage) }
                    let checksums = try String(contentsOf: source.appendingPathComponent("SHA256SUMS"), encoding: .utf8)
                    let entries = checksums.split(separator: "\n").map { $0.split(separator: " ", omittingEmptySubsequences: true).map(String.init) }
                    for name in ["Image", "initrd.img", "rootfs.raw"] {
                        guard let row = entries.first(where: { $0.count == 2 && $0[1] == name }), row[0].count == 64 else { throw LinuxVMError.invalid("Missing runtime checksum: \(name)") }
                        let from = source.appendingPathComponent(name)
                        guard try from.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey]).isRegularFile == true,
                              from.resolvingSymlinksInPath() == from.standardizedFileURL else { throw LinuxVMError.invalid("Invalid runtime file: \(name)") }
                        let to = stage.appendingPathComponent(name)
                        try fm.copyItem(at: from, to: to)
                        guard try StoreFiles.digest(to) == row[0].lowercased() else { throw LinuxVMError.invalid("Runtime checksum mismatch: \(name)") }
                    }
                    let config = LinuxVMConfiguration(directory: stage, log: parent.appendingPathComponent("linux.log"), control: URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("linux-qmp"))
                    _ = try config.arguments()
                    try fm.moveItem(at: stage, to: destination)
                }.value
                status = LinuxExecutionMode.installedStatus
            } catch { self.error = error.localizedDescription; status = "Runtime import failed." }
            installing = false
        }
    }

    func start() {
        guard !started, !installing, !otherRuntimeStarted else { error = "Restart My-pc before starting another runtime."; return }
        guard let framework = Self.framework else { error = "This build does not contain the Linux framework."; return }
        #if !MYPC_INTERPRETER
        guard jit_check_debugged() else { error = "Enable JIT with StikDebug before starting Linux."; return }
        #endif
        do {
            #if MYPC_INTERPRETER
            let manifestURL = Bundle.main.bundleURL.appendingPathComponent("runtime-backend.json")
            let manifest = try JSONSerialization.jsonObject(with: Data(contentsOf: manifestURL)) as? [String: Any]
            guard manifest?["backend"] as? String == "tcti", manifest?["requiresJIT"] as? Bool == false else {
                throw LinuxVMError.invalid("This app requires the bundled interpreter runtime. Reinstall the correct build.")
            }
            #endif
            let control = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("linux-qmp")
            if FileManager.default.fileExists(atPath: control.path) { try FileManager.default.removeItem(at: control) }
            let log = Self.directory.appendingPathComponent("boot.log")
            let arguments = try LinuxVMConfiguration(directory: Self.directory, log: log, control: control,
                memoryMiB: guestMemoryMiB, cpuCount: guestCPUCount,
                resources: Bundle.main.bundleURL.appendingPathComponent("QEMU")).arguments()
            #if !MYPC_INTERPRETER
            jit_install_trap_handler()
            #endif
            started = true; running = true; status = "Booting ARM64 Linux…"
            UIApplication.shared.isIdleTimerDisabled = true
            beginPerformanceSample()
            let frameTimer = Timer(timeInterval: 1.0 / 30, repeats: true) { _ in
                Task { @MainActor in self.refreshDisplay() }
            }
            RunLoop.main.add(frameTimer, forMode: .common)
            timer = frameTimer
            qmp.connect(path: control.path) { result in
                Task { @MainActor in
                    guard self.running else { return }
                    switch result {
                    case .success: self.connected = true; self.status = "Linux is running."
                    case .failure(let error): self.error = error.localizedDescription
                    }
                }
            }
            Thread.detachNewThread {
                var argv = arguments.map { strdup($0) }
                argv.append(nil)
                defer { argv.forEach { free($0) } }
                var message = [CChar](repeating: 0, count: 2048)
                let code = spc_linux_run(framework.path, Int32(arguments.count), &argv, linuxFrameCallback, nil, &message, message.count)
                let detail = String(cString: message)
                Task { @MainActor in
                    self.qmp.close(); self.connected = false; self.running = false
                    self.timer?.invalidate(); self.timer = nil
                    self.pendingPointer = nil; self.pointerDown = false
                    self.displayFPS = 0; self.cpuPercent = nil; self.paused = false
                    UIApplication.shared.isIdleTimerDisabled = false
                    self.status = code == 0 ? "Linux shut down. Restart My-pc for another session." : "Linux stopped: \(detail)"
                    if code != 0 { self.error = detail }
                }
            }
        } catch { self.error = error.localizedDescription }
    }

    func shutdown() {
        guard connected else { return }
        status = "Shutting Linux down…"
        qmp.send("system_powerdown") { result in
            if case .failure(let error) = result { Task { @MainActor in self.error = error.localizedDescription } }
        }
    }
    func pointer(x: Double, y: Double, down: Bool) {
        guard connected else { return }
        let x = x.isFinite ? min(1, max(0, x)) : 0
        let y = y.isFinite ? min(1, max(0, y)) : 0
        lastPointer = (x, y)
        if down != pointerDown {
            // Never coalesce away a press or release. Ordinary motion is
            // limited to the display cadence instead of flooding the socket.
            pendingPointer = nil; pointerDown = down
            qmp.send("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: down))
        } else { pendingPointer = (x, y, down) }
    }
    func click(x: Double, y: Double, button: LinuxMouseButton = .left) {
        guard connected, !pointerDown else { return }
        pendingPointer = nil
        qmp.click(x: x, y: y, button: button)
    }
    func setBackground(_ background: Bool) {
        guard connected else { return }
        paused = background
        if background {
            if pointerDown {
                qmp.send("input-send-event", arguments: LinuxQMP.pointer(x: lastPointer.x, y: lastPointer.y, down: false))
            }
            pendingPointer = nil; pointerDown = false
            cpuPercent = nil; displayFPS = 0
        } else { beginPerformanceSample() }
        qmp.send(background ? "stop" : "cont")
    }
    private func beginPerformanceSample() {
        performance = LinuxPerformanceCounter(); displayedFrames = 0
        sampleTime = ProcessInfo.processInfo.systemUptime
        _ = performance.sample(time: sampleTime, cpuSeconds: LinuxProcessMetrics.cpuSeconds(), frames: 0)
    }
    private func refreshDisplay() {
        guard !paused else { return }
        if let point = pendingPointer {
            pendingPointer = nil
            qmp.send("input-send-event", arguments: LinuxQMP.pointer(x: point.x, y: point.y, down: point.down))
        }
        if let image = LinuxFrameInbox.shared.take() { self.image = image; displayedFrames += 1 }
        let now = ProcessInfo.processInfo.systemUptime
        guard now - sampleTime >= 1 else { return }
        if let rates = performance.sample(time: now, cpuSeconds: LinuxProcessMetrics.cpuSeconds(), frames: displayedFrames) {
            cpuPercent = rates.cpuPercent; displayFPS = rates.displayFPS
        }
        memoryMiB = LinuxProcessMetrics.footprintMiB()
        sampleTime = now; displayedFrames = 0
    }
    func type(_ text: String) {
        guard connected, !text.isEmpty else { return }
        do {
            let events = try LinuxQMP.text(text)["events"] as? [[String: Any]] ?? []
            sendKeyboard(events)
        }
        catch { self.error = error.localizedDescription }
    }
    func press(_ code: String) {
        guard connected, ["esc", "tab", "ret", "backspace", "up", "down", "left", "right"].contains(code) else { return }
        sendKeyboard([LinuxQMP.key(code, down: true), LinuxQMP.key(code, down: false)])
    }
    private func sendKeyboard(_ events: [[String: Any]]) {
        qmp.sendKeyboard(events) { result in
            if case .failure(let error) = result { Task { @MainActor in self.error = error.localizedDescription } }
        }
    }
}
