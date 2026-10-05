import SwiftUI
import GameController
import UIKit
import Darwin

@main
struct ProbeApp: App {
    init() { SystemCrashDiagnostics.shared.start() }
    var body: some Scene { WindowGroup { ProbeScreen() } }
}

@MainActor
final class ProbeModel: ObservableObject {
    @Published var busy = false
    @Published var report = "Run the platform probes to collect a device report."
    @Published var exportURL: URL?
    @Published var showRecovery = false
    @Published var recoveryMessage = ""
    @Published var recoveredLogURL: URL?
    @Published var logShare: DiagnosticShare?
    @Published var engineNeedsRelaunch = false
    @Published var jitActivationMessage = ""
    @Published var preparingLogShare = false
    @Published var testStatus = ""
    @Published var showLinuxScreen = false
    @Published var screenStarted = false
    @Published var frameSequence = true
    @Published var movingSequence = false
    private var requestedStikDebug = false
    private var facts: [String: Any] = [:]
    private let journal = RecoveryJournal(documents: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
    private var recoveryChecked = false
    private var recoveredSnapshot: Data?
    private var activeRunID: String?

    func openLinuxScreen(frames: Bool = true, moving: Bool = false) {
        guard !busy && !engineNeedsRelaunch else { return }
        screenStarted = false
        frameSequence = frames
        movingSequence = moving
        showLinuxScreen = true
    }

    func startLinuxScreen() {
        guard showLinuxScreen && !screenStarted && !busy && !engineNeedsRelaunch else { return }
        screenStarted = true
        run(kind: movingSequence ? "linux-moving" : frameSequence ? "linux-frames" : "linux-screen")
    }

    func checkRecovery() {
        guard !recoveryChecked else { return }
        recoveryChecked = true
        guard let snapshot = journal.pendingSnapshot() else { return }
        recoveredSnapshot = snapshot
        let previous = try? journal.pendingRun(snapshot)
        let stage = journal.lastStage(snapshot) ?? "test preparation"
        recoveryMessage = "The previous \(previous?.kind ?? "unknown") test did not finish normally. Last saved stage: \(stage). Share its saved logs to investigate. A crash, iOS termination or force-close can cause this."
        do { recoveredLogURL = try journal.shareReport(snapshot: snapshot) }
        catch { report = "Could not prepare recovery logs: \(error.localizedDescription)" }
        showRecovery = true
    }

    func acknowledgeRecovery() {
        guard let snapshot = recoveredSnapshot else { return }
        do { try journal.acknowledge(snapshot); recoveredSnapshot = nil }
        catch { report = "Could not acknowledge the interrupted run: \(error.localizedDescription)" }
    }

    func shareRecovery() {
        guard !preparingLogShare else { return }
        preparingLogShare = true
        do {
            let url = try journal.shareReport(snapshot: recoveredSnapshot ?? journal.pendingSnapshot())
            recoveredLogURL = url
            acknowledgeRecovery()
            showRecovery = false
            // Present after the alert's dismissal animation, not while UIKit
            // still owns that modal. File preparation remains synchronous.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                self.logShare = DiagnosticShare(url: url)
                self.preparingLogShare = false
            }
        } catch {
            preparingLogShare = false
            report = "Could not prepare diagnostic logs: \(error.localizedDescription)"
        }
    }

    func enableStikDebug() {
        guard !busy && !engineNeedsRelaunch else { return }
        let facts = MPCPlatformFacts()
        let signing = facts["code_signing"] as? [String: Any]
        guard signing?["get_task_allow"] as? Bool == true else {
            jitActivationMessage = "This signing does not show get-task-allow. Install with signing that preserves the debugger entitlement."
            return
        }
        do {
            let url = try StikDebugRequest.make(bundleID: Bundle.main.bundleIdentifier ?? "", pid: getpid())
            guard UIApplication.shared.canOpenURL(url) else {
                jitActivationMessage = "StikDebug is unavailable. Install or open StikDebug, then return here."
                return
            }
            requestedStikDebug = true
            try journal.recordActivation(["scope": "stikdebug-url-request", "pid": getpid(),
                "bundle_id": Bundle.main.bundleIdentifier ?? "unknown", "script": "universal.js",
                "url_open_accepted": NSNull(), "jit_verified": false])
            jitActivationMessage = "Opening StikDebug for this app. Confirm its JIT request if prompted, then return and run the ARM64 JIT check."
            UIApplication.shared.open(url, options: [:]) { accepted in
                Task { @MainActor in
                    if !accepted { self.jitActivationMessage = "iOS could not open StikDebug. JIT was not enabled." }
                    try? self.journal.recordActivation(["scope": "stikdebug-url-request", "pid": getpid(),
                        "bundle_id": Bundle.main.bundleIdentifier ?? "unknown", "script": "universal.js",
                        "url_open_accepted": accepted, "jit_verified": false])
                }
            }
        } catch { jitActivationMessage = "Could not start StikDebug: \(error.localizedDescription)" }
    }

