ThisBuild / organization := "org.kvpress"
ThisBuild / version := "0.1.0-SNAPSHOT"
ThisBuild / scalaVersion := "2.13.18"

val chiselVersion = "7.15.0"
val scalaTestVersion = "3.2.19"

lazy val root = (project in file("."))
  .settings(
    name := "kvpress-route-a-chisel",
    libraryDependencies ++= Seq(
      "org.chipsalliance" %% "chisel" % chiselVersion,
      "org.scalatest" %% "scalatest" % scalaTestVersion % Test,
    ),
    addCompilerPlugin(
      ("org.chipsalliance" % "chisel-plugin" % chiselVersion)
        .cross(CrossVersion.full),
    ),
    Test / parallelExecution := false,
  )
