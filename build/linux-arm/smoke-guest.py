#!/usr/bin/env python3
"""Boot a real ARM64 kernel twice; require networking and durable disk writes."""
import functools
import http.server
import pathlib
import subprocess
import sys
import tempfile
import threading

guest = pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as directory:
    pathlib.Path(directory, "probe.txt").write_text("my-pc-network-ok\n")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 18080), functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for boot in (1, 2):
            command = ["qemu-system-aarch64", "-machine", "virt", "-cpu", "cortex-a72", "-accel", "tcg,thread=multi,tb-size=128", "-smp", "2", "-m", "768", "-display", "none", "-monitor", "none", "-serial", "stdio", "-no-reboot", "-kernel", str(guest / "Image"), "-initrd", str(guest / "initrd.img"), "-append", "console=ttyAMA0 root=/dev/vda rw my_pc_smoke=1 panic=-1", "-drive", f"file={guest / 'rootfs.raw'},format=raw,if=virtio", "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0"]
            log = guest / f"boot-{boot}.log"
            with log.open("w") as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=360)
            content = log.read_text(errors="replace")
            print(content[-6000:])
            required = ["MYPC_LINUX_ARM64_BOOTED", "MYPC_LINUX_NETWORK_OK", "MYPC_LINUX_SMOKE_OK", "MYPC_LINUX_PERSISTENCE_WRITTEN" if boot == 1 else "MYPC_LINUX_PERSISTENCE_OK"]
            if result.returncode or "MYPC_LINUX_FAIL:" in content or any(marker not in content for marker in required):
                raise SystemExit(f"ARM Linux boot {boot} failed; inspect {log}")
    finally:
        server.shutdown()
print("PASS: two ARM64 Linux boots, guest-to-host networking, durable ext4 state, clean shutdown")
