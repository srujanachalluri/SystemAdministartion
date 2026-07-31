# Rep 4 — Detect drift with a dry run

Playbook: `ansible/site.yml` (five tasks — directory, package, config contents,
file mode, absent override marker).

## Commands

```bash
# 1. Converge: bring the host to baseline for real
ansible-playbook -i ansible/inventory.ini ansible/site.yml

# 2. Confirm clean: a dry run right after convergence should report zero changes
ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff

# 3. Introduce drift by hand (this is what a 2 a.m. hotfix looks like)
echo "temperature=1.0" >> /tmp/rep4-demo/inference.conf
chmod 666 /tmp/rep4-demo/inference.conf
touch /tmp/rep4-demo/UNMANAGED_OVERRIDE

# 4. Detect: dry run reports the drift WITHOUT fixing it
ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff
```

## Output — Step 2 (clean baseline)

<!-- paste output here -->

```
PLAY RECAP
localhost : ok=5  changed=0  unreachable=0  failed=0
```

## Output — Step 4 (drift detected)

<!-- paste output here -->

```
TASK [3. Ensure the inference config has exactly these contents]
--- before: /tmp/rep4-demo/inference.conf
+++ after: /tmp/rep4-demo/inference.conf
@@ -1,5 +1,5 @@
 # managed by ansible - do not edit by hand
 max_tokens=1024
 temperature=0.2
 model_alias=@champion
 log_level=info
-temperature=1.0
changed: [localhost]

TASK [4. Ensure the config file is not world-writable]
--- before
+++ after
@@ -1,2 +1,2 @@
-mode: '0666'
+mode: '0644'
changed: [localhost]

TASK [5. Ensure the drift marker file is absent]
changed: [localhost]

PLAY RECAP
localhost : ok=5  changed=3  unreachable=0  failed=0
```

## Explaining every line of the diff

**`--- before` / `+++ after`** — standard unified-diff headers. `before` is the
state Ansible *found on disk*; `after` is the state the playbook *would write*.
Read them as "reality" and "intent."

**`@@ -1,5 +1,5 @@`** — the hunk header: this chunk covers 5 lines starting at
line 1 in the before-file and 5 lines starting at line 1 in the after-file.

**Unprefixed lines** (`max_tokens=1024`, `model_alias=@champion`, …) — context.
These already match the baseline. They are printed so I can see *where* the change
sits, not because anything happens to them.

**`-temperature=1.0`** — the minus means this line exists in reality but not in
intent. Somebody appended `temperature=1.0` to the file after the last converge.
This is the drift. Note what it actually does: the file now has `temperature=0.2`
on line 3 and `temperature=1.0` on line 6, and most config parsers take
last-wins — so this host is silently serving at a completely different sampling
temperature than every other host in the fleet. Nothing is down. Nothing alerts.
The model just behaves differently here.

**`-mode: '0666'` / `+mode: '0644'`** — the file's permission bits drifted to
world-writable. Ansible reports it as a diff on the mode attribute rather than on
content, because task 4 declares intent about metadata, not text.

**`changed: [localhost]`** — in a normal run this means "I changed it." Under
`--check` it means **"I *would* change it"**. Nothing was written. This is the
single most important line to read correctly.

**`changed=3` in the PLAY RECAP** — three of five tasks disagree with reality:
the config contents, the file mode, and the presence of `UNMANAGED_OVERRIDE`. The
other two (`ok`, not `changed`) are already correct. So the recap is a drift
counter: `changed=0` under `--check` means the host matches its baseline;
anything above zero is the size of the delta.

## Reflection — why `--check` is the right default for *detecting* drift

Because detection and remediation are two different decisions, and collapsing them
into one command takes the decision away from me.

A dry run answers "what is different?" A real run answers "what is different, and
also I already overwrote it." Those look similar right up until the drift turns out
to be someone's deliberate emergency fix. In the diff above, `temperature=1.0` might
be a careless edit — or it might be the on-call engineer's mitigation for a
degenerate-output incident at 3 a.m. that nobody has written up yet. A plain
`ansible-playbook` run reverts it instantly and silently, and the incident comes
back with no obvious cause and one more layer of confusion. `--check --diff` puts
the evidence in front of a human first: here is the delta, now decide whether the
baseline is right or the reality is right.

Sometimes reality is right. When it is, the fix is to change `site.yml`, not to
stamp over the host — and only a dry run gives me the chance to notice that.

There is also a scale argument. `--check` is safe to run everywhere, all the time,
across the whole fleet, on a schedule, as a nightly job. Because it cannot mutate
anything, it needs no change window, no approval, and no rollback plan, so it can
be *routine*. Remediation can never be routine in that way — it is a change, and
changes get records, windows, and signatures (see `rep03-change-record.md`). The
practical shape of maintenance is therefore: continuous cheap detection, deliberate
gated remediation. `--check` is what makes the first half of that possible.

Finally, `--check --diff` output is evidence. `changed=0` on a scheduled dry run is
a dated, reproducible statement that a host matched its declared baseline at a
point in time — which is exactly what an auditor wants and exactly what "the server
looked fine to me" is not.

**One environment note:** task 2 (the package check) runs with `check_mode: true`
and `ignore_errors: true`, because inside an unprivileged dev container the package
manager cannot be queried without root. Ansible prints `...ignoring` for that task.
That is expected, and it is itself a small lesson: a baseline check is only as good
as its access to the thing it is checking. On a real host this task runs with
`become: true` and reports honestly.

**Limits I should state honestly:** a dry run only detects drift in things the
playbook actually declares. My five tasks say nothing about kernel version,
firewall rules, or which model alias the registry resolves to — so `changed=0` means
"no drift in what I check," never "no drift." Some modules also can't fully predict
their result in check mode (anything gated behind a task that would have run
first), so a clean check is a strong signal, not a proof.
