import Foundation

enum LinuxVMError: LocalizedError {
    case invalid(String)
    var errorDescription: String? { if case .invalid(let message) = self { return message }; return nil }
}

/// Arguments passed directly to QEMU, never through a shell.
struct LinuxVMConfiguration {
    let directory: URL
    let log: URL
    let control: URL
    var memoryMiB = 2048
    var cpuCount = 2

    func arguments() throws -> [String] {
        guard (512...3072).contains(memoryMiB), (1...4).contains(cpuCount) else {
            throw LinuxVMError.invalid("Linux requires 512–3072 MB RAM and 1–4 CPU cores.")
        }
        // QEMU's Unix socket chardev uses the platform sockaddr_un path limit.
        guard control.isFileURL, control.path.utf8.count < 100,
              !control.path.contains(","), !control.path.contains("\n"),
              log.isFileURL, !log.path.contains(","), !log.path.contains("\n") else {
            throw LinuxVMError.invalid("The Linux control or log path is invalid or too long.")
        }
        let files = try ["Image", "initrd.img", "rootfs.raw"].map { try asset($0) }
        let kernel = try FileHandle(forReadingFrom: files[0])
        defer { try? kernel.close() }
        let header = try kernel.read(upToCount: 64) ?? Data()
        // Linux's uncompressed ARM64 Image magic, at offset 0x38.
        guard header.count == 64, Array(header[56..<60]) == [0x41, 0x52, 0x4d, 0x64] else {
            throw LinuxVMError.invalid("The Linux kernel is not an ARM64 Image.")
        }
        let disk = try FileHandle(forReadingFrom: files[2])
        defer { try? disk.close() }
        try disk.seek(toOffset: 1080)
        guard try disk.read(upToCount: 2) == Data([0x53, 0xef]) else {
            throw LinuxVMError.invalid("The Linux disk is not a raw ext4 filesystem.")
        }
        let storage = try json(["driver": "file", "filename": files[2].path, "node-name": "linux-file"])
        let raw = try json(["driver": "raw", "file": "linux-file", "node-name": "linux-root"])
        return ["qemu-system-aarch64", "-no-user-config", "-nodefaults",
                "-machine", "virt-10.0,highmem=off", "-cpu", "cortex-a72",
                "-accel", "tcg,thread=multi,tb-size=128,split-wx=on",
                "-smp", String(cpuCount), "-m", String(memoryMiB),
                "-kernel", files[0].path, "-initrd", files[1].path,
                "-append", "console=ttyAMA0 root=/dev/vda rw quiet loglevel=3",
                "-blockdev", storage, "-blockdev", raw,
                "-device", "virtio-blk-pci,drive=linux-root",
                "-netdev", "user,id=linux-net", "-device", "virtio-net-pci,netdev=linux-net",
                "-device", "virtio-gpu-pci,xres=960,yres=540",
                "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd",
                "-display", "none", "-monitor", "none", "-no-reboot",
                "-chardev", "file,id=linux-serial,path=\(log.path)", "-serial", "chardev:linux-serial",
                "-chardev", "socket,id=linux-control,path=\(control.path),server=on,wait=off",
                "-mon", "chardev=linux-control,mode=control"]
    }

    private func asset(_ name: String) throws -> URL {
        let root = directory.standardizedFileURL
        let file = root.appendingPathComponent(name)
        guard root.isFileURL, root.resolvingSymlinksInPath() == root,
              file.resolvingSymlinksInPath() == file else {
            throw LinuxVMError.invalid("Linux runtime files cannot be symbolic links.")
        }
        let values = try file.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        guard values.isRegularFile == true, (values.fileSize ?? 0) > 0 else {
            throw LinuxVMError.invalid("Missing Linux runtime file: \(name)")
        }
        return file
    }

    private func json(_ object: [String: String]) throws -> String {
        String(decoding: try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]), as: UTF8.self)
    }
}

/// QMP envelopes use explicit ids so asynchronous events never count as replies.
enum LinuxQMP {
    static let maxMessageBytes = 1_048_576
    static func command(_ name: String, id: Int, arguments: [String: Any] = [:]) throws -> Data {
        guard ["qmp_capabilities", "query-status", "stop", "cont", "system_powerdown", "input-send-event"].contains(name) else {
            throw LinuxVMError.invalid("Unsupported Linux control command.")
        }
        var object: [String: Any] = ["execute": name, "id": id]
        if !arguments.isEmpty { object["arguments"] = arguments }
        var data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        data.append(contentsOf: [13, 10])
        return data
    }

    static func reply(_ data: Data, id: Int) throws -> Bool {
        guard data.count <= maxMessageBytes,
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw LinuxVMError.invalid("Invalid Linux control response.")
        }
        guard object["id"] as? Int == id else { return false }
        if let error = object["error"] as? [String: Any] {
            throw LinuxVMError.invalid(error["desc"] as? String ?? "Linux control command failed.")
        }
        guard object["return"] != nil else { throw LinuxVMError.invalid("Linux returned an incomplete control response.") }
        return true
    }

    static func pointer(x: Double, y: Double, down: Bool) -> [String: Any] {
        func coordinate(_ value: Double) -> Int { value.isFinite ? Int(min(1, max(0, value)) * 32767) : 0 }
        return ["events": [
            ["type": "abs", "data": ["axis": "x", "value": coordinate(x)]],
            ["type": "abs", "data": ["axis": "y", "value": coordinate(y)]],
            ["type": "btn", "data": ["button": "left", "down": down]]
        ]]
    }
}
