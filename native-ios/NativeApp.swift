// SPDX-License-Identifier: GPL-3.0-or-later
// My-pc native host overlay; preserves the referenced runtime's attribution.
import SwiftUI
import UIKit
import Darwin

@main
struct MadeiraApp: App {
    init() { NativePerformance.begin() }

    var body: some Scene {
        WindowGroup {
            NativeRootView()
                .modifier(ClaimGamepadEvents())
                .onAppear {
                    GamepadInput.shared.start()
                    HardwareInput.shared.start()
                }
        }
    }
}

private struct NativeRootView: View {
    @ObservedObject private var library = LibraryModel.shared
    @ObservedObject private var steam = SteamOwnedLibrary.shared
    @State private var reportPresented = false

    var body: some View {
        ContentView()
            .overlay(alignment: .bottomTrailing) {
                if library.current == nil {
                    Button { reportPresented = true } label: {
                        Label("Performance report", systemImage: "chart.bar.xaxis")
                            .labelStyle(.iconOnly).padding(12)
                    }
                    .buttonStyle(.bordered).padding()
                    .accessibilityLabel("Performance report")
                }
            }
            .onChange(of: steam.owned.count) { _, count in
                NativePerformance.ownedLibrary(count: count)
            }
            .onReceive(steam.$downloads) { downloads in
                NativePerformance.downloadProgress(downloads.values.map(\.progress))
            }
            .onChange(of: library.current) { _, value in
                if value == nil { NativePerformance.endSession() }
                else { NativePerformance.startSession() }
            }
            .onChange(of: library.launching) { _, launching in
                if !launching, library.current != nil { NativePerformance.sessionReady() }
            }
            .sheet(isPresented: $reportPresented) { NativePerformanceView() }
    }
}

@MainActor
enum NativePerformance {
    private static var began = ProcessInfo.processInfo.systemUptime
    private static var libraryMS: Double?
    private static var ownedMS: Double?
    private static var ownedCount = 0
    private static var sessionBegan: Double?
    private static var readyMS: Double?
    private static var presentsPerSecond: Double?
    private static var capture: Task<Void, Never>?
    private static var cpuMedianMS: Double?
    private static var cpuChecksum: String?
    private static var download: SteamDownloadProgress?

    static func begin() { began = ProcessInfo.processInfo.systemUptime }
    static func libraryVisible() {
        guard libraryMS == nil else { return }
        // Recorded by LibraryView's appearance after SwiftUI has mounted it.
        libraryMS = (ProcessInfo.processInfo.systemUptime - began) * 1000
        LogStore.shared.log("[native-startup] library-ms=\(Int(libraryMS!)) backend=ios-fex-wine-metal vm=0")
    }
    static func ownedLibrary(count: Int) {
        ownedCount = count
        if ownedMS == nil, count > 0 { ownedMS = (ProcessInfo.processInfo.systemUptime - began) * 1000 }
    }
    static func downloadProgress(_ progress: [SteamDownloadProgress]) {
        if let active = progress.first(where: { $0.totalBytes > 0 }) { download = active }
    }
    static func startSession() {
        capture?.cancel(); capture = nil
        sessionBegan = ProcessInfo.processInfo.systemUptime
        readyMS = nil; presentsPerSecond = nil
    }
    static func sessionReady() {
        guard readyMS == nil, let start = sessionBegan, wine_process_is_running() != 0 else { return }
        readyMS = (ProcessInfo.processInfo.systemUptime - start) * 1000
        // This counts actual presents after the runtime's starting screen ends.
        // It is not a synthetic GPU workload or the phone's display-link rate.
        capture = Task {
            let count = madeira_get_present_count()
            let time = ProcessInfo.processInfo.systemUptime
            do { try await Task.sleep(for: .seconds(5)) } catch { return }
            guard wine_process_is_running() != 0 else { return }
            let end = madeira_get_present_count()
            if end >= count {
                presentsPerSecond = Double(end - count) / (ProcessInfo.processInfo.systemUptime - time)
            }
        }
    }
    static func endSession() { capture?.cancel(); capture = nil }

