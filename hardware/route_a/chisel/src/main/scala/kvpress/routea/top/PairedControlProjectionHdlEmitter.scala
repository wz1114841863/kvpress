package kvpress.routea.top

import circt.stage.ChiselStage
import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Path, Paths, StandardOpenOption}
import kvpress.routea.params.RouteASynthesisControlProjectionProfile

/**
  * Explicit HDL emitter for the approved bounded paired control profile.
  *
  * This is deliberately a generator-side utility rather than an implicit SBT
  * task: it has one named profile, one caller-supplied output directory, and
  * produces independent Full-KV and Route-A compilation units.  Each unit has
  * its own `.f` file because both emitted designs contain common module names;
  * combining them into one tool invocation would redefine those modules.
  *
  * The generated RTL is a pre-DC functional-control input only.  It selects
  * no macro, clock target, physical memory port, numeric implementation, or
  * external memory implementation.
  */
object PairedControlProjectionHdlEmitter {
  private final case class Emission(
      topName: String,
      fileName: String,
      renderSystemVerilog: () => String,
      renderChirrtl: () => String,
      requiredPortTokens: Seq[String],
      forbiddenModuleTokens: Seq[String],
  )

  private val profile = RouteASynthesisControlProjectionProfile

  private def emissions: Seq[Emission] = Seq(
    Emission(
      topName = "full_kv_control_projection",
      fileName = "full_kv_control_projection.sv",
      renderSystemVerilog = () => ChiselStage.emitSystemVerilog(
          FullKVControlProjectionGenerator.construct(profile.parameters),
        ),
      renderChirrtl = () => ChiselStage.emitCHIRRTL(
          FullKVControlProjectionGenerator.construct(profile.parameters),
        ),
      requiredPortTokens = Seq(
        "full_kv_read_work_in_valid",
        "external_core_mem_if_v1_request_valid",
        "full_kv_payload_read_req_in_valid",
        "full_kv_payload_read_rsp_out_valid",
        "full_kv_consumer_commit_in_valid",
        "attention_terminal_rsp_valid",
        "runtime_retire_req_valid",
        "session_retire_ack_valid",
      ),
      forbiddenModuleTokens = Seq("route_a_kv_subsystem_top"),
    ),
    Emission(
      topName = "route_a_control_projection",
      fileName = "route_a_control_projection.sv",
      renderSystemVerilog = () => ChiselStage.emitSystemVerilog(
          RouteAControlProjectionGenerator.construct(profile.parameters),
        ),
      renderChirrtl = () => ChiselStage.emitCHIRRTL(
          RouteAControlProjectionGenerator.construct(profile.parameters),
        ),
      requiredPortTokens = Seq(
        "external_core_mem_if_v1_request_valid",
        "functional_sidecar_work_out_valid",
        "functional_sidecar_payload_release_out_valid",
        "functional_sidecar_registry_allocate_in_valid",
        "functional_sidecar_read_issue_in_valid",
        "functional_partial_hot_offer_in_valid",
        "functional_partial_pending_offer_in_valid",
        "functional_partial_packed_offer_in_valid",
        "functional_r4_accepted_packet_out_valid",
        "functional_r4_merge_work_out_valid",
        "functional_r4_result_in_valid",
        "functional_r4_numeric_fault_in_valid",
        "attention_terminal_rsp_valid",
        "session_retire_ack_valid",
      ),
      forbiddenModuleTokens = Seq(
        "route_a_kv_subsystem_top",
        "route_a_functional_sidecar_delivery_adapter",
        "route_a_functional_partial_provider_boundary",
        "route_a_functional_r4_reference_boundary",
      ),
    ),
  )

  private def write(path: Path, content: String): Unit = {
    Files.write(
      path,
      content.getBytes(StandardCharsets.UTF_8),
      StandardOpenOption.CREATE,
      StandardOpenOption.TRUNCATE_EXISTING,
      StandardOpenOption.WRITE,
    )
  }

  private def jsonArray(values: Seq[String]): String =
    values.map(value => s"\"$value\"").mkString("[", ", ", "]")

