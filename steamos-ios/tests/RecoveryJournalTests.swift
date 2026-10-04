import Foundation

@main
struct RecoveryJournalTests {
    static func main() throws {
        guard CommandLine.arguments.count == 2 else { fatalError("Pass the native capture test binary") }
        let fm = FileManager.default
        let documents = fm.temporaryDirectory.appendingPathComponent("MPCRecoveryTests-\(UUID().uuidString)", isDirectory: true)
        try fm.createDirectory(at: documents, withIntermediateDirectories: false)
        defer { try? fm.removeItem(at: documents) } // This test's unique temporary directory only.
        let journal = RecoveryJournal(documents: documents)
        let request = try StikDebugRequest.make(bundleID: "com.example.probe+fixture", pid: 123)
        let route = URLComponents(url: request, resolvingAgainstBaseURL: false)!
        precondition(route.scheme == "stikdebug" && route.host == "enable-jit")
        let queries = Dictionary(uniqueKeysWithValues: route.queryItems!.map { ($0.name, $0.value!) })
        precondition(queries == ["pid": "123", "bundle-id": "com.example.probe+fixture", "script-name": "universal.js"])
        var invalidRequestRejected = false
        do { _ = try StikDebugRequest.make(bundleID: "", pid: -1) } catch { invalidRequestRejected = true }
        precondition(invalidRequestRejected)
        try journal.recordActivation(["url_open_accepted": true, "jit_verified": false, "fixture": true])
        func begin(_ kind: String) throws -> (PendingProbe, URL) {
            let run = PendingProbe(runID: UUID().uuidString, kind: kind, startedUTC: "synthetic-fixture",
                                   sourceCommit: "synthetic-fixture", build: "synthetic-fixture")
            return (run, try journal.begin(run, before: ["fixture": true]))
        }
        func child(_ folder: URL, _ mode: String) throws -> (Int32, String) {
            let process = Process(); let pipe = Pipe()
            process.executableURL = URL(fileURLWithPath: CommandLine.arguments[1])
            process.arguments = [folder.path, mode]; process.standardOutput = pipe
            try process.run(); process.waitUntilExit()
            return (process.terminationStatus, String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self))
        }
        // Real subprocess _exit proves the fsynced native stage survives an
        // abrupt process end, rather than just mocking a completed probe.
        let (run, folder) = try begin("jit-fixture")
        let abruptResult = try child(folder, "abrupt")
        precondition(abruptResult.0 == 77)
        let reopened = RecoveryJournal(documents: documents)
        let snapshot = reopened.pendingSnapshot()!
        let restoredRun = try reopened.pendingRun(snapshot)
        precondition(restoredRun == run)
        precondition(reopened.lastStage(snapshot) == "before-abrupt-exit")
        let share = try reopened.shareReport(snapshot: snapshot)
        let text = try String(contentsOf: share, encoding: .utf8)
        precondition(text.contains("synthetic-engine-stdout") && text.contains("synthetic-engine-stderr"))
        precondition(text.contains("before-abrupt-exit"))
        try reopened.acknowledge(snapshot) // Later/cancelled share keeps logs.
        precondition(reopened.pendingSnapshot() == nil && fm.fileExists(atPath: share.path))
        precondition(fm.fileExists(atPath: folder.appendingPathComponent("stages.jsonl").path))

        let (normal, normalFolder) = try begin("host-fixture")
        let normalResult = try child(normalFolder, "normal")
        precondition(normalResult.0 == 0 && normalResult.1 == "stdout-restored\n")
        try Data("{\"synthetic_vulkan_receipt\":true}".utf8).write(to: normalFolder.appendingPathComponent("vulkan-diagnostic.json"))
        let graphicsExport = try journal.shareReport(snapshot: journal.pendingSnapshot())
        let graphicsObject = try JSONSerialization.jsonObject(with: Data(contentsOf: graphicsExport)) as! [String: Any]
        let graphicsFiles = graphicsObject["files"] as! [[String: Any]]
        precondition(graphicsFiles.contains { $0["name"] as? String == "vulkan-diagnostic.json" &&
            ($0["text"] as? String)?.contains("synthetic_vulkan_receipt") == true })
        // Engine metadata made actual reports slightly larger than 128 KiB.
        // The recovery export must preserve the complete structured receipt.
        let structured = ["fixture_completed": true, "payload": String(repeating: "A", count: 132392)] as [String: Any]
        let structuredData = try JSONSerialization.data(withJSONObject: structured, options: [.sortedKeys])
        try journal.complete(runID: normal.runID, result: structuredData)
        precondition(journal.pendingSnapshot() == nil)
        let completeExport = try journal.shareReport(snapshot: nil)
        let completeObject = try JSONSerialization.jsonObject(with: Data(contentsOf: completeExport)) as! [String: Any]
        let completeEntries = completeObject["files"] as! [[String: Any]]
        let completeReceipt = completeEntries.first {
            $0["name"] as? String == "result.json" &&
            $0["relative_directory"] as? String == "ProbeDiagnostics/" + normal.runID
        }!
        precondition(completeReceipt["tail_truncated"] as? Bool == false)
        precondition(completeReceipt["capture_limit_bytes"] as? Int == 524288)
        let completeText = completeReceipt["text"] as! String
        precondition(Data(completeText.utf8) == structuredData)
        let parsedReceipt = try JSONSerialization.jsonObject(with: Data(completeText.utf8)) as! [String: Any]
        precondition(parsedReceipt["fixture_completed"] as? Bool == true)

