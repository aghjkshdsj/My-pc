import SwiftUI
import GameController
import UIKit
import Darwin

@main
struct ProbeApp: App {
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
    private var requestedStikDebug = false
    private var facts: [String: Any] = [:]
    private let journal = RecoveryJournal(documents: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
    private var recoveryChecked = false
    private var recoveredSnapshot: Data?

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
        exportURL = nil
        let runID = UUID().uuidString
        let before = MPCPlatformFacts()
        let controllers = GCController.controllers().map { ["vendor": $0.vendorName ?? "unknown", "extended_gamepad": $0.extendedGamepad != nil] as [String: Any] }
        var prepared = false
        do {
            let run = PendingProbe(runID: runID, kind: kind,
                startedUTC: ISO8601DateFormatter().string(from: Date()),
                sourceCommit: Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "unknown",
                build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown")
            let folder = try journal.begin(run, before: before)
            prepared = true
            guard MPCStartDiagnosticCapture(folder.path) else {
                throw NSError(domain: "ProbeCapture", code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Could not start durable diagnostic capture; test was not executed"])
            }
        } catch {
            report = "Test not started: \(error.localizedDescription)"
            if prepared, let data = try? JSONSerialization.data(withJSONObject: ["status": "not-started", "reason": report]) {
                try? journal.complete(runID: runID, result: data)
            }
            busy = false
            return
        }
        Task.detached(priority: .userInitiated) {
            MPCDiagnosticStage("probe-entering", ["kind": kind])
            let tests: [String: Any]
            switch kind {
            case "linux": tests = ["linux": MPCLinuxKernelProbe()]
            case "jit": tests = ["jit": MPCExecuteJITProbe()]
            default: tests = ["native_cpu": MPCNativeCPUProbe(), "metal": MPCMetalProbe(), "storage": MPCStorageProbe()]
            }
            MPCDiagnosticStage("probe-returned", ["kind": kind])
            let linux = tests["linux"] as? [String: Any]
            if linux?["status"] as? String != "timed-out-engine-still-running" { MPCStopDiagnosticCapture() }
            await self.finish(runID: runID, before: before, controllers: controllers, tests: tests)
        }
    }

    private func finish(runID: String, before: [AnyHashable: Any], controllers: [[String: Any]], tests: [String: Any]) {
        facts.merge(tests) { _, new in new }
        engineNeedsRelaunch = (tests["linux"] as? [String: Any])?["status"] as? String == "timed-out-engine-still-running"
        let linux = (facts["linux"] as? [String: Any])?["linux_execution"] as? Bool == true
        let result: [String: Any] = [
            "schema": 1, "run_id": runID, "collected_utc": ISO8601DateFormatter().string(from: Date()),
            "source_commit": Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "local-unrecorded",
            "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "scope": "physical-ios-host-probe", "before": before, "after": MPCPlatformFacts(),
            "controllers_observed": controllers, "tests": facts,
            "acceptance": ["linux_kernel_boot": linux, "steam_arm_client": false, "fex_game": false,
                           "linux_game_graphics_to_metal": false, "steam_under_60_seconds": false,
                           "hollow_knight_60_to_80_base_fps": false],
            "limitations": "Host Metal and JIT checks do not demonstrate Linux execution. The separate Linux gate, when bundled, validates only a disposable Linux kernel and ABI smoke. SteamOS, guest graphics, Steam, FEX and game performance remain unverified. Controller enumeration is not an input test."
        ]
        do {
            let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
            report = String(decoding: data, as: UTF8.self)
            let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = directory.appendingPathComponent("MyPCSteamOS-Probe-\(runID).json")
            try data.write(to: url, options: .atomic)
            try journal.complete(runID: runID, result: data, clearPending: !engineNeedsRelaunch)
            exportURL = url
        } catch { report = "Could not export report: \(error.localizedDescription)" }
        busy = false
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
                    Text("This prerelease collects iPhone capabilities. Linux, SteamOS and the game graphics bridge are unfinished.")
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
                    Text("The Linux gate requires an engine-bearing build and StikDebug. Keep the app open for up to three minutes. Relaunch before repeating a Linux boot.").font(.callout)
                    if model.busy { ProgressView("Collecting measurements…") }
                    if model.engineNeedsRelaunch { Text("The Linux engine timed out and may still be running. Share the logs, then close and relaunch before another test.").font(.callout) }
                    if let url = model.exportURL { ShareLink("Share device report", item: url) }
                    Button("Share saved diagnostic logs") { model.shareRecovery() }
                        .buttonStyle(.bordered).disabled(model.busy || model.preparingLogShare)
                    if let url = model.recoveredLogURL { ShareLink("Share previous interrupted test logs", item: url) }
                    Text(model.report).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }.padding()
            }.navigationTitle("My-pc SteamOS Probe")
                .task { model.checkRecovery() }
                .onChange(of: scenePhase) { _, phase in if phase == .active { model.refreshJITAttachment() } }
                .alert("Previous test stopped — share logs", isPresented: $model.showRecovery) {
                    Button("Share logs") { model.shareRecovery() }
                    Button("Later", role: .cancel) { model.acknowledgeRecovery() }
                } message: { Text(model.recoveryMessage) }
                .sheet(item: $model.logShare) { DiagnosticShareSheet(url: $0.url) }
        }
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
