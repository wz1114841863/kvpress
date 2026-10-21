# Chisel platform handoff for offline EDA-server use

This document is standalone handoff material for reusing the Chisel
environment on the EDA server or for handing the setup to another project
owner. It describes a user-space toolchain only; it is not a synthesis, timing,
area, power, or PPA result.

## 1. What is installed

On `dc-server` (`ercesi413`, user `yaz80`), the platform is installed at:

```text
/home/yaz80/wz_project/chisel_platform/
  bin/chisel-sbt                 # shared launcher
  sbt-home/                      # sbt boot/global state
  caches/coursier/               # transferred dependency cache (~2.9 GB)
  caches/ivy2/                   # user-local Ivy area
  toolchains/verilator/          # user-built Verilator installation
  toolchains/verilator-src/      # source/build tree for that installation
```

Projects must remain separate from the platform, for example:

```text
/home/yaz80/wz_project/chisel_projects/<project>/workspace/
```

The setup does not modify the existing `/home/yaz80/wz_project/dc_project` or
`vcs_project` directories.

## 2. Toolchain compatibility

The verified versions are:

| Component | Version/evidence |
| --- | --- |
| Java | OpenJDK 11.0.19 on the EDA server |
| sbt | 1.11.5 |
| Scala | 2.13.18 |
| Chisel | 7.15.0 (project dependency) |
| Verilator | 5.041 devel, compiled on the EDA server with GCC 7.5.0 |
| Host ABI | Ubuntu 18 / glibc 2.27 |

The local Ubuntu-24 Java 21 binary must not be copied to this server: it
requires newer GLIBC symbols. Java 11 is sufficient for the verified sbt and
Chisel compile path.

## 3. Project invocation

Use the shared launcher rather than invoking a system sbt installation:

```bash
CHISEL_PROJECT_ROOT=/home/yaz80/wz_project/chisel_projects/<project>/workspace \
  /home/yaz80/wz_project/chisel_platform/bin/chisel-sbt 'Test / compile'
```

For a directed test:

```bash
CHISEL_PROJECT_ROOT=/home/yaz80/wz_project/chisel_projects/<project>/workspace \
  /home/yaz80/wz_project/chisel_platform/bin/chisel-sbt \
  'testOnly example.package.MySpec'
```

The launcher configures sbt boot/global state, Coursier and Ivy caches, and
exports the user-local Verilator installation. It supports overrides through
`CHISEL_PLATFORM_ROOT`, `JAVA_HOME`, `SBT_LAUNCH_JAR`, `SBT_HOME`, `IVY_HOME`,
`COURSIER_CACHE`, `VERILATOR_INSTALL`, and `VERILATOR_ROOT`.

## 4. Synchronizing another project

From a networked development host, copy source only into a separate project
workspace. Do not copy generated `target/` or `build/` trees:

```bash
rsync -a \
  --exclude='.git' --exclude='target' --exclude='build' \
  --exclude='*.log' --exclude='*.vcd' \
  <local-project>/ \
  dc-server:/home/yaz80/wz_project/chisel_projects/<project>/workspace/
```

Dependency caches are intentionally offline on the EDA server. If a project
needs an uncached dependency, synchronize the required cache from a networked
host or obtain administrator approval; do not silently run remote package
downloads.

Before a measured run, record the source commit and any working-tree diff (or
use a clean checkout). The platform does not make a dirty source tree
reproducible by itself.

## 5. Verification performed for this handoff

For the KVzap Chisel workspace:

1. `about` through the shared launcher: passed.
2. `Test / compile`: passed; 12 main Scala sources and 67 test sources
   compiled in 31 seconds.
3. `DualMeasurementDutStructuralSpec`: Verilator launched successfully. Two
   structural checks passed. The DUT elaboration test failed because the
   current `FullKVMeasurementDut.scala` does not initialize the
   `RouteACoreSideArbiter` `direct_candidate_cancel` input and related fields.
   This is an RTL connection issue, not a platform installation failure.

The platform is therefore ready for offline Chisel compilation and
Verilator-backed tests, subject to each project's own RTL correctness.

## 6. Current KVzap experiment distinction

The local session `kvzap-mr1b-b2c-p2a-fix` is not the same test as the remote
structural test above. Its durable log is
`analysis/experiments/mr1b_b2c_p2a_fix.log` and records:

- `RouteAMeasurementDutR3Spec`: 4 tests run, 4 passed;
- exit code 0;
- elapsed time 40 minutes 10 seconds;
- the four tests include the pre-issue direct-candidate cancellation and
  R6-owned fault-terminal case.

That result was produced locally with Java 21. The remote run was a separate
platform smoke/structural check and must not be substituted for the local
MR-1B regression.
