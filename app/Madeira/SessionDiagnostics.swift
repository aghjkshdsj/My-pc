import Foundation
import UIKit
import MetricKit

final class SessionDiagnostics: NSObject, MXMetricManagerSubscriber {
    static let shared = SessionDiagnostics()
    static let contextURL = GameLibrary.documents.appendingPathComponent("somethingpc-session-diagnostics.json")
    static let systemFolder = GameLibrary.documents.appendingPathComponent("SystemDiagnostics", isDirectory: true)
    private let queue = DispatchQueue(label: "somethingpc.diagnostics", qos: .utility)
    private var context: [String: Any] = [:]
    private var events: [[String: Any]] = []
    private var memory: [[String: Any]] = []
    private var peakMB = 0
    private var timer: Timer?

    private override init() {
        super.init()
        var system = utsname()
        uname(&system)
        let capacity = MemoryLayout.size(ofValue: system.machine)
        let model = withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: capacity) { String(cString: $0) }
        }
        let entitlements = EntitlementStatus.check()
        context = ["sessionID": UUID().uuidString, "started": Self.timestamp(), "device": model,
            "os": ProcessInfo.processInfo.operatingSystemVersionString,
            "appVersion": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown",
            "build": Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown",
            "commit": Bundle.main.infoDictionary?["SomethingPCBuildCommit"] as? String ?? "local",
            "ramMB": ProcessInfo.processInfo.physicalMemory / 1_048_576,
            "increasedMemoryEntitlement": entitlements.increasedMemory,
            "extendedVirtualAddressing": entitlements.extendedVA,
            "backend": "Wine / FEX / DXMT Metal", "progressMeaning": "completed startup milestones, not game loading percentage"]
        MXMetricManager.shared.add(self)
        NotificationCenter.default.addObserver(self, selector: #selector(memoryWarning), name: UIApplication.didReceiveMemoryWarningNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(background), name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(foreground), name: UIApplication.didBecomeActiveNotification, object: nil)
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.sample() }
        event("App initialized")
        sample()
    }

    static func timestamp() -> String { ISO8601DateFormatter().string(from: Date()) }

    func event(_ message: String) {
        queue.async {
            self.events.append(["time": Self.timestamp(), "event": message])
            self.events = Array(self.events.suffix(100))
            self.persist()
        }
    }

    @MainActor func launch(game: LibraryGame, profile: GameProfile) {
        let settings = EmulatorSettings.shared
        let input = InputSettings.shared
        let effective: [String: Any] = ["resolution": settings.resolution, "fpsHUD": settings.showFPS,
            "presentationMode": settings.presentationMode, "keepAwake": settings.keepAwake,
            "controllerMode": settings.controllerMode, "deadZone": settings.deadZone, "mouseSpeed": settings.mouseSpeed,
            "relativeMouse": input.relative, "pointerSensitivity": input.sensAbs, "mouseLookSensitivity": input.sensRel,
            "verbose": input.diagnostics, "ARM64Runtime": profile.visualCppARM64,
            "customSettings": profile.customSettings]
        let executable = game.executable.flatMap { try? GameFiles.windowsPath($0, drive: GameLibrary.drive) } ?? "explorer.exe"
        let controllers = GameControllerManager.shared.devices.map { ["slot": String($0.id + 1), "name": $0.name] }
        queue.async {
            self.context["game"] = game.title
            self.context["executable"] = executable
            self.context["settings"] = effective
            self.context["controllers"] = controllers
            self.context["hasLaunchArguments"] = !profile.arguments.isEmpty
            if let url = Bundle.main.resourceURL?.appendingPathComponent("ARM64Runtime/manifest.json"),
               let data = try? Data(contentsOf: url), let manifest = try? JSONSerialization.jsonObject(with: data) {
                self.context["bundledRuntimeManifest"] = manifest
            }
            self.persist()
        }
    }

    func libraryInventory(_ games: [LibraryGame]) {
        let inventory = games.prefix(100).map { game in
            ["id": game.id, "title": game.title, "selected": game.executable?.lastPathComponent ?? "not selected",
             "candidates": game.candidates.map { String($0.path.dropFirst(GameLibrary.gamesFolder.path.count + 1)) }.joined(separator: " | ")]
        }
        queue.async { self.context["library"] = inventory; self.context["libraryCount"] = games.count; self.persist() }
    }

    @objc private func memoryWarning() { event("iOS memory warning received"); sample() }
    @objc private func background() { event("Application entered background"); sample() }
    @objc private func foreground() { event("Application became active"); sample() }

    private func sample() {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<natural_t>.size)
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count) }
        }
        let footprint = result == KERN_SUCCESS ? Int(info.phys_footprint / 1_048_576) : -1
        let sample: [String: Any] = ["time": Self.timestamp(), "footprintMB": footprint,
            "thermalState": ProcessInfo.processInfo.thermalState.rawValue,
            "lowPowerMode": ProcessInfo.processInfo.isLowPowerModeEnabled,
            "foreground": UIApplication.shared.applicationState == .active,
            "metalPresents": madeira_get_present_count(), "gdiPresents": spc_gdi_present_count(),
            "wineRunning": wine_process_is_running() != 0, "serverRunning": wineserver_is_running() != 0]
        queue.async {
            self.peakMB = max(self.peakMB, footprint)
            self.memory.append(sample)
            self.memory = Array(self.memory.suffix(120))
            self.persist()
        }
    }

    private func persist() {
        var snapshot = context
        snapshot["events"] = events
        snapshot["memorySamples"] = memory
        snapshot["observedPeakMB"] = peakMB
        do { try JSONSerialization.data(withJSONObject: snapshot, options: [.prettyPrinted, .sortedKeys]).write(to: Self.contextURL, options: .atomic) }
        catch { NSLog("Session diagnostics write failed: %@", error.localizedDescription) }
    }

    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        let data = payloads.map { $0.jsonRepresentation() }
        queue.async {
            do {
                try FileManager.default.createDirectory(at: Self.systemFolder, withIntermediateDirectories: true)
                for payload in data where payload.count <= 4_194_304 {
                    try payload.write(to: Self.systemFolder.appendingPathComponent("MetricKit-\(UUID().uuidString).json"), options: .atomic)
                }
                let files = try FileManager.default.contentsOfDirectory(at: Self.systemFolder, includingPropertiesForKeys: [.creationDateKey])
                    .filter { $0.lastPathComponent.hasPrefix("MetricKit-") }
                    .sorted { ((try? $0.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast) > ((try? $1.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast) }
                for file in files.dropFirst(3) { try? FileManager.default.removeItem(at: file) }
                self.events.append(["time": Self.timestamp(), "event": "System diagnostic payload received (may describe an earlier session)"])
                self.persist()
            } catch { NSLog("System diagnostic capture failed: %@", error.localizedDescription) }
        }
    }
}

