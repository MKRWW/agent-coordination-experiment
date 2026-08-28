# Do two agents ask what the other one knows?

Two instances of the same language model investigate one incident. Each sees
only half the evidence — one has the logs, the other has the config diff. The
actual cause follows only from both. They can talk to each other freely.

**Across 330 runs in 11 arms, they asked five times what the other side could
even see.**

The interesting part is not that they don't ask. It's that they know.

## The core finding: knowledge without action

Asked directly *before the first exchange* — with nothing but their own system
prompt in context — **85 % of agents correctly name the kind of source the
other side holds.** The log-side agent guesses configuration and change
history; the config-side agent guesses logs and metrics. Both are right before
a single word has been said.

Adding one sentence to both prompts — *"Your counterpart may have information
that is not available to you"* — raises spontaneous awareness of the asymmetry
from 10 % to 67 % (p < 0.0001).

Its effect on their behaviour in conversation: **zero.** Not one
knowledge-state question in 30 runs.

Give them a toolbox instead, and the same gap appears as a routing error: in
120 runs with tools they issued **370 data requests to an anonymous system that
never answers**, and asked the colleague holding that exact data **twice**.

## What does *not* change it

| Intervention | Effect on asking | Effect on solving |
|---|---|---|
| One sentence about the asymmetry | none (0/30) | 19/30 vs 15/30, p=0.43 |
| A role in the prompt ("developer" / "manager") | none | none |
| Corporate framing (reporting line, missed SLA, deadline) | none | none |
| A shared toolbox (6 tools incl. `escalate`, `meeting`) | none | none |
| An agent framework instead of plain HTTP | none | **worse**: 9/30 vs 19/30, p=0.0191, at 2.7× the tokens |

Role labels are the clearest null result here. Between the developer and
manager arms the prompts differ by six characters; the tool choice differs by
one call out of 283 (181 vs 182). `meeting` and `assign` — the two
organisational tools — are used twice in 60 runs by either role.

## What *does* change behaviour: the task

Adding a decision to make ("should v2.14.0 be rolled back?") is the only
intervention that moves anything. The organisational tools finally get used —
`assign` from 0 to 9 calls, `meeting` from 1 to 4 — **identically in both
roles.** The task drives behaviour, the role does not.

The price is the diagnosis: `both_correct` drops from 17/60 to 7/60
(p=0.0385). Of those 60 runs, 39 reach a *joint* decision. In most of them
neither side has identified the actual cause. They agree, quickly and without
friction, on a decision neither can ground.

## Method notes

Everything measured is reconstructible from the logs. Four points that
mattered more than the headline numbers:

**Isolation is verified, not asserted.** After every run a machine check
confirms that each history starts with its own system prompt, that the foreign
data block never appears in the opposite history, that every incoming `user`
turn is byte-identical to a message the other side sent, and that ground truth
never leaks. In the framework arm a recording proxy additionally checks the
prompts *actually sent to the model*. 330/330 runs passed.

**A solo control is mandatory.** The first scenario looked like successful
coordination at 9/10 — until a control showed one agent reached the answer
alone in 3/10 runs. A success rate without a solo baseline measures nothing.
The final scenario has each side holding exactly one indispensable piece
(solo: 0/30 and 3/30).

**A premature-final lock changed what was measured.** Without it the median run
was two turns long — "never asked" then partly meant "never talked". A `FINAL`
is only valid once the agent has received at least one message from the other
side.

**Several apparent findings were measurement artefacts.** A significant role
effect (p=0.0046) failed to replicate in four later arms. A collapse in
solution quality turned out to be a substring matcher missing "erhöhte das
Tax-Service-Timeout" — 34 of 270 runs changed classification once fixed; the
report now re-classifies from raw logs at read time rather than trusting
stored verdicts. Agents looping on the same tool call 15 times looked like
behaviour and was a missing turn limit. With 11 arms and a dozen metrics,
false positives are the base rate, not the exception.

**The heuristics are not the verdict.** Every classification is logged with the
plain-text sentence that triggered it. 20 % of the judge's source-attribution
verdicts were checked by hand (94.2 % agreement, all 14 disagreements
documented).

## Reproducing

Requires an OpenAI-compatible endpoint (vLLM or similar) on `localhost:8000`.
No agent framework, no LangChain — plain HTTP calls, because the scaffolding is
the variable under test.

```bash
# Baseline with the final lock
python3 run_config.py --scenario scenario_v3 --config v4 --out runs_v4 \
                      --final-lock --arm v4 --seed-range 2001 2030
python3 solo_check.py --scenario scenario_v3 --out runs_v3_solo30 --seed-range 2001 2030

# The one-sentence hint
python3 run_config.py --scenario scenario_v3_hint --config hinweis --out runs_hint \
                      --final-lock --arm hinweis --seed-range 2001 2030

# Roles, toolbox, corporate framing, decision task
python3 run_config.py --scenario scenario_v3_mgr_decide --config mgrdec \
                      --out runs_mgr_decide --final-lock --arm manager-entscheidung \
                      --seed-range 2001 2030

# The probes that separate representation from action
python3 apriori.py --scenario scenario_v3      --out posthoc/apriori_v3.jsonl
python3 apriori.py --scenario scenario_v3_hint --out posthoc/apriori_hint.jsonl

python3 aggregate.py    # rebuilds report.md from the raw logs
```

All raw runs are included (`runs_*/`, `judge/`, `posthoc/`) — the report is
generated from them, not written by hand.

## Layout

| Path | Purpose |
|---|---|
| `scenario*.py` | scenarios, roles, toolbox, ground truth, trap — swappable |
| `toolbox.py`, `corpcontext.py` | shared tool list and corporate framing, identical for both roles |
| `orchestrator.py` | isolation, turn loop, final lock, tool handling, metrics |
| `orchestrator_framework.py` | framework arm, same metrics |
| `framework_proxy.py` | forces sampling parity, records effective prompts and model calls |
| `metrics.py` | heuristics, outcome, consensus, corporate behaviour, tool and decision classification |
| `stats.py` | two-sided Fisher exact, no dependencies |
| `judge.py`, `judge_sample.py` | source attribution and the hand-check sample |
| `apriori.py`, `posthoc.py` | representation probes outside the conversation |
| `reclassify.py` | re-scores all runs after a classification fix |
| `aggregate.py` | builds `report.md` |

## Limitations

One model, one scenario, 30 runs per arm. Most differences between arms are
not significant, and this README says so where that is the case. Nothing here
says anything about models in general.

Model and framework names are replaced by neutral placeholders throughout,
including in the raw logs. The substitutions are purely lexical and change no
measured value. For interpretation: the model is a 27B open-weights model
served via vLLM at int4 quantisation; the framework arm used an established
open-source agent framework with tools and skills disabled — required for
isolation, so that arm measures a deliberately reduced framework.

The detailed report ([`report.md`](report.md)) is in German.

## License

MIT