  private def verify(emission: Emission, systemVerilog: String): Unit = {
    require(
      systemVerilog.contains(s"module ${emission.topName}"),
      s"missing expected top ${emission.topName}",
    )
    emission.requiredPortTokens.foreach { token =>
      require(systemVerilog.contains(token), s"missing typed top-level port token $token")
    }
    emission.forbiddenModuleTokens.foreach { token =>
      require(!systemVerilog.contains(s"module $token"), s"forbidden module emitted: $token")
    }
  }

  /** Emit selected independent HDL compilation units and their per-top filelists. */
  def emit(outputDirectory: Path, selectedTopNames: Set[String] = Set.empty): Unit = {
    Files.createDirectories(outputDirectory)
    val all = emissions
    val knownTopNames = all.map(_.topName).toSet
    require(
      selectedTopNames.isEmpty || selectedTopNames.subsetOf(knownTopNames),
      s"unknown projection selection: ${selectedTopNames.diff(knownTopNames).mkString(",")}",
    )
    val selected = if (selectedTopNames.isEmpty) all else all.filter(emission => selectedTopNames(emission.topName))
    // Render and write one projection at a time.  Apart from making progress
    // observable in a long full-profile lowering run, this preserves a valid
    // Full-KV artifact if a later, independent Route-A lowering fails.
    selected.foreach { emission =>
      println(s"HDL_EMIT_START top=${emission.topName}")
      val systemVerilog = emission.renderSystemVerilog()
      verify(emission, systemVerilog)
      write(outputDirectory.resolve(emission.fileName), systemVerilog)
      write(
        outputDirectory.resolve(s"${emission.topName}.f"),
        s"${emission.fileName}\n",
      )
      println(s"HDL_EMIT_DONE top=${emission.topName}")
    }
    val manifest = selected.map { emission =>
      s"""    {\n      \"top\": \"${emission.topName}\",\n      \"systemverilog\": \"${emission.fileName}\",\n      \"filelist\": \"${emission.topName}.f\",\n      \"required_port_tokens\": ${jsonArray(emission.requiredPortTokens)},\n      \"forbidden_module_tokens\": ${jsonArray(emission.forbiddenModuleTokens)}\n    }"""
    }.mkString("[\n", ",\n", "\n  ]")
    write(
      outputDirectory.resolve("paired_control_projection_emission_manifest.json"),
      s"""{\n  \"schema_version\": \"paired-control-projection-emission-v1\",\n  \"profile_id\": \"${profile.profileId}\",\n  \"tops\": $manifest\n}\n""",
    )
  }

  /**
    * Emits only pre-firtool CHIRRTL for one selected top. This is a diagnostic
    * recovery path for tool crashes: it neither substitutes a physical array
    * implementation nor changes the selected profile or production topology.
    */
  def emitChirrtl(outputDirectory: Path, topName: String): Unit = {
    val emission = emissions.find(_.topName == topName).getOrElse(
      throw new IllegalArgumentException(s"unknown projection selection: $topName"),
    )
    Files.createDirectories(outputDirectory)
    println(s"CHIRRTL_EMIT_START top=${emission.topName}")
    val chirrtl = emission.renderChirrtl()
    require(chirrtl.contains(s"module ${emission.topName}"), s"missing expected top ${emission.topName}")
    write(outputDirectory.resolve(s"${emission.topName}.fir"), chirrtl)
    println(s"CHIRRTL_EMIT_DONE top=${emission.topName}")
  }
}

/**
  * `runMain` entry point. Usage:
  *
  *   runMain kvpress.routea.top.EmitPairedControlProjectionHdl <output-dir> [full_kv_control_projection|route_a_control_projection]
  */
object EmitPairedControlProjectionHdl extends App {
  require(args.length == 1 || args.length == 2, "expected an output directory and optional top selection")
  PairedControlProjectionHdlEmitter.emit(Paths.get(args.head), args.drop(1).toSet)
}

/** `runMain` entry point for isolated pre-firtool diagnostics. */
object EmitControlProjectionChirrtl extends App {
  require(args.length == 2, "expected an output directory and exactly one top selection")
  PairedControlProjectionHdlEmitter.emitChirrtl(Paths.get(args.head), args(1))
}
