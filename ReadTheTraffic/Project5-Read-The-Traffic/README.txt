Project 5 - Read the Traffic
Chapter 5: Network Services and the Watch on the Wire
Author: Srujana Challuri

WHAT THIS IS
------------
A per-host behavioral baseline detector for NetFlow logs. It learns what
"normal" looks like for each host from 30 days of baseline traffic, then scores
one suspicious live hour against each host's OWN baseline and reports anomalies
with a plain-English "why" for every flag.

FILES
-----
watchman.py         My detector (run this). Builds the per-host baseline,
                    detects beaconing / port_scan / exfil, prints the evidence
                    behind each flag, and runs a false-positive sweep.
baseline_flows.csv  30 days of "normal", distilled (ground truth).
window_flows.csv    One suspicious live hour. Three anomalies are hidden in it.
flow_baseline.py    The instructor's reference detector. I read it, then
                    reimplemented it in watchman.py with added explainability
                    (per-host destination/port profiles + behavioral
                    false-positive reasoning). Kept here to show provenance.
gpu_fabric_check.sh  Instructor's east-west GPU fabric prerequisite check
                    (Medium tier). Read-only.
REPORT.docx         Technical report for the record (findings + evidence).
MEMO.docx           Plain-language memo for the IT director (Hard tier).
AI_USAGE.txt        What I delegated to an AI copilot and what I verified by hand.

HOW TO RUN
----------
Requires Python 3.9+ (no third-party packages).

    python3 watchman.py baseline_flows.csv window_flows.csv

WHAT YOU SHOULD SEE
-------------------
1. A per-host baseline profile (p95 outbound bytes, known destinations, known
   ports) for each of the four hosts.
2. Three findings, each with a WHY line tied to a specific baseline deviation:
     - BEACONING  10.20.4.62 -> 203.0.113.77:8443  (fixed 300s interval, novel
       public destination the vLLM host never used = C2 check-in)
     - PORT_SCAN  10.20.4.77  fans out to 6 hosts on admin ports 22/3389/445 in
       1 second (host's baseline is a single host on 443)
     - EXFIL      10.20.4.45 -> 198.51.100.42  sends ~1.8 GB, ~750,000x its own
       2.4 KB p95 baseline
3. A false-positive sweep explaining why the baseline's git-pull and
   package-mirror traffic (public + periodic) is NOT flagged -- suppressed by
   behavior (known baseline destination), not by IP allow-listing.
