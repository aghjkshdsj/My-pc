import Foundation
import SwiftUI
import UIKit
import Darwin
import CryptoKit
import Metal
import GameController

/// A separate, nonblocking local channel. Slow Linux input cannot hold up QMP.
final class LinuxGamepadConnection: @unchecked Sendable {
    private let queue = DispatchQueue(label: "my-pc.linux.gamepad", qos: .userInteractive)
    private let lock = NSLock()
    private var pending: [(Data, Data)] = [] // transition signature, full state
    private var overflow = false
    private var descriptor: Int32 = -1
    private var timer: DispatchSourceTimer?
    private var path = ""
    private var retryAt = 0.0
    private var sending = Data(), received = Data()
    private var offset = 0
    private var guestReady = false
    private var acknowledgedMask: UInt32?
    private var acknowledgedAt = 0.0
    var guestMask: UInt32? {
        lock.lock(); defer { lock.unlock() }
        return ProcessInfo.processInfo.systemUptime - acknowledgedAt < 3 ? acknowledgedMask : nil
    }
    func offer(_ data: Data, signature: Data) {
        lock.lock(); defer { lock.unlock() }
        if pending.last?.0 == signature { pending[pending.count - 1] = (signature, data) }
        else if pending.count < 64 { pending.append((signature, data)) }
        else { pending = [(signature, data)]; overflow = true }
    }
    func start(path: String) {
        queue.async {
            self.path = path
            let timer = DispatchSource.makeTimerSource(queue: self.queue)
            timer.schedule(deadline: .now(), repeating: .milliseconds(16), leeway: .milliseconds(2))
            timer.setEventHandler { [weak self] in self?.drain() }
            self.timer = timer; timer.resume()
        }
    }
    func close() {
        queue.async {
            self.timer?.cancel(); self.timer = nil; self.disconnect()
            self.lock.lock(); self.pending.removeAll(); self.overflow = false; self.lock.unlock()
        }
    }
    private func disconnect() {
        if descriptor >= 0 { Darwin.close(descriptor); descriptor = -1 }
        sending.removeAll(); received.removeAll(); offset = 0
        guestReady = false
        lock.lock(); acknowledgedMask = nil; lock.unlock()
    }
    private func drain() {
        let now = ProcessInfo.processInfo.systemUptime
        lock.lock(); let reset = overflow; overflow = false; lock.unlock()
        if reset { disconnect() }
        if descriptor < 0 {
            guard now >= retryAt, path.utf8.count < 100 else { return }
            retryAt = now + 1
            let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
            guard fd >= 0 else { return }
            _ = fcntl(fd, F_SETFL, O_NONBLOCK)
            var flag: Int32 = 1
            setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &flag, socklen_t(MemoryLayout<Int32>.size))
            var address = sockaddr_un()
            address.sun_family = sa_family_t(AF_UNIX); address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
            _ = withUnsafeMutableBytes(of: &address.sun_path) { bytes in
                path.withCString { strlcpy(bytes.baseAddress!.assumingMemoryBound(to: CChar.self), $0, bytes.count) }
            }
            let result = withUnsafePointer(to: &address) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
            }
            guard result == 0 else { Darwin.close(fd); return }
            descriptor = fd
        }
        // Linux opens the virtio port after boot. Before its first ACK, only
        // the newest full state matters; do not replay pre-boot button presses.
        if !guestReady {
            lock.lock()
            if let latest = pending.last { pending = [latest] }
            lock.unlock()
        }
        var buffer = [UInt8](repeating: 0, count: 256)
        let count = Darwin.recv(descriptor, &buffer, buffer.count, 0)
        if count == 0 { disconnect(); return }
        if count < 0 {
            if errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR { disconnect(); return }
        } else {
            received.append(contentsOf: buffer.prefix(count))
        }
        while received.count >= 16 {
            let bytes = Array(received.prefix(16)); received.removeFirst(16)
            guard Array(bytes[0..<4]) == Array("ACK1".utf8), bytes[4] == 1,
                  bytes[5..<8].allSatisfy({ $0 == 0 }), bytes[8] <= 15,
                  bytes[9..<16].allSatisfy({ $0 == 0 }) else { disconnect(); return }
            lock.lock(); acknowledgedMask = UInt32(bytes[8]); acknowledgedAt = now; lock.unlock()
            guestReady = true
        }
        guard guestReady else { return }
        // Once ready, preserve partial frames and button edges. Coalesce only
        // queued analog motion with an unchanged button/connection signature.
        for _ in 0..<32 {
            if sending.isEmpty {
                lock.lock()
                if !pending.isEmpty { sending = pending.removeFirst().1 }
                lock.unlock(); offset = 0
                if sending.isEmpty { break }
            }
            let count = sending.withUnsafeBytes { bytes in
                Darwin.send(descriptor, bytes.baseAddress!.advanced(by: offset), sending.count - offset, 0)
            }
            if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) { break }
            guard count > 0 else { disconnect(); return }
            offset += count
            if offset == sending.count { sending.removeAll(); offset = 0 }
        }
    }
}

/// A single serial owner for the local QMP socket. No listener is exposed on LAN.
final class LinuxQMPConnection: @unchecked Sendable {
    private let queue = DispatchQueue(label: "my-pc.linux.qmp", qos: .userInteractive)
    private var descriptor: Int32 = -1
    private var requestID = 0
    private let motion = LinuxPointerMailbox()
    private let metricsLock = NSLock()
    private var lastInputMilliseconds: Double?
    var inputMilliseconds: Double? {
        metricsLock.lock(); defer { metricsLock.unlock() }
        return lastInputMilliseconds
    }

