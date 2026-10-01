from pathlib import Path

core = Path("FEX/FEXCore/Source/Interface/Core/Core.cpp")
s = core.read_text()
reporter_start = "  /* iOS-Madeira ml316: report ExitToX64 FFS bypasses"
reporter_end = "  /* iOS-Madeira: refuse to compile obviously-invalid guest RIPs."
start = s.find(reporter_start)
if start == -1:
    raise SystemExit("FEX iOS diagnostic reporter start marker not found")
end = s.find(reporter_end, start)
if end == -1:
    raise SystemExit("FEX iOS diagnostic reporter end marker not found")
s = s[:start] + s[end:]
if "const uint64_t FfsCount = IosFfsBypassLog[0]" in s or "const uint64_t CBCount = IosCbEntryLog[6]" in s:
    raise SystemExit("FEX iOS diagnostic reporters remain after cleanup")
core.write_text(s)

arm = Path("FEX/FEXCore/Source/Utils/ArchHelpers/Arm64.cpp")
s = arm.read_text()
start = s.find("  MEMORY_BASIC_INFORMATION mbi {};")
if start != -1:
    end_marker = "mbi.Protect, type, mbi.State);"
    end = s.find(end_marker, start)
    if end == -1:
        raise SystemExit("Arm64 CASPAL diagnostic end marker not found")
    new = """  LogMan::Msg::EFmt("[caspal128] MISALIGNED-UNSUPPORTED Size={} addrReg=x{} addr={:#x} misalign={} ",
                  Size, AddressReg, GPRs[AddressReg], GPRs[AddressReg] & 15);"""
    arm.write_text(s[:start] + new + s[end + len(end_marker):])