        let (another, _) = try begin("linux-fixture")
        try journal.complete(runID: another.runID, result: Data("{\"status\":\"timed-out-engine-still-running\"}".utf8), clearPending: false)
        precondition(journal.pendingSnapshot() != nil) // An engine alive after timeout keeps recovery capture.
        let prior = journal.pendingSnapshot()!
        let marker = journal.directory.appendingPathComponent("pending-run.json")
        try Data("different-marker-fixture".utf8).write(to: marker, options: .atomic)
        try journal.acknowledge(prior)
        precondition(journal.pendingSnapshot() != nil) // Stale UI cannot erase another marker.
        let corrupt = journal.pendingSnapshot()!
        var rejected = false
        do { _ = try journal.pendingRun(corrupt) } catch { rejected = true }
        precondition(rejected)
        _ = try journal.shareReport(snapshot: corrupt)
        try journal.acknowledge(corrupt)

        let malicious = PendingProbe(runID: "../outside", kind: "fixture", startedUTC: "fixture", sourceCommit: "fixture", build: "fixture")
        rejected = false
        do { _ = try journal.pendingRun(JSONEncoder().encode(malicious)) } catch { rejected = true }
        precondition(rejected)

        // Only known diagnostic names are included; symlinks and unrelated
        // user files never enter an export. Large logs are bounded tails.
        let linux = documents.appendingPathComponent("LinuxGate-fixture", isDirectory: true)
        try fm.createDirectory(at: linux, withIntermediateDirectories: false)
        try Data(repeating: 65, count: 262144).write(to: linux.appendingPathComponent("serial.log"))
        let unrelated = documents.appendingPathComponent("unrelated-user-file.txt")
        try Data("DO_NOT_EXPORT_SYNTHETIC_PRIVATE_FILE".utf8).write(to: unrelated)
        try fm.createSymbolicLink(at: linux.appendingPathComponent("linux-test.json"), withDestinationURL: unrelated)
        let bounded = try journal.shareReport(snapshot: nil)
        let body = try String(contentsOf: bounded, encoding: .utf8)
        precondition(!body.contains("DO_NOT_EXPORT_SYNTHETIC_PRIVATE_FILE"))
        let object = try JSONSerialization.jsonObject(with: Data(body.utf8)) as! [String: Any]
        let entries = object["files"] as! [[String: Any]]
        let serial = entries.first { $0["name"] as? String == "serial.log" }!
        precondition(serial["tail_truncated"] as? Bool == true && (serial["text"] as! String).utf8.count == 131072)
        // Bigger JSON is still bounded and explicitly incomplete, never silently
        // accepted as a valid receipt. Existing symlink exclusion stays intact.
        let oversized = try JSONSerialization.data(withJSONObject: ["payload": String(repeating: "B", count: 786432)])
        try oversized.write(to: normalFolder.appendingPathComponent("result.json"))
        let oversizedExport = try journal.shareReport(snapshot: nil)
        let oversizedObject = try JSONSerialization.jsonObject(with: Data(contentsOf: oversizedExport)) as! [String: Any]
        let oversizedEntries = oversizedObject["files"] as! [[String: Any]]
        let oversizedReceipt = oversizedEntries.first {
            $0["name"] as? String == "result.json" &&
            $0["relative_directory"] as? String == "ProbeDiagnostics/" + normal.runID
        }!
        precondition(oversizedReceipt["tail_truncated"] as? Bool == true)
        precondition(oversizedReceipt["captured_bytes"] as? Int == 524288)
        precondition((oversizedReceipt["text"] as! String).utf8.count == 524288)
        precondition(!String(decoding: try Data(contentsOf: oversizedExport), as: UTF8.self).contains("DO_NOT_EXPORT_SYNTHETIC_PRIVATE_FILE"))
        _ = another
        print("RECOVERY_GATE_OK: abrupt-exit stages/output, reopen marker, completion/timeout, retained/cancelled share, stale/corrupt marker, path/symlink exclusion, complete JSON receipts, bounded oversized JSON/log tails and exact StikDebug request")
    }
}
