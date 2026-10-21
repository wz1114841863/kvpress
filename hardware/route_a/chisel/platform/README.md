# Shared EDA-server Chisel platform

This directory contains the reusable launcher used with the user-owned
`/home/yaz80/wz_project/chisel_platform` installation on `dc-server`.

The platform is offline by design.  It contains the sbt boot/global state and
the Coursier/Ivy dependency caches; it does not modify the existing
`dc_project` or `vcs_project` directories.  Projects are kept separately
under `/home/yaz80/wz_project/chisel_projects/`.

## Use

Copy this directory (or the launcher) into a project and run, on the EDA
server:

```bash
CHISEL_PROJECT_ROOT=/home/yaz80/wz_project/chisel_projects/<name>/workspace \
  /home/yaz80/wz_project/chisel_platform/bin/chisel-sbt 'Test / compile'
```

`CHISEL_PLATFORM_ROOT`, `JAVA_HOME`, `SBT_LAUNCH_JAR`, `SBT_HOME`, `IVY_HOME`,
and `COURSIER_CACHE` may be overridden for another user-owned installation.
The current installation was verified with Java 11.0.19, sbt 1.11.5, Scala
2.13.18, and Chisel 7.15.0. A user-local Verilator 5.041 build is installed
under `toolchains/verilator` and is exported automatically by the launcher
(the tool's `VERILATOR_ROOT` points at its `share/verilator` subdirectory).
Do not use the copied local Ubuntu-24 Java 21
binary on this Ubuntu-18/glibc-2.27 server; it requires newer GLIBC symbols.

No network access is required for the verified compile path.  If a future
project adds dependencies not present in the cache, sync the dependency cache
from a networked development host or obtain administrator approval for a
separate package installation; do not silently run remote package downloads.
