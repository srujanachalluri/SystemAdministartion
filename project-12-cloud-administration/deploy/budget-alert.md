# FinOps controls — configured BEFORE traffic

These were set in the provider billing console before a single billable request
was made. A control wired after the scary bill is a lesson learned the expensive
way.

CONFIRMED: yes

Provider          : OpenRouter (free tier, openai/gpt-oss-20b:free)
Monthly budget    : $25.00                   (board-approved ceiling for this project)
Alert threshold   : 80%  ($20.00)
Hard cap          : $0.00 per-key credit limit — set on the API key itself
Rate ceiling      : 20 requests/min, 50 requests/day (free tier, not adjustable)
Alert destination : ______________________   <-- fill in (email on the account)
Configured on     : ____-__-__               <-- fill in the date you set it
Screenshot        : docs/budget-alert.png    <-- key settings page showing the limit

## Why the hard cap is $0.00 and not $50

OpenRouter lets you set a credit limit on an individual API key. I set this key's
limit to $0.00. That is not a formality — it means the key is structurally
incapable of spending money. If I fat-finger a paid model ID, or a loop runs
away, or the key leaks, the request is refused rather than billed.

This is the strongest form of the control the chapter describes. A budget emails
you after the fact. A cap refuses the request. On a student project with no
revenue behind it, refusing is the correct default.

The $25 monthly budget above is the figure I would defend to the board if this
moved to paid models. It is documented here so the number exists BEFORE anyone
needs it, not after a surprise invoice.

## Why both a budget and a cap

A **budget** warns. It sends an email and then politely watches the meter keep
running. A **hard cap** stops. The organization was previously burned by a GPU
left running over a holiday weekend — the failure there was not a missing alert,
it was a missing stop. So both are wired, at different numbers: warn at $20
(80% of $25), stop at $50.

The $50 cap is deliberately above the $25 budget. The cap is a circuit breaker
for a runaway loop or a leaked key, not a second budget. If normal work trips the
cap, the budget was wrong and should be re-argued with the board — not silently
raised.

## Anomaly detection

`deploy/finops_alerts_gm.sh` is the daily warn half: it groups the cost export by
the `project` tag, projects month-end spend, and alerts at the 80% threshold.
Run it against the provider export once the bill lands:

    bash deploy/finops_alerts_gm.sh --budget 25 --threshold 0.8
