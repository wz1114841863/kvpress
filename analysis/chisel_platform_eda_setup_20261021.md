# Chisel platform on `dc-server` — 2026-10-21

This record covers only the user-owned Chisel toolchain setup. It does not
modify `/home/yaz80/wz_project/dc_project` or `vcs_project`, and it does not
claim RTL, synthesis, timing, area, power, or PPA closure.

## Installation

Remote host: `dc-server` (`ercesi413`, user `yaz80`). The reusable platform is
under:

```text
/home/yaz80/wz_project/chisel_platform/
  bin/chisel-sbt
  sbt-home/
  caches/coursier/
  caches/ivy2/
  toolchains/verilator/
  toolchains/verilator-src/
```

The current project workspace is separate:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/workspace/
```

The launcher accepts `CHISEL_PROJECT_ROOT` and optional overrides for the
platform root, Java, sbt launcher, Coursier/Ivy caches, and Verilator. The
platform is offline by design; dependencies were transferred from the local
cache rather than downloaded by the EDA server.

## Tool evidence

- Java: remote OpenJDK 11.0.19, glibc 2.27.
- sbt: 1.11.5; Scala: 2.13.18; project Chisel dependency: 7.15.0.
- Verilator: user-built 5.041 devel, compiled on the remote host with GCC
  7.5.0 and installed under `toolchains/verilator`.
- The local Ubuntu-24 Java 21 binary was not used: it requires GLIBC 2.33,
  2.34 and 2.38 symbols absent on the EDA server.

## Verification

1. `about` through the shared launcher: PASS.
2. `Test / compile` through the shared launcher: PASS; 12 main Scala sources
   and 67 test sources compiled in 31 seconds.
3. `testOnly kvpress.routea.DualMeasurementDutStructuralSpec`: the Verilator
   backend launched successfully. Two structural checks passed, while the
   elaboration test failed after 176 seconds because
   `FullKVMeasurementDut.scala` leaves the `RouteACoreSideArbiter`
   `direct_candidate_cancel` input and its ready/bit fields uninitialized.
   This is a source-level RTL connection failure, not a missing-platform or
   simulator failure, and is intentionally not changed by this setup batch.

The remote workspace was synchronized from local commit
`8fe1bba9ed28f12ff19950946018b95ba497bea6`, with the existing local working
tree changes preserved locally and without copying generated `build/` or
`target/` artifacts.

## Reuse boundary

The platform is ready for offline Chisel compilation and Verilator-backed tests
once project-level RTL elaboration errors are fixed. New projects should be
placed below `chisel_projects/<name>/workspace` and invoked with the shared
launcher; missing dependencies must be synchronized explicitly from a
networked development host or installed with administrator approval.