    func refreshJITAttachment() {
        guard requestedStikDebug else { return }
        let signing = MPCPlatformFacts()["code_signing"] as? [String: Any]
        jitActivationMessage = signing?["debugger_attached"] as? Bool == true
            ? "Debugger attached. Run the ARM64 JIT check to verify executable-region preparation."
            : "Debugger attachment is not currently observed. Enable JIT in StikDebug, then run the check."
    }

    func run(kind: String) {
        guard !busy && !engineNeedsRelaunch else { return }
        busy = true
        testStatus = "Starting \(kind == "linux-frames" ? "Eight-frame Linux test" : kind == "linux-screen" ? "Linux screen test" : kind == "linux-image" ? "Linux image import gate" : kind == "linux-gpu" ? "Linux guest Vulkan gate" : kind == "linux" ? "Linux kernel gate" : kind == "jit" ? "ARM64 JIT check" : kind == "vulkan" ? "native Vulkan â†’ Metal check" : "host probes")â€¦"
        exportURL = nil
        let runID = UUID().uuidString
        activeRunID = runID
        let before = MPCPlatformFacts()
        let controllers = GCController.controllers().map { ["vendor": $0.vendorName ?? "unknown", "extended_gamepad": $0.extendedGamepad != nil] as [String: Any] }
        var prepared = false
        var diagnosticDirectory = ""
        do {
            let run = PendingProbe(runID: runID, kind: kind,
                startedUTC: ISO8601DateFormatter().string(from: Date()),
                sourceCommit: Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "unknown",
                build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown")
            let folder = try journal.begin(run, before: before)
            diagnosticDirectory = folder.path
            prepared = true
            guard MPCStartDiagnosticCapture(folder.path) else {
                throw NSError(domain: "ProbeCapture", code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Could not start durable diagnostic capture; test was not executed"])
            }
        } catch {
            report = "Test not started: \(error.localizedDescription)"
            testStatus = report
            if prepared, let data = try? JSONSerialization.data(withJSONObject: ["status": "not-started", "reason": report]) {
                try? journal.complete(runID: runID, result: data)
            }
            busy = false
            activeRunID = nil
            return
        }
        Task { @MainActor in
            while busy && activeRunID == runID {
                try? await Task.sleep(nanoseconds: 500_000_000)
                if busy && activeRunID == runID, let snapshot = journal.pendingSnapshot(), let stage = journal.lastStage(snapshot) {
                    testStatus = "Running: \(stage)"
                }
            }
        }
        let diagnosticPath = diagnosticDirectory
        Task.detached(priority: .userInitiated) {
            MPCDiagnosticStage("probe-entering", ["kind": kind])
            var tests: [String: Any]
            switch kind {
            case "linux": tests = ["linux": MPCLinuxKernelProbe()]
            case "linux-gpu": tests = ["linux_gpu": MPCLinuxGuestGPUProbe()]
            case "linux-image": tests = ["linux_image": MPCLinuxGuestImageProbe()]
            case "linux-screen": tests = ["linux_screen": MPCLinuxGuestScreenProbe()]
            case "linux-frames": tests = ["linux_frames": MPCLinuxGuestFrameProbe()]
            case "linux-moving": tests = ["linux_moving": MPCLinuxGuestMovingProbe()]
            case "jit": tests = ["jit": MPCExecuteJITProbe()]
            case "vulkan": tests = ["native_vulkan": MPCNativeVulkanProbe(diagnosticPath)]
            default: tests = ["native_cpu": MPCNativeCPUProbe(), "metal": MPCMetalProbe(), "storage": MPCStorageProbe()]
            }
            MPCDiagnosticStage("probe-returned", ["kind": kind])
            let linux = (tests["linux_moving"] ?? tests["linux"] ?? tests["linux_gpu"] ?? tests["linux_image"] ?? tests["linux_screen"] ?? tests["linux_frames"]) as? [String: Any]
            if linux?["status"] as? String != "timed-out-engine-still-running" { MPCStopDiagnosticCapture() }
            let gpuKey = kind == "linux-moving" ? "linux_moving" : kind == "linux-frames" ? "linux_frames" : kind == "linux-screen" ? "linux_screen" : kind == "linux-image" ? "linux_image" : "linux_gpu"
            if var gpu = tests[gpuKey] as? [String: Any] {
                gpu["engine_output"] = MPCDiagnosticOutputSnapshot(diagnosticPath)
                gpu["engine_output_capture_finished"] = gpu["engine_finished"] as? Bool == true
                tests[gpuKey] = gpu
            }
            await self.finish(runID: runID, before: before, controllers: controllers, tests: tests)
        }
    }

    private func finish(runID: String, before: [AnyHashable: Any], controllers: [[String: Any]], tests: [String: Any]) {
        if let jit = tests["jit"] as? [String: Any] {
            testStatus = jit["status"] as? String == "passed"
                ? "ARM64 JIT passed: code returned 42. Open Show eight Linux-rendered frames next in this fresh process."
                : "JIT \(jit["status"] ?? "failed"): \(jit["reason"] ?? jit["stage"] ?? "See the saved report.")"
        } else if let moving = tests["linux_moving"] as? [String: Any] {
            let result = moving["moving_output"] as? [String: Any]
            let native = result?["native"] as? [String: Any]
            let count = (native?["releases"] as? [[String: Any]])?.count ?? 0
            testStatus = moving["buffer_reuse_verified"] as? Bool == true
                ? "120 changing Linux frames passed across three reused buffers. " + (moving["presentation_verified"] as? Bool == true ? "Display timestamps passed. " : "Display timing is incomplete. ") + "Desktop, Steam and game FPS remain unfinished. Share the report and logs."
                : "Moving test \(moving["status"] ?? "failed"): \(count)/120 native releases recorded. \(result?["reason"] ?? moving["reason"] ?? moving["stage"] ?? "Share the saved logs.")"
        } else if let frames = tests["linux_frames"] as? [String: Any] {
            let screen = frames["frame_screen"] as? [String: Any]
            let native = screen?["native"] as? [String: Any]
            let rows = native?["frames"] as? [[String: Any]] ?? []
            let completed = rows.filter { $0["gpu_completed"] as? Bool == true && $0["consumer_error"] as? Bool == false }.count
            testStatus = frames["gpu_sequence_verified"] as? Bool == true
                ? "Eight Linux frames imported; 8/8 screen GPU draws completed. " + (frames["presentation_verified"] as? Bool == true ? "Display timestamps passed. " : "Display timing remains incomplete. ") + "Desktop, games and FPS remain unfinished. Share the report and logs."
                : "Eight-frame test \(frames["status"] ?? "failed"): \(completed)/8 draws completed. \(screen?["reason"] ?? frames["reason"] ?? frames["stage"] ?? "Share the saved logs.")"
        } else if let screen = tests["linux_screen"] as? [String: Any] {
            let receipt = screen["screen_presentation"] as? [String: Any]
            if screen["presentation_verified"] as? Bool == true {
                testStatus = "Both Linux images passed the screen timing check. Continuous animation, desktop and games remain unfinished."
            } else if screen["host_memory_import_verified"] as? Bool == true,
                      let native = receipt?["native"] as? [String: Any] {
                let frames = native["frames"] as? [[String: Any]] ?? []
                let completed = frames.filter { $0["gpu_completed"] as? Bool == true && $0["consumer_error"] as? Bool == false }.count
                let missingTimes = frames.filter { ($0["presented_seconds"] as? Double ?? 0) <= 0 }.count
                let events = native["lifecycle_events"] as? [[String: Any]] ?? []
                let interruption = events.first { $0["interrupts_acceptance"] as? Bool == true }?["reason"] as? String
                testStatus = "Linux image import passed; \(completed)/2 screen draws completed. Display timing is incomplete"
                    + (missingTimes > 0 ? " (\(missingTimes) missing timestamps)" : "")
                    + (interruption.map { "; interruption: \($0)" } ?? (native["interrupted"] as? Bool == true ? "; screen interrupted" : ""))
                    + ". Share the report and saved logs."
            } else {
                testStatus = "Linux screen test \(screen["status"] ?? "failed"): \(receipt?["reason"] ?? screen["reason"] ?? "Share the report and saved logs.")"
            }
        } else if let image = tests["linux_image"] as? [String: Any] {
            let receipt = image["image_import"] as? [String: Any]
            let rejection = (receipt?["guest_rejections"] as? [[String: Any]])?.first
            let failure = rejection?["stage"] ?? receipt?["reason"] ?? image["reason"] ?? "See the saved report."
            testStatus = image["host_memory_import_verified"] as? Bool == true
                ? "Two Linux images imported into Metal and matched. Visible presentation and games remain unfinished."
                : "Linux image import \(image["status"] ?? "failed"): \(failure). Share the device report and saved logs."
        } else if let gpu = tests["linux_gpu"] as? [String: Any] {
            testStatus = gpu["guest_vulkan_pixels_verified"] as? Bool == true
                ? (gpu["metal_host_verified"] as? Bool == true
                    ? "Linux guest Vulkan pixels and native Metal completions passed. Memory import, presentation and game tests remain unfinished."
                    : "Linux guest Vulkan pixels passed. The native Metal completion check is incomplete; share the report. Presentation and game tests remain unfinished.")
                : "Linux guest GPU \(gpu["status"] ?? "failed"): \(gpu["reason"] ?? gpu["stage"] ?? "Share the saved report and logs.")"
        } else if let linux = tests["linux"] as? [String: Any] {
            testStatus = linux["linux_execution"] as? Bool == true
                ? "Linux kernel and ABI gate passed. SteamOS and game graphics remain unfinished."
                : "Linux \(linux["status"] ?? "failed"): \(linux["reason"] ?? linux["stage"] ?? "See the saved report and logs.")"
        } else if let vulkan = tests["native_vulkan"] as? [String: Any] {
            testStatus = vulkan["native_vulkan_to_metal_verified"] as? Bool == true
                ? "Native Vulkan â†’ Metal shader check passed. Linux graphics and presentation remain unfinished."
                : "Native Vulkan \(vulkan["status"] ?? "failed"): \(vulkan["reason"] ?? vulkan["stage"] ?? "See the saved logs.")"
        } else { testStatus = "Host probes finished. See the saved measurements below." }
        facts.merge(tests) { _, new in new }
        let kernel = (tests["linux_moving"] ?? tests["linux"] ?? tests["linux_gpu"] ?? tests["linux_image"] ?? tests["linux_screen"] ?? tests["linux_frames"]) as? [String: Any]
        engineNeedsRelaunch = kernel?["status"] as? String == "timed-out-engine-still-running" ||
            kernel?["requires_relaunch"] as? Bool == true ||
            (tests["native_vulkan"] as? [String: Any])?["requires_relaunch"] as? Bool == true
        let linux = (facts["linux_moving"] as? [String: Any])?["linux_execution"] as? Bool == true ||
            (facts["linux"] as? [String: Any])?["linux_execution"] as? Bool == true ||
            (facts["linux_gpu"] as? [String: Any])?["linux_execution"] as? Bool == true ||
            (facts["linux_image"] as? [String: Any])?["linux_execution"] as? Bool == true ||
            (facts["linux_screen"] as? [String: Any])?["linux_execution"] as? Bool == true ||
            (facts["linux_frames"] as? [String: Any])?["linux_execution"] as? Bool == true
        let result: [String: Any] = [
            "schema": 1, "run_id": runID, "collected_utc": ISO8601DateFormatter().string(from: Date()),
            "source_commit": Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "local-unrecorded",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "scope": "physical-ios-host-probe", "before": before, "after": MPCPlatformFacts(),
            "executed_tests": tests.keys.sorted(),
            "controllers_observed": controllers, "tests": facts,
            "acceptance": ["linux_kernel_boot": linux,
                           "linux_guest_vulkan_pixels": ((facts["linux_moving"] ?? facts["linux_frames"] ?? facts["linux_screen"] ?? facts["linux_image"] ?? facts["linux_gpu"]) as? [String: Any])?["guest_vulkan_pixels_verified"] as? Bool == true,
                           "linux_guest_offscreen_metal_completion": ((facts["linux_moving"] ?? facts["linux_frames"] ?? facts["linux_screen"] ?? facts["linux_image"] ?? facts["linux_gpu"]) as? [String: Any])?["metal_host_verified"] as? Bool == true,
                           "linux_guest_image_import": ((facts["linux_moving"] ?? facts["linux_frames"] ?? facts["linux_screen"] ?? facts["linux_image"]) as? [String: Any])?["host_memory_import_verified"] as? Bool == true,
                           "linux_guest_two_image_screen_presentation": (facts["linux_screen"] as? [String: Any])?["presentation_verified"] as? Bool == true,
                           "linux_guest_eight_frame_gpu_sequence": (facts["linux_frames"] as? [String: Any])?["gpu_sequence_verified"] as? Bool == true,
                           "linux_guest_eight_frame_display_timing": (facts["linux_frames"] as? [String: Any])?["presentation_verified"] as? Bool == true,
                           "linux_guest_three_buffer_reuse": (facts["linux_moving"] as? [String: Any])?["buffer_reuse_verified"] as? Bool == true,
                           "linux_guest_moving_display_timing": (facts["linux_moving"] as? [String: Any])?["presentation_verified"] as? Bool == true,
                           "linux_guest_continuous_animation": false,
                           "linux_guest_frame_pacing": false,
                           "native_vulkan_to_metal_offscreen": (facts["native_vulkan"] as? [String: Any])?["native_vulkan_to_metal_verified"] as? Bool == true,
                           "steam_arm_client": false, "fex_game": false,
                           "linux_game_graphics_to_metal": false, "steam_under_60_seconds": false,
                           "hollow_knight_60_to_80_base_fps": false],
            "limitations": "Host-only Metal and JIT checks do not demonstrate Linux execution. The Linux kernel, guest offscreen Vulkan/Metal and guest image import gates have separate acceptance fields and require fresh device results. These disposable diagnostics do not establish moving presentation, full SteamOS, Steam ARM, FEX/Proton or game performance. Controller enumeration is not an input test."
        ]
        do {
            let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
            report = String(decoding: data, as: UTF8.self)
            let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = directory.appendingPathComponent("MyPCSteamOS-Probe-\(runID).json")
            try data.write(to: url, options: .atomic)
            try journal.complete(runID: runID, result: data,
                clearPending: kernel?["status"] as? String != "timed-out-engine-still-running")
            exportURL = url
        } catch { report = "Could not export report: \(error.localizedDescription)" }
        busy = false
        activeRunID = nil
    }
}

struct ProbeScreen: View {
    @StateObject private var model = ProbeModel()
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("SteamOS platform bring-up").font(.title2.bold())
                    Text("This prerelease tests separate parts of Linux graphics on your iPhone. The SteamOS desktop and game environment are unfinished.")
                    Button("Show changing Linux frames") { model.openLinuxScreen(moving: true) }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Text("The next test renders 120 changing frames inside Linux while reusing three buffers. Start it first after enabling JIT in a fresh app process, and share the completed report and saved logs.").font(.callout)
                    Button("Show eight Linux-rendered frames") { model.openLinuxScreen() }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Button("Show Linux-rendered images") { model.openLinuxScreen(frames: false) }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Text("This opens a real Metal screen for two images rendered inside Linux. Enable JIT first, then start the test from that screen. Continuous animation and the desktop are still unfinished.").font(.callout)
                    Button("Run Metal and storage probes") { model.run(kind: "host") }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Button("Enable JIT in StikDebug") { model.enableStikDebug() }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Text("StikDebug will request JIT for this running app using universal.js. Confirm there if prompted, return here, then run the JIT check.").font(.callout)
                    if !model.jitActivationMessage.isEmpty { Text(model.jitActivationMessage).font(.callout) }
                    Button("Run ARM64 JIT check") { model.run(kind: "jit") }
                        .buttonStyle(.bordered).disabled(model.busy || model.engineNeedsRelaunch)
                    Button("Run Linux kernel gate") { model.run(kind: "linux") }
                        .buttonStyle(.bordered).disabled(model.busy || model.engineNeedsRelaunch)
                    Button("Run Linux guest Vulkan gate") { model.run(kind: "linux-gpu") }
                        .buttonStyle(.bordered).disabled(model.busy || model.engineNeedsRelaunch)
                    Button("Run Linux image import gate") { model.run(kind: "linux-image") }
                        .buttonStyle(.borderedProminent).disabled(model.busy || model.engineNeedsRelaunch)
                    Text("This separate import diagnostic checks two Linux images without displaying them. The new Show Linux-rendered images button adds the screen check. Each Linux boot needs a fresh process.").font(.callout)
                    Text("The guest graphics build boots Linux with virtio-GPU/Venus and tests two 720p shader images inside Linux. Enable StikDebug first and use a fresh app process for each Linux boot.").font(.callout)
                    Button("Run native Vulkan â†’ Metal check") { model.run(kind: "vulkan") }
                        .buttonStyle(.bordered).disabled(model.busy || model.engineNeedsRelaunch)
                    Text("The graphics-engine build tests two 720p shader images offscreen. Linux graphics, moving presentation and games require separate tests.").font(.callout)
                    Text("The Linux gate requires an engine-bearing build and StikDebug. Keep the app open for up to three minutes. Relaunch before repeating a Linux boot.").font(.callout)
                    if model.busy { ProgressView("Collecting measurementsâ€¦") }
                    if !model.testStatus.isEmpty { Text(model.testStatus).font(.callout).textSelection(.enabled) }
                    if model.engineNeedsRelaunch { Text("This test requires a fresh app process. Share the saved logs, then close and relaunch before another test.").font(.callout) }
                    if let url = model.exportURL { ShareLink("Share device report", item: url) }
                    Button("Share saved diagnostic logs") { model.shareRecovery() }
                        .buttonStyle(.bordered).disabled(model.busy || model.preparingLogShare)
                    if let url = model.recoveredLogURL { ShareLink("Share previous interrupted test logs", item: url) }
                    Text(model.report).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }.padding()
            }.navigationTitle("My-pc SteamOS Probe")
                .task { model.checkRecovery() }
                .onChange(of: scenePhase) { _, phase in if phase == .active { model.refreshJITAttachment() } }
                .alert("Previous test stopped â€” share logs", isPresented: $model.showRecovery) {
                    Button("Share logs") { model.shareRecovery() }
                    Button("Later", role: .cancel) { model.acknowledgeRecovery() }
                } message: { Text(model.recoveryMessage) }
                .sheet(item: $model.logShare) { DiagnosticShareSheet(url: $0.url) }
                .fullScreenCover(isPresented: $model.showLinuxScreen) { LinuxScreenTest(model: model) }
        }
    }
}

