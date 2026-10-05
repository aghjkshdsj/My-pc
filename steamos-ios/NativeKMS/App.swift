// SPDX-License-Identifier: MIT
import SwiftUI
import UIKit
import Darwin

@main struct NativeKMSApp: App {
    init() { SystemCrashDiagnostics.shared.start() }
    var body: some Scene { WindowGroup { NativeKMSScreen() } }
}
private struct SharedFile: Identifiable { let id = UUID(); let url: URL }
private struct NativeSurface: UIViewRepresentable {
    func makeUIView(context: Context) -> UIView { MPCNativeKMSCreateView() }
    func updateUIView(_ view: UIView, context: Context) {}
}
private struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ view: UIActivityViewController, context: Context) {}
}
@MainActor private final class NativeKMSModel: ObservableObject {
    @Published var busy = false
    @Published var needsRelaunch = false
    @Published var showScreen = false
    @Published var recovery = false
    @Published var message = "Enable JIT, check it, then open the Linux display test."
    @Published var share: SharedFile?
    private let journal = RecoveryJournal(documents: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
    private var interrupted: Data?
    private var reportURL: URL?
    private var checked = false
    func checkRecovery() {
        guard !checked else { return }; checked = true
        interrupted = journal.pendingSnapshot()
        if let interrupted {
            message = "The last test did not finish. Last stage: \(journal.lastStage(interrupted) ?? "preparation"). Share its saved logs."
            recovery = true
        }
    }
    func acknowledge() {
        if let interrupted { try? journal.acknowledge(interrupted) }
        interrupted = nil
    }
    func shareLogs() {
        do {
            let url = try journal.shareReport(snapshot: interrupted ?? journal.pendingSnapshot())
            acknowledge()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.share = SharedFile(url: url) }
        } catch { message = error.localizedDescription }
    }
    func shareReport() { if let reportURL { share = SharedFile(url: reportURL) } }
    func enableJIT() {
        do {
            let url = try StikDebugRequest.make(bundleID: Bundle.main.bundleIdentifier ?? "", pid: getpid())
            guard UIApplication.shared.canOpenURL(url) else { message = "StikDebug is unavailable."; return }
            UIApplication.shared.open(url) { opened in
                Task { @MainActor in self.message = opened ? "Confirm universal.js in StikDebug, return here, then run the JIT check." : "StikDebug could not open." }
            }
        } catch { message = error.localizedDescription }
    }
    func run(linux: Bool) {
        guard !busy && (!linux || !needsRelaunch) else { return }
        let id = UUID().uuidString
        let before = MPCPlatformFacts()
        let pending = PendingProbe(runID: id, kind: linux ? "linux-native-kms" : "jit", startedUTC: ISO8601DateFormatter().string(from: Date()),
            sourceCommit: Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "unknown",
            build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown")
        let directory: URL
        do {
            directory = try journal.begin(pending, before: before)
            guard MPCStartDiagnosticCapture(directory.path) else { throw NSError(domain: "NativeKMS", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not start durable capture. Relaunch and share logs."]) }
        } catch { message = error.localizedDescription; return }
        busy = true; message = linux ? "Running Linux’s standard display completion test…" : "Running ARM64 JIT check…"
        Task.detached(priority: .userInitiated) {
            let result = linux ? MPCNativeKMSRun() : MPCExecuteJITProbe()
            let timedOut = result["status"] as? String == "timed-out-engine-still-running"
            if !timedOut { MPCStopDiagnosticCapture() }
            let report: [String: Any] = ["schema": 1, "scope": "private-native-kms-device-test",
                "build": pending.build, "source_commit": pending.sourceCommit, "test": result,
                "engine_output": MPCDiagnosticOutputSnapshot(directory.path)]
            do {
                let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
                await self.finish(id: id, data: data, result: result, linux: linux, timedOut: timedOut)
            } catch { await self.failedSave(error.localizedDescription) }
        }
    }
    private func failedSave(_ error: String) { message = "Could not save the result: \(error). Share logs."; busy = false; needsRelaunch = true }
    private func finish(id: String, data: Data, result: [AnyHashable: Any], linux: Bool, timedOut: Bool) {
        do {
            try journal.complete(runID: id, result: data, clearPending: !timedOut)
            let url = journal.documents.appendingPathComponent("MyPCSteamOS-Probe-\(id).json")
            try data.write(to: url, options: .atomic); reportURL = url
        } catch { failedSave(error.localizedDescription); return }
        busy = false
        if linux {
            needsRelaunch = result["requires_relaunch"] as? Bool == true
            message = result["standard_kms_native_completion_verified"] as? Bool == true
                ? "Linux standard display completion passed: eight Linux frames, positive output fences, matching flip events and actual Metal completion. \(result["validation_status"] as? String == "unavailable" ? "Vulkan validation layers are unavailable. " : "")Desktop, Steam and games remain unfinished. Share the report and logs."
                : "Linux display test \(result["status"] ?? "failed"): \(result["reason"] ?? result["stage"] ?? "Share the report and saved logs.")"
        } else {
            message = result["status"] as? String == "passed" ? "ARM64 JIT passed. Open the Linux standard display test next." : "JIT \(result["status"] ?? "failed"): \(result["reason"] ?? "Share logs.")"
        }
    }
}
private struct NativeKMSScreen: View {
    @StateObject private var model = NativeKMSModel()
    var body: some View {
        VStack(spacing: 16) {
            Text(model.showScreen ? "Linux standard display test" : "My-pc Linux display gate").font(.title2)
            Text("SteamOS desktop and ARM Steam remain unfinished.").font(.caption)
            if model.showScreen {
                NativeSurface().frame(maxWidth: .infinity, maxHeight: .infinity).background(.black)
                Button("Start Linux display test") { model.run(linux: true) }.disabled(model.busy || model.needsRelaunch)
                Button("Return to report") { model.showScreen = false }.disabled(model.busy)
            } else {
                Button("Enable JIT in StikDebug") { model.enableJIT() }.disabled(model.busy || model.needsRelaunch)
                Button("Run ARM64 JIT check") { model.run(linux: false) }.disabled(model.busy || model.needsRelaunch)
                Button("Open Linux standard display test") { model.showScreen = true }.disabled(model.busy || model.needsRelaunch)
                Spacer()
            }
            if model.busy { ProgressView() }
            Text(model.message).font(.callout)
            Button("Share device report") { model.shareReport() }.disabled(model.busy)
            Button("Share saved logs") { model.shareLogs() }.disabled(model.busy)
        }
        .padding().buttonStyle(.borderedProminent)
        .onAppear { model.checkRecovery() }
        .alert("Share logs from the interrupted test?", isPresented: $model.recovery) {
            Button("Share logs") { model.shareLogs() }
            Button("Later", role: .cancel) { model.acknowledge() }
        } message: { Text(model.message) }
        .sheet(item: $model.share) { ShareSheet(url: $0.url) }
    }
}
