import SwiftUI
import UIKit

final class CrashRecovery: ObservableObject {
    static let shared = CrashRecovery()
    @Published var prompt = false
    @Published var report: URL?
    private let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    private var marker: URL { documents.appendingPathComponent("somethingpc-session.json") }
    private var reports: URL { documents.appendingPathComponent("Diagnostics", isDirectory: true) }
    private var game = "Library"

    private init() {
        let manager = FileManager.default
        do {
            try manager.createDirectory(at: reports, withIntermediateDirectories: true)
            if let data = try? Data(contentsOf: marker),
               let previous = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               previous["foreground"] as? Bool == true {
                let destination = reports.appendingPathComponent("Unexpected-close-\(UUID().uuidString).txt")
                let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown"
                var output = Data("Something PC \(version)\niOS \(UIDevice.current.systemVersion)\nPrevious session: \(previous)\nAn unfinished foreground session was detected. This may be a crash, force-quit, or OS termination; this is not a crash stack trace.\nLogs may contain game names, paths, and other private information. Review before sharing.\n\n".utf8)
                output.append(SupportReport.context())
                output.append(SupportReport.log())
                try output.write(to: destination, options: .atomic)
                UserDefaults.standard.set(destination.lastPathComponent, forKey: "pendingCrashReport")
            }
            if let name = UserDefaults.standard.string(forKey: "pendingCrashReport"),
               name == URL(fileURLWithPath: name).lastPathComponent {
                let candidate = reports.appendingPathComponent(name)
                if manager.fileExists(atPath: candidate.path) { report = candidate; prompt = true }
            }
            let existing = try manager.contentsOfDirectory(at: reports, includingPropertiesForKeys: [.creationDateKey])
                .filter { $0.lastPathComponent.hasPrefix("Unexpected-close-") && $0.pathExtension == "txt" }
                .sorted { ((try? $0.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast) > ((try? $1.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? .distantPast) }
            if report == nil { report = existing.first }
            for old in existing.dropFirst(5) where old != report { try? manager.removeItem(at: old) }
        } catch {
            NSLog("Could not preserve previous session logs: %@", error.localizedDescription)
        }
        record(foreground: false)
    }

    func record(foreground: Bool) {
        let values: [String: Any] = ["foreground": foreground, "game": game,
            "time": ISO8601DateFormatter().string(from: Date())]
        do { try JSONSerialization.data(withJSONObject: values).write(to: marker, options: .atomic) }
        catch { NSLog("Could not save session marker: %@", error.localizedDescription) }
    }

    func launching(_ title: String) { game = title; record(foreground: true) }
    func acknowledge() {
        prompt = false
        UserDefaults.standard.removeObject(forKey: "pendingCrashReport")
    }
}

struct DiagnosticShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
