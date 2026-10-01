# Run the Steam CPU and GPU tests

These instructions apply to a preview that includes the responsive diagnostic
runner. Preview 21 can stall at its first `sampling-idle` report; that report is
not a completed benchmark. Check the release notes and build number first.

1. Update the existing signed My-pc app, keeping its installed Linux disk.
   Restart My-pc, select Metal, enable JIT, and open Library → Apps → Steam ARM64.
2. Pause Steam downloads and close games. Leave Steam open for the first tests
   so its idle load is included. Do not reset the Linux installation.
3. Tap **Tests** in the desktop's bottom toolbar. The test buttons and progress
   controls stay fixed while results scroll. The settings page also has a fixed
   **Open CPU & GPU tests** button.
4. Run **Run CPU** first, then **Run GPU (FEX)** after the CPU test finishes.
   Keep My-pc in the foreground. Share the report for each completed or failed
   test with **Share test report**.

The percentage advances when samples or frames complete. Elapsed time and the
last Linux heartbeat are separate, so a percentage does not pretend that a
blocked operation completed. Starting the sampler, measuring idle activity,
launching a workload, compiling shaders and rendering frames are separate
stages. A sampler timeout marks CPU activity as unavailable and allows the
workload test to proceed. Each CPU phase has a 30-second deadline and each GPU
phase has a 60-second deadline. Stop test cancels only the diagnostic process
and its own children.

If a heartbeat stops, share the report even if there are no results. Include
whether the desktop and Steam still respond. A stopped diagnostic while Steam
responds is different from the whole virtual machine freezing. Avoid starting
another test while the app is still waiting for the previous cancellation.

## Reading the results

| Measurement | What it can tell us | Limitation |
|---|---|---|
| Native iOS vs ARM Linux, one worker | Cost of executing this integer workload inside QEMU | Swift/C compiler differences affect the comparison; this is not a CPU clock measurement |
| ARM Linux vs x86 through FEX | Additional translation cost for the same checksum-verified C workload | It does not measure every game or Steam CEF workload |
| One worker vs all guest cores | Whether parallel work increases measured throughput | Six virtual CPUs do not guarantee six fast physical cores or native CPU execution |
| Idle per-core busy/iowait, helper CPU, swap and available memory | CPU contention, storage waits or memory pressure while Steam is open | A timed-out sampler provides no measured activity result |
| ARM vs FEX GPU submission, finish and swap timings | Where this synchronized graphics workload spends time | GPU utilization and in-game FPS are not available |
| GPU renderer and exact shader pixel checks | Whether the tested path renders through virgl instead of a software fallback | It does not validate Vulkan, DirectX or Proton games |
| Display FPS and VM input acknowledgement | Frame delivery and host-to-VM input processing | These are separate from Steam's click-to-visible-response time |

The GPU test renders exact red, green and blue shader pixels, then 60 frames
with 16 draws per frame at 800×500. The bundled upstream FEX binaries are
unmodified and use an isolated diagnostic root. Tests do not read Steam
account files, export command lines or change Steam's FEX settings.

## Backbone Pro

Open session options to check the controller name and Linux acknowledgement,
then tap **Open Steam Big Picture**. Sticks, triggers, D-pad and standard
buttons are forwarded as a real Linux gamepad. Native My-pc panels temporarily
release guest input so controller navigation remains available in the app.
Rumble and Backbone-specific shortcut functions are not implemented. Physical
Backbone behavior must be checked on the device; hosted tests do not prove
every game's Steam Input mapping.
