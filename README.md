# Do two agents ask what the other one knows?

Two instances of the same language model investigate one incident. Each sees
only half the evidence — one has the logs, the other has the config diff. The
actual cause follows only from both. They can talk to each other freely.

**In 90 runs they asked five times what the other side could even see.**

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

Its effect on their behaviour in conversation: **zero.** Not one knowledge-state
question in 30 runs.

The model knows its counterpart sees something different. It can say what. And
it still doesn't ask when it matters. Representation and action are decoupled.

## Results

Three arms, 30 runs each, identical seeds (2001–2030), identical sampling.

| | v4 | Hint | Framework |
|---|---|---|---|
| runs with ≥1 knowledge-state question | 3/30 | **0/30** | 2/30 |
| both agents correct | 11/30 | 17/30 | 8/30 |
| trap triggered | 11/30 | 7/30 | 17/30 |
| contradictions ignored | 7/8 | 4/9 | 9/11 |
| total tokens per run (median) | 3132 | 3360 | 8471 |

Pairwise Fisher exact tests are in [`report.md`](report.md). No pair differs
significantly on the knowledge-state question. The only significant difference
in the entire experiment is that the framework arm performs *worse* than the
hint arm (p = 0.0352) while consuming 2.7× the tokens.

What the agents do instead of asking: they fill the gap. A judge pass over all
1211 factual claims found 8 % with a broken source relation — invented,
misattributed, or applied to the wrong context. And when a statement from the
other side contradicts their own data, it is silently passed over in 20 of 28
cases. Exactly one contradiction leads to a follow-up question.

## Method notes

Everything measured is reconstructible from the logs. Three points that
mattered more than the headline numbers:

**Isolation is verified, not asserted.** After every run a machine check
confirms that each history starts with its own system prompt, that the foreign
data block never appears in the opposite history, that every incoming `user`
turn is byte-identical to a message the other side sent (no prefix, no speaker
label), and that ground truth never leaks into either history. In the framework
arm a second layer checks the prompts *actually sent to the model* via a
recording proxy. 90/90 runs passed.

**A solo control is mandatory.** The first scenario looked like successful
coordination at 9/10 — until a control condition showed one agent reached the
answer alone in 3/10 runs, because its data set contained half the cause. A
success rate without a solo baseline measures nothing. The final scenario has
each side holding exactly one indispensable piece (solo: 0/30 and 3/30).

**A premature-final lock changed what was measured.** Without it the median run
was two turns long, sometimes with a verdict in turn one — "never asked" then
partly meant "never talked". A `FINAL` is now only valid once the agent has
received at least one message from the other side; a premature one is rejected
and the run continues.

**The heuristics are not the verdict.** Every classification is logged together
with the plain-text sentence that triggered it. 20 % of the judge's verdicts
were checked by hand (94.2 % agreement, all 14 disagreements documented with
the judge's failure patterns).

## Reproducing

Requires an OpenAI-compatible endpoint (vLLM or similar) on `localhost:8000`.
No agent framework, no LangChain — plain HTTP calls, because the scaffolding is
the variable under test and must not come from a library.

```bash
# Arm 1 — baseline with the final lock
python3 run_config.py --scenario scenario_v3 --config v4 --out runs_v4 \
                      --final-lock --arm v4 --seed-range 2001 2030
python3 solo_check.py --scenario scenario_v3 --out runs_v3_solo30 --seed-range 2001 2030

# Arm 2 — identical, plus one sentence in both system prompts
python3 run_config.py --scenario scenario_v3_hint --config hinweis --out runs_hint \
                      --final-lock --arm hinweis --seed-range 2001 2030

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
| `scenario*.py` | scenarios, ground truth, trap — swappable |
| `orchestrator.py` | isolation, turn loop, final lock, metrics |
| `orchestrator_framework.py` | framework arm, same metrics |
| `framework_proxy.py` | forces sampling parity, records effective prompts and model calls |
| `metrics.py` | heuristics, outcome and consensus classification |
| `stats.py` | two-sided Fisher exact, no dependencies |
| `judge.py`, `judge_sample.py` | source attribution and the hand-check sample |
| `apriori.py`, `posthoc.py` | representation probes outside the conversation |
| `aggregate.py` | builds `report.md` |

## Limitations

One model, one scenario, n=30 per arm. The hint arm's higher solve rate
(17/30 vs 11/30) is **not** significant (p = 0.1954) — at this sample size it
does not carry. Nothing here says anything about models in general.

Model and framework names are replaced by neutral placeholders throughout,
including in the raw logs. The substitutions are purely lexical and change no
measured value. For interpretation: the model is a 27B open-weights model
served via vLLM at int4 quantisation; the framework arm used an established
open-source agent framework with tools and skills disabled — disabling them was
required for isolation, so that arm measures a deliberately reduced framework.

The detailed report ([`report.md`](report.md)) is in German.

## License

MIT
