import Foundation
import MetricKit

// Receive only OS reports for this application. No network or signal handler.
// The MX subscriber is retained for the app lifetime and works with the iOS 26
// build SDK. System delivery and the crash's original build are not inferred
// from the version of the app that happens to receive the callback.
final class SystemCrashDiagnostics: NSObject, MXMetricManagerSubscriber {
    static let shared = SystemCrashDiagnostics()
    private let queue = DispatchQueue(label: "com.aghjkshdsj.mypc.crash-diagnostics", qos: .utility)
    private let journal = RecoveryJournal(documents: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
    private var started = false

    func start() {
        guard !started else { return }
        started = true
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        // Empty/performance-only payloads cannot stand in for a crash stack.
        for payload in payloads.prefix(8) where !(payload.crashDiagnostics ?? []).isEmpty {
            let data = payload.jsonRepresentation()
            let collector: [String: String] = [
                "build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
                "source_commit": Bundle.main.object(forInfoDictionaryKey: "MPCSourceCommit") as? String ?? "unknown"
            ]
            queue.async {
                // Do not associate this report with an active nonce: delivery
                // can describe an older process. Preserve original OS metadata.
                try? self.journal.recordSystemCrash(data, collector: collector)
            }
        }
    }
}
