#!/usr/bin/env python3
"""Validate the no-model RTL2.0c R2 ingress/context contract."""
from __future__ import annotations
import argparse
from pathlib import Path
from kvpress.rtl2_r2_ingress_delivery_context_manifest import load_manifest,validate_manifest
ROOT=Path(__file__).resolve().parents[1]
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--manifest",type=Path,default=ROOT/"analysis/rtl2_0c_r2_ingress_delivery_context_manifest.json",help="RTL2.0c R2 ingress/context manifest")
 a=p.parse_args();validate_manifest(load_manifest(a.manifest));print(f"RTL2.0c R2 ingress/context manifest passed: {a.manifest}");return 0
if __name__=="__main__":raise SystemExit(main())