    func move(x: Double, y: Double, down: Bool) {
        if motion.offer(.init(x: x, y: y, down: down)) { scheduleMotion() }
    }
    func discardMotion() { motion.discard() }
    private func scheduleMotion() {
        queue.async {
            if let point = self.motion.take() {
                try? self.request("input-send-event", arguments: LinuxQMP.pointer(x: point.x, y: point.y, down: point.down))
            }
            if self.motion.finish() { self.scheduleMotion() }
        }
    }

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
        motion.discard()
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
        motion.discard()
        queue.async {
            do {
                try self.request("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: true, button: button))
                Thread.sleep(forTimeInterval: 0.01)
                try self.request("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: false, button: button))
            } catch { /* A disconnected session cannot accept pointer input. */ }
        }
    }

    private func request(_ command: String, arguments: [String: Any]) throws {
        let started = ProcessInfo.processInfo.systemUptime
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
            if try LinuxQMP.reply(line(), id: requestID) {
                if command == "input-send-event" {
                    metricsLock.lock()
                    lastInputMilliseconds = (ProcessInfo.processInfo.systemUptime - started) * 1000
                    metricsLock.unlock()
                }
                return
            }
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

/// Tests use their own nonblocking port, independent of keyboard grabs and UART.
/// Disconnects never replay a start/cancel command; status only replays results.
final class LinuxDiagnosticConnection: @unchecked Sendable {
    private let queue = DispatchQueue(label: "my-pc.linux.diagnostics", qos: .userInitiated)
    private let lock = NSLock()
    private var readyAt = 0.0
    private var descriptor: Int32 = -1
    private var timer: DispatchSourceTimer?
    private var path = "", retryAt = 0.0
    private var received = Data(), sending = Data()
    private var offset = 0
    private var pending = [(Data, (Bool) -> Void)]()
    private var sent: ((Bool) -> Void)?
    private var receiver: ((LinuxDiagnosticMessage) -> Void)?
    var ready: Bool {
        lock.lock(); defer { lock.unlock() }
        return readyAt > 0 && ProcessInfo.processInfo.systemUptime - readyAt < 4
    }
    static func identifier() -> String { UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased() }
    func start(path: String, receive: @escaping (LinuxDiagnosticMessage) -> Void) {
        queue.async {
            self.path = path; self.receiver = receive
            let timer = DispatchSource.makeTimerSource(queue: self.queue)
            timer.schedule(deadline: .now(), repeating: .milliseconds(50), leeway: .milliseconds(5))
            timer.setEventHandler { [weak self] in self?.drain() }
            self.timer = timer; timer.resume()
        }
    }
    func send(id: String, command: String, target: String? = nil, completion: @escaping (Bool) -> Void = { _ in }) {
        guard let data = LinuxDiagnosticMessage.request(id: id, command: command, target: target) else { completion(false); return }
        queue.async {
            guard self.ready, self.descriptor >= 0, self.pending.count < 8 else { completion(false); return }
            self.pending.append((data, completion))
        }
    }
    func close() {
        queue.async { self.timer?.cancel(); self.timer = nil; self.disconnect(); self.receiver = nil }
    }
    private func disconnect() {
        if descriptor >= 0 { Darwin.close(descriptor); descriptor = -1 }
        lock.lock(); readyAt = 0; lock.unlock()
        received.removeAll(); sending.removeAll(); offset = 0
        sent?(false); sent = nil
        let dropped = pending; pending.removeAll()
        dropped.forEach { $0.1(false) }
    }
    private func drain() {
        let now = ProcessInfo.processInfo.systemUptime
        if descriptor < 0 {
            guard now >= retryAt, path.utf8.count < 100 else { return }
            retryAt = now + 1
            let fd = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
            guard fd >= 0 else { return }
            _ = fcntl(fd, F_SETFL, O_NONBLOCK)
            var flag: Int32 = 1
            setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &flag, socklen_t(MemoryLayout<Int32>.size))
            var address = sockaddr_un()
            address.sun_family = sa_family_t(AF_UNIX); address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
            _ = withUnsafeMutableBytes(of: &address.sun_path) { bytes in
                path.withCString { strlcpy(bytes.baseAddress!.assumingMemoryBound(to: CChar.self), $0, bytes.count) }
            }
            let result = withUnsafePointer(to: &address) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
            }
            guard result == 0 else { Darwin.close(fd); return }
            descriptor = fd
        }
        var buffer = [UInt8](repeating: 0, count: 4096)
        for _ in 0..<8 {
            let count = Darwin.recv(descriptor, &buffer, buffer.count, 0)
            if count == 0 { disconnect(); return }
            if count < 0 {
                if errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR { disconnect() }
                break
            }
            received.append(contentsOf: buffer.prefix(count))
            while let newline = received.firstIndex(of: 10) {
                let data = Data(received[..<newline]); received.removeSubrange(...newline)
                guard let message = LinuxDiagnosticMessage.parse(data) else { disconnect(); return }
                if case .ready = message {
                    let first = !ready
                    lock.lock(); readyAt = now; lock.unlock()
                    if first, let status = LinuxDiagnosticMessage.request(id: Self.identifier(), command: "status") {
                        pending.append((status, { _ in }))
                    }
                }
                receiver?(message)
            }
            guard received.count < LinuxDiagnosticMessage.maxBytes else { disconnect(); return }
        }
        for _ in 0..<8 {
            if sending.isEmpty {
                guard !pending.isEmpty else { break }
                let next = pending.removeFirst(); sending = next.0; sent = next.1; offset = 0
            }
            let count = sending.withUnsafeBytes { bytes in
                Darwin.send(descriptor, bytes.baseAddress!.advanced(by: offset), sending.count - offset, 0)
            }
            if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) { break }
            guard count > 0 else { disconnect(); return }
            offset += count
            if offset == sending.count { sending.removeAll(); sent?(true); sent = nil; offset = 0 }
        }
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
    private let gamepad = LinuxGamepadConnection()
    private let diagnostics = LinuxDiagnosticConnection()
    private var controllers: [GCController?] = Array(repeating: nil, count: 4)
    private var controllerSequence: UInt32 = 0
    private var lastControllerFrame = Data()
    private var lastControllerTime = 0.0
    @Published private(set) var controllerNames = [String]()
    @Published private(set) var controllerGuestCount: Int?
    private var controllerPanelVisible = false
    var controllerStatus: String {
        guard !controllerNames.isEmpty else { return "Connect Backbone Pro or another iOS gamepad." }
        guard let count = controllerGuestCount else { return "\(controllerNames.joined(separator: ", ")) · waiting for Linux gamepad bridge…" }
        return "\(controllerNames.joined(separator: ", ")) · \(count) Linux gamepad\(count == 1 ? "" : "s")"
    }
    func setControllerPanelVisible(_ visible: Bool) {
        controllerPanelVisible = visible
        pollControllers(force: true)
    }
    func openBigPicture() {
        guard connected, hardwareTestsReady, !paused else { return }
        sendKeyboard(LinuxHardwareTestKind.shortcut("f7"))
    }
    private func pollControllers(force: Bool = false) {
        guard running else { return }
        let available = GCController.controllers().filter { $0.extendedGamepad != nil }
        for index in controllers.indices {
            if let old = controllers[index], !available.contains(where: { $0 === old }) { controllers[index] = nil }
        }
        for controller in available where !controllers.contains(where: { $0 === controller }) {
            if let index = controllers.firstIndex(where: { $0 == nil }) { controllers[index] = controller }
        }
        let enabled = !controllerPanelVisible && !paused && UIApplication.shared.applicationState == .active
        var frame = Data(), signature = Data(), names = [String]()
        controllerSequence &+= 1
        for index in controllers.indices {
            var state = LinuxGamepadState()
            if let controller = controllers[index], let pad = controller.extendedGamepad {
                names.append(controller.vendorName ?? "iOS gamepad")
                state.connected = true
                if enabled {
                    let values: [(GCControllerButtonInput?, UInt32)] = [
                        (pad.buttonA,0x1000),(pad.buttonB,0x2000),(pad.buttonX,0x4000),(pad.buttonY,0x8000),
                        (pad.leftShoulder,0x100),(pad.rightShoulder,0x200),(pad.dpad.up,1),(pad.dpad.down,2),
                        (pad.dpad.left,4),(pad.dpad.right,8),(pad.buttonMenu,0x10),(pad.buttonOptions,0x20),
                        (pad.leftThumbstickButton,0x40),(pad.rightThumbstickButton,0x80),(pad.buttonHome,0x400)]
                    for (button, mask) in values where button?.isPressed == true { state.buttons |= mask }
                    state.axes = [LinuxGamepadState.axis(pad.leftThumbstick.xAxis.value),
                        LinuxGamepadState.axis(pad.leftThumbstick.yAxis.value,inverted: true),
                        LinuxGamepadState.axis(pad.rightThumbstick.xAxis.value),
                        LinuxGamepadState.axis(pad.rightThumbstick.yAxis.value,inverted: true),
                        LinuxGamepadState.axis(pad.leftTrigger.value,trigger: true),
                        LinuxGamepadState.axis(pad.rightTrigger.value,trigger: true)]
                }
            }
            let packet = state.packet(slot: index, sequence: 0)
            signature.append(packet.subdata(in: 4..<8)); signature.append(packet.subdata(in: 12..<16))
            frame.append(packet)
        }
        let now = ProcessInfo.processInfo.systemUptime
        if force || frame != lastControllerFrame || now-lastControllerTime >= 0.5 {
            lastControllerFrame = frame; lastControllerTime = now
            for index in 0..<4 {
                for offset in 0..<4 { frame[index*32+8+offset] = UInt8(truncatingIfNeeded: controllerSequence >> (offset*8)) }
            }
            gamepad.offer(frame, signature: signature)
        }
        if controllerNames != names { controllerNames = names }
        let count = gamepad.guestMask.map { $0.nonzeroBitCount }
        if controllerGuestCount != count { controllerGuestCount = count }
    }
    private static var initialCPUSelection: Int {
        UserDefaults.standard.object(forKey: "linuxCPUCount") == nil
            ? LinuxExecutionMode.defaultCPUSelection : UserDefaults.standard.integer(forKey: "linuxCPUCount")
    }
    static var framework: URL? {
        let file = Bundle.main.bundleURL.appendingPathComponent("Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu")
        return FileManager.default.fileExists(atPath: file.path) ? file : nil
    }
    static let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].resolvingSymlinksInPath().appendingPathComponent("LinuxARM")
    static var bundledRuntime: URL? {
        let folder = Bundle.main.bundleURL.appendingPathComponent("LinuxRuntime")
        return FileManager.default.fileExists(atPath: folder.appendingPathComponent("manifest.json").path) ? folder : nil
    }
    static var metalAvailable: Bool {
        #if MYPC_INTERPRETER
        return false
        #else
        return bundledRuntime.map { FileManager.default.fileExists(atPath: $0.appendingPathComponent("graphics.json").path) } ?? false
        #endif
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
    @Published private(set) var inputMilliseconds: Double?
    @Published private(set) var hardwareTestsReady = false
    @Published private(set) var hardwareTestWaiting = false
    @Published private(set) var hardwareObservation: LinuxHardwareObservation?
    @Published private(set) var cpuObservation: LinuxHardwareObservation?
    @Published private(set) var gpuObservation: LinuxHardwareObservation?
    @Published private(set) var nativeCPUMilliseconds: Double?
    @Published private(set) var nativeCPUChecksum: String?
    @Published private(set) var hardwareElapsedSeconds = 0.0
    @Published private(set) var hardwareHeartbeatAge = 0.0
    @Published private(set) var hardwareCancellationRequested = false
    @Published private(set) var hardwareTestUnresponsive = false
    @Published private(set) var hardwareRequestedKind: LinuxHardwareTestKind?
    @Published private(set) var hardwareLaunchStatus = "idle"
    @Published private(set) var hardwareLauncherAcknowledged = false
    @Published private(set) var hardwareCancellationAcknowledged = false
    @Published private(set) var hardwareFailure: String?
    @Published private(set) var hardwareTestActive = false
    @Published private(set) var hardwareGuestBusy = false
    private var hardwareRequestIdentifier: String?
    private var hardwareCancelIdentifier: String?
    private var hardwareCancelAttemptTime = 0.0
    private var hardwareHeartbeat = LinuxHardwareHeartbeat()
    private var hardwareBackgroundTime: Double?
    private var backgroundRequested = false
    private var cpuReportJSON: String?
    private var gpuReportJSON: String?
    private var hardwareRequestTime = 0.0
    var hardwareTestBusy: Bool { hardwareTestActive }
    var hardwareTestStatus: String {
        if let hardwareFailure {
            switch hardwareFailure {
            case "launch-failed", "runner-exited": return "The Linux test runner could not start or exited before reporting results."
            case "launch-timeout": return "The Linux test runner did not start within its deadline."
            case "report-invalid": return "The Linux test runner returned an invalid report."
            case "launch-cancelled": return "The test was stopped before it started."
            case "runner-busy": return "Linux already has a diagnostic test running. Waiting for it to finish."
            case "transport-lost": return "The diagnostic connection was interrupted. Waiting for Linux to confirm the test state."
            default: return "Linux has not confirmed that the diagnostic stopped."
            }
        }
        if hardwareTestUnresponsive { return "Linux did not acknowledge stopping the test. Shut down Linux or restart My-pc before retrying." }
        if hardwareCancellationRequested { return "Stopping the diagnostic test…" }
        if paused && hardwareTestBusy { return "Test paused while My-pc is in the background." }
        if hardwareTestWaiting { return hardwareLauncherAcknowledged ? "Linux accepted the test. Waiting for its first workload heartbeat…" : "Waiting for Linux to acknowledge the test request…" }
        guard let result = hardwareObservation else { return hardwareTestsReady ? "Ready to test." : "Tests become available after the Metal startup update and desktop boot." }
        return "\(result.stageTitle) · \(result.status)"
    }
    var hardwareProgress: Double {
        guard let observation = hardwareObservation else {
            return hardwareTestWaiting && nativeCPUMilliseconds != nil && hardwareRequestedKind == .cpu ? 0.05 : 0
        }
        if observation.status == "complete" { return 1 }
        let percent = observation.progressPercent ?? 0
        return (observation.kind == .cpu ? 5 + percent * 0.95 : percent) / 100
    }
    var hardwareHeartbeatStatus: String {
        if !hardwareTestBusy { return "Results stay available below." }
        if paused { return "Resume My-pc to continue the test." }
        if hardwareTestUnresponsive { return "No response from Linux. The last percentage is retained." }
        if hardwareHeartbeatAge >= 15 { return "No Linux heartbeat for \(Int(hardwareHeartbeatAge)) seconds." }
        if hardwareTestWaiting { return "Waiting for the first Linux heartbeat." }
        return "Linux heartbeat received \(Int(hardwareHeartbeatAge)) seconds ago."
    }
    var hardwareReport: String {
        var report: [String: Any] = ["schema": 1,
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "commit": Bundle.main.object(forInfoDictionaryKey: "SomethingPCBuildCommit") as? String ?? "unknown",
            "graphics": graphicsMode.rawValue, "virtual_cpus": guestCPUCount,
            "guest_renderer": guestGraphics?.renderer ?? "unverified",
            "guest_readback_ok": guestGraphics?.readbackOK ?? false,
            "guest_virgl_verified": guestGraphics?.verifiedVirgl ?? false,
            "host_available_cpus": hostCPUCount, "guest_memory_mib": guestMemoryMiB,
            "thermal_state": thermalStatus, "low_power_mode": ProcessInfo.processInfo.isLowPowerModeEnabled,
            "host_app_cpu_percent": cpuPercent.map { $0 as Any } ?? NSNull(),
            "host_app_memory_mib": memoryMiB.map { $0 as Any } ?? NSNull(),
            "display_fps": displayFPS, "input_ack_ms": inputMilliseconds.map { $0 as Any } ?? NSNull(),
            "native_ios_single_worker_ms": nativeCPUMilliseconds.map { $0 as Any } ?? NSNull(),
            "native_ios_checksum": nativeCPUChecksum.map { $0 as Any } ?? NSNull(),
            "native_ios_iterations": LinuxNativeCPUBenchmark.iterations,
            "vm_paused": paused, "vm_connected": connected,
            "hardware_monitor": ["active_elapsed_s": hardwareElapsedSeconds,
                "guest_heartbeat_age_s": hardwareHeartbeatAge, "cancellation_requested": hardwareCancellationRequested,
                "unresponsive": hardwareTestUnresponsive, "transport": "private-virtio-serial",
                "launcher_ready": hardwareTestsReady, "request_kind": hardwareRequestedKind?.rawValue as Any? ?? NSNull(),
                "service_ready": diagnostics.ready, "guest_busy": hardwareGuestBusy,
                "request_id": hardwareRequestIdentifier as Any? ?? NSNull(), "launch_status": hardwareLaunchStatus,
                "launcher_acknowledged": hardwareLauncherAcknowledged,
                "cancellation_acknowledged": hardwareCancellationAcknowledged,
                "failure": hardwareFailure as Any? ?? NSNull()]]
        for (key, json) in [("cpu_test", cpuReportJSON), ("gpu_test", gpuReportJSON)] {
            if let json, let value = try? JSONSerialization.jsonObject(with: Data(json.utf8)) { report[key] = value }
        }
        return (try? JSONSerialization.data(withJSONObject: report, options: [.sortedKeys, .prettyPrinted]))
            .map { String(decoding: $0, as: UTF8.self) } ?? "Hardware report unavailable."
    }
    func runHardwareTest(_ kind: LinuxHardwareTestKind) {
        guard running, connected, !paused, hardwareTestsReady, !hardwareTestBusy, !hardwareTestUnresponsive else { return }
        hardwareTestWaiting = true
        hardwareTestActive = true
        hardwareGuestBusy = true; hardwareTestsReady = false
        hardwareRequestIdentifier = LinuxDiagnosticConnection.identifier()
        hardwareCancelIdentifier = nil
        hardwareLaunchStatus = "preparing"
        hardwareLauncherAcknowledged = false; hardwareCancellationAcknowledged = false; hardwareFailure = nil
        hardwareObservation = nil
        hardwareRequestTime = ProcessInfo.processInfo.systemUptime
        hardwareHeartbeat.start(now: hardwareRequestTime)
        hardwareRequestedKind = kind
        hardwareElapsedSeconds = 0; hardwareHeartbeatAge = 0
        hardwareCancellationRequested = false; hardwareTestUnresponsive = false
        guard let requestID = hardwareRequestIdentifier else { return }
        Task {
            if kind == .cpu {
                let result = await Task.detached(priority: .userInitiated) { LinuxNativeCPUBenchmark.run() }.value
                guard hardwareRequestIdentifier == requestID, hardwareTestActive else { return }
                nativeCPUMilliseconds = result.milliseconds; nativeCPUChecksum = result.checksum
            }
            guard running, connected, hardwareTestActive, !hardwareCancellationRequested,
                  hardwareRequestIdentifier == requestID else { return }
            let id = requestID
            hardwareLaunchStatus = "sending"
            diagnostics.send(id: id, command: kind.rawValue) { [weak self] sent in
                Task { @MainActor in
                    guard let self, self.hardwareRequestIdentifier == id, self.hardwareTestActive else { return }
                    if !sent { self.hardwareFailure = "transport-lost" }
                    else if !self.hardwareLauncherAcknowledged { self.hardwareLaunchStatus = "sent" }
                }
            }
        }
    }
    func cancelHardwareTest() {
        guard connected, hardwareTestBusy else { return }
        hardwareCancellationRequested = true
        let now = ProcessInfo.processInfo.systemUptime
        hardwareHeartbeat.cancel(now: now)
        sendHardwareCancellation(now: now)
    }
    private func sendHardwareCancellation(now: Double) {
        guard let target = hardwareRequestIdentifier else { return }
        let id = LinuxDiagnosticConnection.identifier(); hardwareCancelIdentifier = id
        hardwareCancelAttemptTime = now
        diagnostics.send(id: id, command: "cancel", target: target) { [weak self] sent in
            if !sent { Task { @MainActor in self?.hardwareFailure = "transport-lost" } }
        }
    }
    private func receiveDiagnostic(_ message: LinuxDiagnosticMessage) {
        guard running else { return }
        let now = ProcessInfo.processInfo.systemUptime
        switch message {
        case let .ready(busy):
            hardwareGuestBusy = busy
            hardwareTestsReady = diagnostics.ready && !busy
            if !busy, hardwareFailure == "runner-busy" { hardwareFailure = nil; hardwareTestUnresponsive = false }
            if hardwareTestActive, hardwareCancellationRequested, !hardwareCancellationAcknowledged,
               now - hardwareCancelAttemptTime >= 5 { sendHardwareCancellation(now: now) }
        case let .ack(id, command, status):
            if id == hardwareCancelIdentifier, command == "cancel" {
                hardwareCancellationAcknowledged = status == "accepted" || status == "idle"
                if status == "stale" {
                    hardwareFailure = "runner-busy"; hardwareTestUnresponsive = true
                    hardwareTestActive = false; hardwareTestWaiting = false
                }
                if status == "idle" {
                    hardwareTestActive = false; hardwareTestWaiting = false
                    // Stop can arrive after a truthful terminal report while
                    // its runner is still exiting. Wait for service readiness
                    // and preserve completion instead of inventing cancellation.
                    hardwareGuestBusy = true; hardwareTestsReady = false
                    if let observation = hardwareObservation, observation.status != "running" {
                        hardwareLaunchStatus = observation.status
                    } else { hardwareLaunchStatus = "idle" }
                    hardwareCancellationRequested = false
                    hardwareTestUnresponsive = false; hardwareFailure = nil
                }
                return
            }
            guard id == hardwareRequestIdentifier, command == hardwareRequestedKind?.rawValue else { return }
            if status == "accepted" || status == "duplicate" {
                hardwareLauncherAcknowledged = true; hardwareLaunchStatus = "accepted"
                if hardwareFailure == "transport-lost" { hardwareFailure = nil }
            } else if status == "busy" {
                hardwareLaunchStatus = "busy"; hardwareFailure = "runner-busy"
                hardwareTestActive = false; hardwareTestWaiting = false; hardwareGuestBusy = true
                hardwareTestsReady = false; hardwareTestUnresponsive = false
            }
        case let .state(id, observation, json):
            guard id == hardwareRequestIdentifier, observation.kind == hardwareRequestedKind,
                  hardwareHeartbeat.receive(json, now: now) else { return }
            hardwareLauncherAcknowledged = true; hardwareLaunchStatus = "running"
            hardwareTestWaiting = false; hardwareObservation = observation
            hardwareElapsedSeconds = hardwareHeartbeat.elapsed(now: now); hardwareHeartbeatAge = 0
            if hardwareFailure == "transport-lost" { hardwareFailure = nil }
            if observation.status != "running" {
                hardwareTestActive = false; hardwareLaunchStatus = observation.status
                hardwareTestsReady = false; hardwareGuestBusy = true // wait for idle after child cleanup
                hardwareCancellationRequested = false; hardwareTestUnresponsive = false; hardwareFailure = nil
            }
            if observation.kind == .cpu { cpuObservation = observation; cpuReportJSON = json }
            else { gpuObservation = observation; gpuReportJSON = json }
        case let .failure(id, code, busy):
            guard id == hardwareRequestIdentifier else { return }
            hardwareFailure = code; hardwareLaunchStatus = "failed"
            if !busy {
                hardwareTestActive = false; hardwareTestWaiting = false
                hardwareGuestBusy = false; hardwareTestsReady = diagnostics.ready
                hardwareCancellationRequested = false; hardwareTestUnresponsive = false
            }
        }
    }
    @Published private(set) var paused = false
    @Published private(set) var cpuSelection = LinuxVMSession.initialCPUSelection
    @Published private(set) var graphicsMode = LinuxGraphicsMode.initial(metalAvailable: LinuxVMSession.metalAvailable,
        saved: UserDefaults.standard.string(forKey: "linuxGraphicsMode"))
    @Published private(set) var guestGraphics: LinuxGuestGraphics?
    @Published private(set) var guestCPUCount = LinuxCPUSelection.resolve(
        LinuxVMSession.initialCPUSelection, hostCount: ProcessInfo.processInfo.activeProcessorCount)
    let guestMemoryMiB = 2048
    var hostCPUCount: Int { LinuxCPUSelection.available(ProcessInfo.processInfo.activeProcessorCount) }
    var graphicsSummary: String {
        guard graphicsMode == .metal else { return "GPU: software selected" }
        guard let observed = guestGraphics, !observed.renderer.isEmpty else { return "GPU: Metal requested · unverified" }
        return observed.verifiedVirgl ? "GPU: virgl → Metal verified · use —" : "GPU: software fallback or failed readback"
    }
    var graphicsReport: String {
        let report: [String: Any] = ["build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "commit": Bundle.main.object(forInfoDictionaryKey: "SomethingPCBuildCommit") as? String ?? "unknown",
            "selected_backend": graphicsMode.rawValue,
            "guest_renderer": guestGraphics?.renderer ?? "unverified",
            "guest_readback_ok": guestGraphics?.readbackOK ?? false,
            "guest_virgl_verified": guestGraphics?.verifiedVirgl ?? false,
            "steam_cef_renderer": "unverified",
            "metal_device": MTLCreateSystemDefaultDevice()?.name ?? "unavailable",
            "virtual_cpus": guestCPUCount, "guest_memory_mib": guestMemoryMiB,
            "input_ack_ms": inputMilliseconds.map { $0 as Any } ?? NSNull(),
            "thermal_state": thermalStatus, "translation_cache_mib": LinuxExecutionMode.requiresJIT ? 256 : 128]
        return (try? JSONSerialization.data(withJSONObject: report, options: [.sortedKeys, .prettyPrinted]))
            .map { String(decoding: $0, as: UTF8.self) } ?? "Graphics report unavailable."
    }
    func selectGraphics(_ mode: LinuxGraphicsMode) {
        guard !started, mode == .software || Self.metalAvailable else { return }
        graphicsMode = mode
        UserDefaults.standard.set(mode.rawValue, forKey: "linuxGraphicsMode")
    }
    private func verifiedGraphicsInitrd() throws -> URL? {
        if graphicsMode == .software {
            if Self.graphicsUpdateFailed(Self.directory.appendingPathComponent("boot.log")) { return nil }
            return try? verifiedBootUpdate()
        }
        return try verifiedBootUpdate()
    }
    private func verifiedBootUpdate() throws -> URL? {
        guard Self.metalAvailable, let source = Self.bundledRuntime else {
            if graphicsMode == .software { return nil }
            throw LinuxVMError.invalid("This build or device cannot start Metal graphics. Choose Software.")
        }
        if graphicsMode == .metal && MTLCreateSystemDefaultDevice() == nil { throw LinuxVMError.invalid("Metal is unavailable on this device.") }
        let metadata = source.appendingPathComponent("graphics.json")
        let data = try Data(contentsOf: metadata)
        guard data.count <= 8192 else { throw LinuxVMError.invalid("Invalid graphics update metadata.") }
        let manifest = try JSONDecoder().decode(LinuxGraphicsManifest.self, from: data)
        let update = source.appendingPathComponent("graphics-initrd.img")
        guard manifest.schema == 1, manifest.backend == "virgl-metal",
              (1...268_435_456).contains(manifest.initrdBytes),
              try update.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey]).isRegularFile == true,
              try update.resourceValues(forKeys: [.fileSizeKey]).fileSize == manifest.initrdBytes,
              try StoreFiles.digest(update) == manifest.initrdSHA256 else {
            throw LinuxVMError.invalid("The Metal boot update failed verification. Choose Software.")
        }
        guard try StoreFiles.digest(Self.directory.appendingPathComponent("Image")) == manifest.kernelSHA256 else {
            throw LinuxVMError.invalid("This installed Linux kernel does not match the Metal update. Choose Software; your disk will be preserved.")
        }
        return update
    }
    private static func graphicsUpdateFailed(_ log: URL) -> Bool {
        guard let handle = try? FileHandle(forReadingFrom: log) else { return false }
        defer { try? handle.close() }
        guard let length = try? handle.seekToEnd() else { return false }
        try? handle.seek(toOffset: length > 65_536 ? length - 65_536 : 0)
        let data = (try? handle.read(upToCount: 65_536)) ?? Data()
        return String(decoding: data, as: UTF8.self).contains("MYPC_GRAPHICS_UPDATE_FAILED")
    }
    func selectCPUCount(_ count: Int) {
        guard !started else { return }
        cpuSelection = count > 0 ? min(hostCPUCount, count) : 0
        UserDefaults.standard.set(cpuSelection, forKey: "linuxCPUCount")
        guestCPUCount = LinuxCPUSelection.resolve(cpuSelection, hostCount: hostCPUCount)
    }
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
            let controller = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("l-pad")
            if FileManager.default.fileExists(atPath: controller.path) { try FileManager.default.removeItem(at: controller) }
            let diagnostic = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("l-test")
            if FileManager.default.fileExists(atPath: diagnostic.path) { try FileManager.default.removeItem(at: diagnostic) }
            let log = Self.directory.appendingPathComponent("boot.log")
            guestCPUCount = LinuxCPUSelection.resolve(cpuSelection, hostCount: hostCPUCount)
            let arguments = try LinuxVMConfiguration(directory: Self.directory, log: log, control: control,
                memoryMiB: guestMemoryMiB, cpuCount: guestCPUCount,
                resources: Bundle.main.bundleURL.appendingPathComponent("QEMU"),
                graphics: graphicsMode, graphicsInitrd: verifiedGraphicsInitrd(), controller: controller, diagnostics: diagnostic).arguments()
            #if !MYPC_INTERPRETER
            jit_install_trap_handler()
            #endif
            guestGraphics = nil
            hardwareTestsReady = false; hardwareTestWaiting = false; hardwareObservation = nil
            cpuObservation = nil; gpuObservation = nil; cpuReportJSON = nil; gpuReportJSON = nil
            nativeCPUMilliseconds = nil; nativeCPUChecksum = nil
            hardwareHeartbeat = LinuxHardwareHeartbeat(); hardwareBackgroundTime = nil
            hardwareElapsedSeconds = 0; hardwareHeartbeatAge = 0; hardwareRequestedKind = nil
            hardwareCancellationRequested = false; hardwareTestUnresponsive = false
            hardwareTestActive = false; hardwareRequestIdentifier = nil; hardwareCancelIdentifier = nil
            hardwareGuestBusy = false
            hardwareLaunchStatus = "idle"; hardwareLauncherAcknowledged = false
            hardwareCancellationAcknowledged = false; hardwareFailure = nil
            started = true; running = true; status = "Booting ARM64 Linux with \(guestCPUCount) CPU cores · \(graphicsMode.title)…"
            gamepad.start(path: controller.path)
            diagnostics.start(path: diagnostic.path) { [weak self] message in
                Task { @MainActor in self?.receiveDiagnostic(message) }
            }
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
                    case .success:
                        self.connected = true; self.status = "Linux is running with \(self.guestCPUCount) virtual CPU cores."
                        self.setBackground(self.backgroundRequested)
                    case .failure(let error): self.error = error.localizedDescription
                    }
                }
            }
            let vmThread = Thread {
                var argv = arguments.map { strdup($0) }
                argv.append(nil)
                defer { argv.forEach { free($0) } }
                var message = [CChar](repeating: 0, count: 2048)
                let code = spc_linux_run(framework.path, Int32(arguments.count), &argv, linuxFrameCallback, nil, &message, message.count)
                let detail = String(cString: message)
                Task { @MainActor in
                    self.gamepad.close(); self.controllerGuestCount = nil
                    self.diagnostics.close()
                    self.qmp.close(); self.connected = false; self.running = false
                    self.timer?.invalidate(); self.timer = nil
                    self.pendingPointer = nil; self.pointerDown = false
                    self.displayFPS = 0; self.cpuPercent = nil; self.paused = false
                    self.hardwareTestsReady = false; self.hardwareTestWaiting = false
                    self.hardwareTestActive = false
                    self.hardwareCancellationRequested = false
                    UIApplication.shared.isIdleTimerDisabled = false
                    self.status = code == 0 ? "Linux shut down. Restart My-pc for another session." : "Linux stopped: \(detail)"
                    if code != 0 { self.error = detail }
                    if self.graphicsMode == .metal, Self.graphicsUpdateFailed(log) {
                        self.error = "The Metal startup update failed. Restart My-pc and choose Software. Your Linux disk was preserved."
                    }
                }
            }
            // The foreground VM creates its CPU and I/O threads here. Give
            // iOS an explicit scheduling preference for this user-started work.
            vmThread.qualityOfService = .userInitiated
            vmThread.name = "My-pc Linux VM"
            vmThread.start()
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
            qmp.discardMotion()
            qmp.send("input-send-event", arguments: LinuxQMP.pointer(x: x, y: y, down: down))
        } else { pendingPointer = (x, y, down) }
    }
    func click(x: Double, y: Double, button: LinuxMouseButton = .left) {
        guard connected, !pointerDown else { return }
        pendingPointer = nil
        qmp.click(x: x, y: y, button: button)
    }
    func setBackground(_ background: Bool) {
        backgroundRequested = background
        guard connected else { return }
        guard paused != background else { return }
        paused = background
        pollControllers(force: true)
        if background {
            hardwareBackgroundTime = ProcessInfo.processInfo.systemUptime
            if pointerDown {
                qmp.send("input-send-event", arguments: LinuxQMP.pointer(x: lastPointer.x, y: lastPointer.y, down: false))
            }
            pendingPointer = nil; pointerDown = false
            qmp.discardMotion()
            cpuPercent = nil; displayFPS = 0
        } else {
            if let time = hardwareBackgroundTime {
                hardwareHeartbeat.excludeBackgroundTime(max(0, ProcessInfo.processInfo.systemUptime - time))
            }
            hardwareBackgroundTime = nil
            beginPerformanceSample()
        }
        qmp.send(background ? "stop" : "cont")
    }
    private func beginPerformanceSample() {
        performance = LinuxPerformanceCounter(); displayedFrames = 0
        sampleTime = ProcessInfo.processInfo.systemUptime
        _ = performance.sample(time: sampleTime, cpuSeconds: LinuxProcessMetrics.cpuSeconds(), frames: 0)
    }
    private func refreshDisplay() {
        pollControllers()
        guard !paused else { return }
        if let point = pendingPointer {
            pendingPointer = nil
            qmp.move(x: point.x, y: point.y, down: point.down)
        }
        if let image = LinuxFrameInbox.shared.take() { self.image = image; displayedFrames += 1 }
        let now = ProcessInfo.processInfo.systemUptime
        guard now - sampleTime >= 1 else { return }
        if let rates = performance.sample(time: now, cpuSeconds: LinuxProcessMetrics.cpuSeconds(), frames: displayedFrames) {
            cpuPercent = rates.cpuPercent; displayFPS = rates.displayFPS
        }
        memoryMiB = LinuxProcessMetrics.footprintMiB()
        inputMilliseconds = qmp.inputMilliseconds
        hardwareTestsReady = diagnostics.ready && !hardwareGuestBusy
        // Read bounded diagnostic records once a second, never Steam logs or
        // account files. A running test retains only its latest small result.
        do {
            let log = Self.directory.appendingPathComponent("boot.log")
            if let handle = try? FileHandle(forReadingFrom: log) {
                defer { try? handle.close() }
                if let length = try? handle.seekToEnd() {
                    try? handle.seek(toOffset: length > 65_536 ? length - 65_536 : 0)
                    if let bytes = try? handle.read(upToCount: 65_536) {
                        let text = String(decoding: bytes, as: UTF8.self)
                        if guestGraphics == nil { guestGraphics = LinuxGuestGraphics.observation(in: text) }
                    }
                }
            }
        }
        if hardwareTestBusy {
            hardwareElapsedSeconds = hardwareHeartbeat.elapsed(now: now)
            hardwareHeartbeatAge = hardwareHeartbeat.age(now: now)
            if hardwareHeartbeat.needsCancellation(now: now) { cancelHardwareTest() }
            hardwareTestUnresponsive = hardwareHeartbeat.unresponsive(now: now)
        }
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
