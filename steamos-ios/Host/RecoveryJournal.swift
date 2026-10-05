import Foundation

struct PendingProbe: Codable, Equatable {
    let runID: String
    let kind: String
    let startedUTC: String
    let sourceCommit: String
    let build: String
}

// Foundation-only so interrupted/completed/export cases can run outside iOS.
final class RecoveryJournal {
    let documents: URL
    let directory: URL
    private let files = FileManager.default
    private var marker: URL { directory.appendingPathComponent("pending-run.json") }

    init(documents: URL) {
        self.documents = documents
        directory = documents.appendingPathComponent("ProbeDiagnostics", isDirectory: true)
    }

    private func durableWrite(_ data: Data, to url: URL) throws {
        try data.write(to: url, options: .atomic)
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        try handle.synchronize()
    }

    private func runDirectory(_ runID: String) throws -> URL {
        guard UUID(uuidString: runID) != nil else {
            throw NSError(domain: "RecoveryJournal", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid run ID"])
        }
        return directory.appendingPathComponent(runID, isDirectory: true)
    }

    func begin(_ run: PendingProbe, before: [AnyHashable: Any]) throws -> URL {
        try files.createDirectory(at: directory, withIntermediateDirectories: true)
        guard !files.fileExists(atPath: marker.path) else {
            throw NSError(domain: "RecoveryJournal", code: 2, userInfo: [NSLocalizedDescriptionKey: "Share or dismiss the previous interrupted run first"])
        }
        let folder = try runDirectory(run.runID)
        try files.createDirectory(at: folder, withIntermediateDirectories: false)
        let data = try JSONEncoder().encode(run)
        try durableWrite(data, to: folder.appendingPathComponent("run.json"))
        try durableWrite(JSONSerialization.data(withJSONObject: before, options: [.prettyPrinted, .sortedKeys]),
                         to: folder.appendingPathComponent("before.json"))
        // This reaches disk before any JIT allocation/call or engine entry point.
        try durableWrite(data, to: marker)
        return folder
    }

    func pendingSnapshot() -> Data? { try? Data(contentsOf: marker) }

    func recordSystemCrash(_ data: Data, collector: [String: String]) throws {
        // Bound individual OS payloads before parsing or storing. Keep all
        // saved reports; export only the three most recent complete snapshots.
        guard data.count > 0, data.count <= 384 * 1024,
              let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let crashes = payload["crashDiagnostics"] as? [[String: Any]], !crashes.isEmpty else {
            throw NSError(domain: "RecoveryJournal", code: 4, userInfo: [NSLocalizedDescriptionKey: "No bounded system crash payload"])
        }
        let row: [String: Any] = ["schema": 1, "scope": "private-apple-metrickit-crash-diagnostics",
            "origin": "apple-metrickit", "received_utc": ISO8601DateFormatter().string(from: Date()),
            "collector": collector, "system_payload": payload, "automatically_uploaded": false,
            "active_probe_nonce_bound": false,
            "limitation": "OS-provided diagnostic, possibly from an earlier process/build. Collector identity is not crash identity. Delivery is not guaranteed; absence does not establish no crash. Inspect original system metadata and matching binary UUIDs."]
        let encoded = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
        guard encoded.count <= 512 * 1024 else {
            throw NSError(domain: "RecoveryJournal", code: 5, userInfo: [NSLocalizedDescriptionKey: "System crash report exceeds export budget"])
        }
        try files.createDirectory(at: directory, withIntermediateDirectories: true)
        try durableWrite(encoded, to: directory.appendingPathComponent("SystemCrash-\(UUID().uuidString).json"))
    }

    func recordActivation(_ details: [String: Any]) throws {
        try files.createDirectory(at: directory, withIntermediateDirectories: true)
        var row = details
        row["collected_utc"] = ISO8601DateFormatter().string(from: Date())
        try durableWrite(JSONSerialization.data(withJSONObject: row, options: [.prettyPrinted, .sortedKeys]),
                         to: directory.appendingPathComponent("stikdebug-request.json"))
    }

    func pendingRun(_ snapshot: Data) throws -> PendingProbe {
        let run = try JSONDecoder().decode(PendingProbe.self, from: snapshot)
        _ = try runDirectory(run.runID)
        return run
    }

    func complete(runID: String, result: Data, clearPending: Bool = true) throws {
        let folder = try runDirectory(runID)
        try durableWrite(result, to: folder.appendingPathComponent("result.json"))
        // Do not erase another run's marker or one whose identity is unreadable.
        if clearPending, let snapshot = pendingSnapshot(), let pending = try? pendingRun(snapshot), pending.runID == runID {
            try files.removeItem(at: marker)
        }
    }

    func acknowledge(_ snapshot: Data) throws {
        guard pendingSnapshot() == snapshot else { return }
        // Keep evidence when the user cancels the share sheet or chooses Later.
        let saved = directory.appendingPathComponent("interrupted-\(UUID().uuidString).json")
        try files.moveItem(at: marker, to: saved)
    }

    private func textFile(_ url: URL) throws -> [String: Any] {
        // Receipts include the pinned engine metadata and bounded Metal ledger.
        // Keep ordinary receipts intact instead of exporting an invalid JSON
        // suffix. Both classes remain bounded; oversized entries stay explicitly
        // truncated and cannot establish a successful diagnostic result.
        let limit = url.pathExtension == "json" ? 2 * 1024 * 1024 : 1024 * 1024
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true else {
            throw NSError(domain: "RecoveryJournal", code: 3, userInfo: [NSLocalizedDescriptionKey: "Not a regular diagnostic file"])
        }
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let size = UInt64(max(0, values.fileSize ?? 0))
        if size > UInt64(limit) { try handle.seek(toOffset: size - UInt64(limit)) }
        let data = try handle.read(upToCount: limit) ?? Data()
        return ["name": url.lastPathComponent, "file_bytes": size, "captured_bytes": data.count,
                "capture_limit_bytes": limit, "tail_truncated": size > UInt64(limit),
                "text": String(decoding: data, as: UTF8.self)]
    }

    private func recent(_ folder: URL, prefix: String, maximum: Int, runDirectoriesOnly: Bool = false) -> [URL] {
        let urls = (try? files.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.contentModificationDateKey], options: [.skipsHiddenFiles])) ?? []
        return Array(urls.filter { $0.lastPathComponent.hasPrefix(prefix) &&
            (!runDirectoriesOnly || UUID(uuidString: $0.lastPathComponent) != nil) }.sorted {
            let left = (try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let right = (try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return left > right
        }.prefix(maximum))
    }

    func lastStage(_ snapshot: Data) -> String? {
        guard let run = try? pendingRun(snapshot), let folder = try? runDirectory(run.runID),
              let row = try? textFile(folder.appendingPathComponent("stages.jsonl")), let text = row["text"] as? String else { return nil }
        for line in text.split(separator: "\n").reversed() {
            if let data = String(line).data(using: .utf8),
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let stage = object["stage"] as? String { return stage }
        }
        return nil
    }

    func shareReport(snapshot: Data?) throws -> URL {
        var entries: [[String: Any]] = []
        var pending: Any = NSNull()
        if var entry = try? textFile(directory.appendingPathComponent("stikdebug-request.json")) {
            entry["relative_directory"] = "ProbeDiagnostics"; entries.append(entry)
        }
        for url in recent(directory, prefix: "SystemCrash-", maximum: 3)
            where url.pathExtension == "json" {
            if var entry = try? textFile(url) {
                entry["relative_directory"] = "ProbeDiagnostics"; entries.append(entry)
            }
        }
        if let snapshot {
            pending = (try? JSONSerialization.jsonObject(with: snapshot)) ?? ["unreadable_marker": String(decoding: snapshot.prefix(4096), as: UTF8.self)]
        }
        let run = snapshot.flatMap { try? pendingRun($0) }
        var folders: [URL] = []
        if let run, let folder = try? runDirectory(run.runID) { folders = [folder] }
        else { folders = recent(directory, prefix: "", maximum: 3, runDirectoriesOnly: true) }
        for folder in folders {
            for name in ["run.json", "before.json", "stages.jsonl", "engine-output.log", "vulkan-diagnostic.json", "result.json"] {
                if var entry = try? textFile(folder.appendingPathComponent(name)) {
                    entry["relative_directory"] = "ProbeDiagnostics/" + folder.lastPathComponent
                    entries.append(entry)
                }
            }
        }
        // Only the probe's known report names and disposable kernel logs.
        for report in recent(documents, prefix: "MyPCSteamOS-Probe-", maximum: 3) {
            if var entry = try? textFile(report) { entry["relative_directory"] = "."; entries.append(entry) }
        }
        for folder in recent(documents, prefix: "LinuxGate-", maximum: 2) {
            for name in ["serial.log", "linux-test.json"] {
                if var entry = try? textFile(folder.appendingPathComponent(name)) {
                    entry["relative_directory"] = folder.lastPathComponent; entries.append(entry)
                }
            }
        }
        let report: [String: Any] = ["schema": 1, "scope": "private-ios-interrupted-probe-diagnostics",
            "collected_utc": ISO8601DateFormatter().string(from: Date()), "pending_test": pending,
            "last_saved_stage": snapshot.flatMap { lastStage($0) } ?? "unavailable", "files": entries,
            "limitation": "A pending test means no result was saved. Crash, OS termination or force-close are possible; the stage journal is not a fault stack or proof of cause. Separately saved Apple MetricKit payloads, if delivered, retain their original OS metadata and are not automatically bound to a probe nonce. No automatic upload. Linux/Steam/graphics success is not inferred."]
        let output = documents.appendingPathComponent("SharedDiagnostics", isDirectory: true)
        try files.createDirectory(at: output, withIntermediateDirectories: true)
        let url = output.appendingPathComponent("MyPCSteamOS-Recovery-\(UUID().uuidString).json")
        try durableWrite(JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]), to: url)
        return url
    }
}