    static func runCPU() async {
        let result = await Task.detached(priority: .userInitiated) { () -> (Double, String) in
            var samples: [Double] = []
            var checksums: [String] = []
            for sample in 0..<7 {
                let start = ProcessInfo.processInfo.systemUptime
                var value: UInt64 = UInt64(sample + 1)
                for _ in 0..<1_000_000 {
                    value ^= value >> 12
                    value ^= value << 25
                    value ^= value >> 27
                    value = value &* 2_685_821_657_736_338_717
                }
                samples.append((ProcessInfo.processInfo.systemUptime - start) * 1000)
                checksums.append(String(format: "%016llx", value))
            }
            return (samples.sorted()[samples.count / 2], checksums.joined(separator: ","))
        }.value
        cpuMedianMS = result.0; cpuChecksum = result.1
    }

    private static var residentMiB: Double? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let status = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        return status == KERN_SUCCESS ? Double(info.phys_footprint) / 1_048_576 : nil
    }

    static func report() throws -> (String, URL) {
        let info = Bundle.main.infoDictionary ?? [:]
        let process = ProcessInfo.processInfo
        var value: [String: Any] = [
            "schema": 1, "backend": "native-ios-fex-wine-metal", "vm_started": false,
            "build": info["CFBundleVersion"] as? String ?? "unknown",
            "commit": info["SomethingPCBuildCommit"] as? String ?? "unknown",
            "runtime_source": info["MyPCNativeSourceCommit"] as? String ?? "unknown",
            "ios_version": UIDevice.current.systemVersion,
            "host_available_cpus": process.activeProcessorCount,
            "low_power_mode": process.isLowPowerModeEnabled,
            "thermal_state": process.thermalState.rawValue,
            "owned_game_count": ownedCount,
            "wine_running": wine_process_is_running() != 0,
            "measurement_scope": "app init to library appearance; excludes pre-main and external tap time"
        ]
        if let libraryMS { value["app_init_to_library_ms"] = libraryMS }
        if let ownedMS { value["app_init_to_owned_library_ms"] = ownedMS }
        if let readyMS { value["session_request_to_ready_ms"] = readyMS }
        if let presentsPerSecond { value["metal_presents_per_s_after_session_ready"] = presentsPerSecond }
        if let memory = residentMiB { value["host_app_memory_mib"] = memory }
        if let download {
            value["last_download_phase"] = download.phase.rawValue
            value["last_download_total_bytes"] = download.totalBytes
            value["last_download_completed_bytes"] = download.doneBytes
            value["last_download_bytes_per_s"] = download.bytesPerSecond
        }
        if let cpuMedianMS {
            value["native_cpu_median_ms"] = cpuMedianMS
            value["native_cpu_checksum"] = cpuChecksum
            value["native_cpu_iterations"] = 1_000_000
            value["native_cpu_samples"] = 7
        }
        let data = try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys])
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("MyPCNativeReports", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let url = directory.appendingPathComponent("native-performance.json")
        try data.write(to: url, options: .atomic)
        return (String(decoding: data, as: UTF8.self), url)
    }
}

private struct NativePerformanceView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var url: URL?
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Library startup, native CPU timing and the last game's Metal presents.")
                    Text("For a cold-launch comparison, also time from tapping the app icon to seeing your library.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button(busy ? "Running CPU test…" : "Run native CPU test") {
                        busy = true
                        Task { await NativePerformance.runCPU(); busy = false; refresh() }
                    }.disabled(busy)
                    Button("Refresh report", action: refresh)
                    if let url { ShareLink("Share report", item: url) }
                }
                Section {
                    Text(text).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                }
            }
            .navigationTitle("Performance")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } } }
            .onAppear(perform: refresh)
        }
    }

    private func refresh() {
        do { (text, url) = try NativePerformance.report() }
        catch { text = "Could not write the report: " + error.localizedDescription; url = nil }
    }
}