enum SupportReport {
    static func read(_ url: URL, limit: Int) -> Data {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return Data() }
        defer { try? handle.close() }
        return (try? handle.read(upToCount: limit)) ?? Data()
    }

    static func context() -> Data {
        var output = Data("\n--- Structured session diagnostics ---\n".utf8)
        output.append(read(SessionDiagnostics.contextURL, limit: 524_288))
        output.append(Data("\n--- iOS diagnostics (when delivered; may describe earlier sessions) ---\n".utf8))
        let files = (try? FileManager.default.contentsOfDirectory(at: SessionDiagnostics.systemFolder, includingPropertiesForKeys: nil)) ?? []
        for file in files.filter({ $0.lastPathComponent.hasPrefix("MetricKit-") && $0.pathExtension == "json" }).sorted(by: { $0.lastPathComponent < $1.lastPathComponent }).prefix(3) {
            output.append(Data("\n\(file.lastPathComponent)\n".utf8))
            output.append(read(file, limit: 4_194_304))
        }
        if files.isEmpty { output.append(Data("No system diagnostic payload has been delivered. An iOS .ips/JetsamEvent report may still be needed.\n".utf8)) }
        return output
    }

    static func log() -> Data {
        let url = GameLibrary.documents.appendingPathComponent("madeira-log.txt")
        guard let handle = try? FileHandle(forReadingFrom: url) else { return Data("No runtime log is available.\n".utf8) }
        defer { try? handle.close() }
        do {
            let length = try handle.seekToEnd()
            try handle.seek(toOffset: 0)
            var output = Data("\n--- Runtime log ---\n".utf8)
            if length > 4_194_304 {
                output.append(try handle.read(upToCount: 131_072) ?? Data())
                output.append(Data("\n--- Middle omitted; last 4 MiB follows ---\n".utf8))
                try handle.seek(toOffset: length - 4_194_304)
            }
            output.append(try handle.read(upToCount: 4_194_304) ?? Data())
            return output
        } catch { return Data("Could not read runtime log: \(error.localizedDescription)\n".utf8) }
    }

    static func current() throws -> URL {
        let directory = GameLibrary.documents.appendingPathComponent("Diagnostics", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let url = directory.appendingPathComponent("Support-current.txt")
        var output = Data("Something PC support report — \(SessionDiagnostics.timestamp())\nReview before sharing. Includes game filenames, settings, device information, and logs. No automatic upload. Not every iOS termination produces an in-app stack trace.\n".utf8)
        output.append(context())
        output.append(log())
        try output.write(to: url, options: .atomic)
        return url
    }
}

struct SharedReport: Identifiable {
    let id = UUID()
    let url: URL
}
