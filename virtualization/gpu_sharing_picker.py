#!/usr/bin/env python3
"""gpu_sharing_picker.py — recommend a GPU-sharing mode for a workload.

System Administration and Maintenance, Chapter 6 reference tool. The point is NOT to trust the output blindly —
it encodes the chapter's decision rules so you can argue with them. The administrator
owns the verdict; this just drafts it.

Modes, in increasing isolation:
  time-slicing  : no memory/fault isolation. Bursty dev/notebooks only.
  mps           : soft compute/memory caps; one fatal fault can reset for all clients.
  mig           : true hardware fault + performance isolation. Multi-tenant prod.
  vgpu          : licensed; full VMs share a GPU (VDI / mixed estates).
  passthrough   : one whole GPU to one VM, near-bare-metal. Training / latency-critical.

Usage:
  python gpu_sharing_picker.py --vram-needed 18 --tenants 4 --isolation strict --kind inference
"""
import argparse

def recommend(vram_needed_gb, tenants, isolation, kind, gpu_vram_gb=80):
    reasons = []
    # One tenant that wants the whole card, or training/latency-critical -> passthrough.
    if tenants == 1 and (kind == "training" or vram_needed_gb > gpu_vram_gb * 0.6):
        return "passthrough", ["single tenant wants near-bare-metal throughput",
                               "no sharing benefit; VFIO overhead is low single-digit %"]
    # Hard multi-tenant isolation (e.g. different customers / PII) -> MIG.
    if tenants > 1 and isolation == "strict":
        if vram_needed_gb > gpu_vram_gb / 2:
            reasons.append("WARNING: per-tenant VRAM may exceed the largest MIG slice; "
                           "check the profile table (max 7 slices, even on a 180GB B200)")
        return "mig", reasons + ["multi-tenant with strict isolation needs hardware fault isolation",
                                 "MIG gives each tenant a walled-off slice"]
    # VMs (not containers) needing to share one card -> vGPU.
    if isolation == "vm":
        return "vgpu", ["workloads are full VMs sharing one GPU (e.g. VDI)",
                        "requires NVIDIA vGPU licensing + SR-IOV in BIOS on Ampere+"]
    # Many cooperative inference processes, soft caps acceptable -> MPS.
    if kind == "inference" and tenants > 1 and isolation == "soft":
        return "mps", ["cooperative same-trust inference processes, latency-sensitive",
                       "accept that one fatal fault can reset the GPU for all clients"]
    # Bursty dev, isolation not required -> time-slicing.
    return "time-slicing", ["bursty/dev workload, no isolation requirement",
                            "cheapest to set up; oversubscribe and hope for non-overlap"]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--vram-needed", type=float, required=True, help="GB per tenant")
    p.add_argument("--tenants", type=int, required=True)
    p.add_argument("--isolation", choices=["none", "soft", "strict", "vm"], default="soft")
    p.add_argument("--kind", choices=["inference", "training", "dev"], default="inference")
    p.add_argument("--gpu-vram", type=float, default=80.0)
    a = p.parse_args()
    mode, why = recommend(a.vram_needed, a.tenants, a.isolation, a.kind, a.gpu_vram)
    print(f"Recommended sharing mode: {mode}")
    for r in why:
        print(f"  - {r}")
    print("\nReminder: this is a draft. You own the verdict. Verify against the GPU's "
          "-lgip profile table and your real isolation/compliance requirements.")