struct LinuxSurface: UIViewRepresentable {
    func makeUIView(context: Context) -> UIView { MPCGuestScreenCreateView() }
    func updateUIView(_ view: UIView, context: Context) {}
}

struct LinuxScreenTest: View {
    @ObservedObject var model: ProbeModel
    var body: some View {
        ZStack {
            LinuxSurface().ignoresSafeArea()
            VStack {
                Text("Linux GPU screen test").font(.headline)
                Text(model.movingSequence ? "120 changing Linux frames · three buffers · desktop unfinished" : model.frameSequence ? "Eight Linux-rendered frames · desktop and FPS unfinished" : "Two Linux-rendered images · SteamOS desktop unfinished").font(.caption)
                Spacer()
                if !model.screenStarted {
                    Button(model.movingSequence ? "Start moving-frame test" : model.frameSequence ? "Start eight-frame test" : "Start Linux screen test") { model.startLinuxScreen() }
                        .buttonStyle(.borderedProminent)
                    Text("Enable JIT before starting. Keep this screen open and avoid rotating during the test.").font(.callout)
                } else {
                    Text(model.testStatus).font(.callout)
                    if model.busy { ProgressView().tint(.white) }
                    if let url = model.exportURL { ShareLink("Share screen-test report", item: url).buttonStyle(.borderedProminent) }
                }
                Button(model.screenStarted ? "Return to report" : "Back") { model.showLinuxScreen = false }
                    .buttonStyle(.bordered).disabled(model.busy)
            }.padding().foregroundStyle(.white)
        }.background(.black).interactiveDismissDisabled(model.busy)
    }
}

struct DiagnosticShare: Identifiable {
    let url: URL
    var id: String { url.path }
}

struct DiagnosticShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
