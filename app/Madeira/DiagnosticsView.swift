import SwiftUI

struct DiagnosticsView: View {
    @State private var report: SharedReport?
    @State private var preparing = false
    @State private var error: String?
    var body: some View {
        Form {
            Section("Support report") {
                Text("Includes startup stages, effective game settings, the selected EXE, library candidates, device/build details, memory and thermal history, runtime versions, and runtime logs. iOS crash/hang diagnostics are included when the system delivers them.")
                Button("Share current diagnostic report", systemImage: "square.and.arrow.up") {
                    preparing = true
                    Task {
                        do { report = SharedReport(url: try await Task.detached(priority: .utility) { try SupportReport.current() }.value) }
                        catch { self.error = error.localizedDescription }
                        preparing = false
                    }
                }.disabled(preparing)
                if preparing { ProgressView("Preparing report…") }
                if let previous = CrashRecovery.shared.report {
                    Button("Share last unexpected-close report") { report = SharedReport(url: previous) }
                }
                Text("Reports stay on your phone. Review before sharing: they can include game filenames, file paths, and game output. Nothing is uploaded automatically.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Capture limits") {
                Text("A force-quit, memory-pressure termination, or native crash can end the process before it records a final message. MetricKit reports may arrive later or not at all. If the cause is still unclear, include the matching iOS Analytics .ips or JetsamEvent report.")
                    .font(.caption).foregroundStyle(.secondary)
                Text("Signal handlers used by Wine and FEX are not replaced. Debug reports retain the start and end of large logs, not an unlimited trace.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Diagnostics")
        .sheet(item: $report) { DiagnosticShareSheet(url: $0.url) }
        .alert("Diagnostics", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("OK", role: .cancel) { error = nil }
        } message: { Text(error ?? "") }
    }
}
