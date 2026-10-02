// SPDX-License-Identifier: GPL-3.0-or-later
import Foundation

func rejects(_ operation: () throws -> Void) {
    var rejected = false
    do { try operation() } catch { rejected = true }
    precondition(rejected, "Unsafe desktop Steam input was accepted")
}

@main struct DesktopSteamChecks {
    static func main() throws {
        let manifest = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
        let plan = try NativeSteamDesktopFiles.manifest(manifest)
        precondition(plan.version == 1788652215 && plan.packages.count == 18)
        precondition(plan.packages.contains { $0.file.hasPrefix("steam_win64.zip.") && $0.bytes == 2668385 })
        let text = String(decoding: manifest, as: UTF8.self)
        for bad in [text.replacingOccurrences(of: "steam_win64.zip.", with: "../steam_win64.zip."),
                    text.replacingOccurrences(of: "\"bins_cef_win64\"", with: "\"missing_cef\""),
                    text.replacingOccurrences(of: "\"2668385\"", with: "\"0\""),
                    text.replacingOccurrences(of: "5dbc39918056cc8b7815daaa181eb3fa19a264b25dab33f3d1ad631b79ee3bb8", with: "wrong") ] {
            precondition(bad != text)
            rejects { _ = try NativeSteamDesktopFiles.manifest(Data(bad.utf8)) }
        }
        rejects { _ = try NativeSteamDesktopFiles.manifest(Data("\"win64\" { \"version\" \"1\" }".utf8)) }
        var pe = Data(repeating: 0, count: 128)
        pe[0] = 0x4d; pe[1] = 0x5a; pe[60] = 64; pe[64] = 0x50; pe[65] = 0x45; pe[68] = 0x64; pe[69] = 0x86
        precondition(NativeSteamDesktopFiles.isAMD64(pe))
        pe[68] = 0x4c; pe[69] = 1; precondition(!NativeSteamDesktopFiles.isAMD64(pe))
        pe[60] = 0xff; pe[61] = 0xff; precondition(!NativeSteamDesktopFiles.isAMD64(pe))
        precondition(!NativeSteamDesktopFiles.isAMD64(Data([0x4d, 0x5a])))
        let fixture = URL(fileURLWithPath: CommandLine.arguments[2])
        var count = 0
        try SteamRuntimeFiles.unpack(Data(contentsOf: fixture.appendingPathComponent("valid.zip")), desktop: true) { name, bytes in
            precondition(name == "bin/cef/cef.win64/libcef.dll" && bytes == Data("fixture".utf8)); count += 1
        }
        precondition(count == 1)
        for name in ["traversal.zip", "collision.zip", "link.zip", "crc.zip"] {
            rejects { try SteamRuntimeFiles.unpack(Data(contentsOf: fixture.appendingPathComponent(name)), desktop: true) { _, _ in } }
        }
        let large = try Data(contentsOf: fixture.appendingPathComponent("large.zip"))
        rejects { try SteamRuntimeFiles.unpack(large) { _, _ in } }
        try SteamRuntimeFiles.unpack(large, desktop: true) { name, bytes in
            precondition(name == "large.dll" && bytes.count == 65 * 1024 * 1024)
        }
        let user = #"""
        WINE REGISTRY Version 2
        [Software\\Valve\\Steam]
        "SteamPath"="C:\\SteamDesktop"
        "SteamExe"="C:\\SteamDesktop\\steam.exe"
        "RememberPassword"="keep"
        [Software\\Valve\\Steam\\ActiveProcess]
        "SteamClientDll"="C:\\SteamDesktop\\steamclient.dll"
        "SteamClientDll64"="C:\\SteamDesktop\\steamclient64.dll"
        "pid"=dword:00000003
        """#
        let fixed = try NativeSteamDesktopFiles.registryForLibrary(user, machine: false)
        precondition(!fixed.contains("SteamDesktop") && fixed.contains("Program Files (x86)"))
        precondition(fixed.contains("\"RememberPassword\"=\"keep\"") && fixed.contains("\"pid\"=dword:00000003"))
        let unchanged = try NativeSteamDesktopFiles.registryForLibrary(fixed, machine: false)
        precondition(unchanged == fixed)
        rejects { _ = try NativeSteamDesktopFiles.registryForLibrary(user.replacingOccurrences(of: "SteamDesktop", with: "SteamDesktopOther"), machine: false) }
        rejects { _ = try NativeSteamDesktopFiles.registryForLibrary("changed hive", machine: true) }
        let drive = fixture.appendingPathComponent("drive_c")
        let apps = drive.appendingPathComponent(SteamInstallPaths.libraryRelative)
        try FileManager.default.createDirectory(at: apps, withIntermediateDirectories: true)
        try Data("\"AppState\" { \"appid\" \"2019300\" \"SizeOnDisk\" \"1000\" \"installdir\" \"Dokimon\" }".utf8).write(to: apps.appendingPathComponent("appmanifest_2019300.acf"))
        let folders = try NativeSteamDesktopFiles.libraryFolders(drive: drive)
        var kv = try SteamKeyValues(Data(folders.utf8))
        let result = try kv.read()
        precondition(result["libraryfolders"]?["1"]?["apps"]?["2019300"]?.string == "1000")
        precondition(result["libraryfolders"]?["1"]?["path"]?.string == SteamRuntimeFiles.windowsRoot)
        precondition(NativeSteamDesktopFiles.batch.contains("C:\\SteamDesktop\\steam.exe"))
        precondition(!NativeSteamDesktopFiles.batch.contains("token") && !NativeSteamDesktopFiles.batch.contains("password"))
        print("PASS: actual desktop manifest, package bounds, ZIP CRC/traversal/symlinks, x64 PE headers, library sharing and registry restoration")
    }
}
