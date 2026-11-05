# SPEC — two ρ, and an actor that is a principal

**Status: Phase 1. Nothing here is built.** Approve or strike before a line is written, per prompt 9 of
the 18 September design review. §7 is the table of what needs deciding.

Everything in §1 was read off the code on 20 September 2026. **Five of the review's premises turned out
to be wrong**, and two of them change what Phase 2 has to build.

---

## §1 · What actually writes a ρ row today

ρ is the product — the share of act alerts a human answered, the number nobody can measure from orbit,
`ARCHITECTURE.md`'s "the brick nobody else has". It is also the least-defended number in the system.

### The writers, all five of them

| # | path | auth | `actor` becomes |
|---|---|---|---|
| 1 | `POST /actions` from inside the container | **none** — `_is_local` | whatever the body says |
| 2 | `POST /actions` from anywhere else | `ACT_TOKEN` or `ADMIN_TOKEN` | whatever the body says |
| 3 | MCP `act` (`app/agent.py`) | none — it posts to loopback | the `agent` argument |
| 4 | Telegram `/act` (`app/agent_loop.py`) | via 3 | `local-model/telegram` |
| 5 | LXMF `act <id>` (the bridge, fabcity/planetai-reticulum) | `ACT_TOKEN` | `lxmf:<source hash>` |
| 6 | `planetai act` (`bin/planetai`) | `ACT_TOKEN`/`ADMIN_TOKEN` | **`$(whoami)`** |

`actor` is free text, truncated at 80 characters, and `POST /actions` has *"deliberately no
one-action-per-alert cap"*. All of that is right for a household. None of it is right for an index other
cities are compared on.

### Five corrections to the review

**1. `POST /actions` is NOT open on the LAN.** The review says "on the LAN with no token (decided
open)". `_is_local` returns true only for `127.0.0.1`/`::1`, and its docstring says so on purpose:

> *"false for the browser on the machine hosting it, which arrives as the bridge gateway. That is
> deliberate rather than an oversight: on a node whose Docker forwards through a VM — Colima, Lima — a
> LAN client arrives as the gateway too, so trusting the bridge would trust the whole WiFi… Fail
> closed."*

So the decision that stands — and this spec records it rather than relitigating it — is **open on
loopback, token everywhere else.** The household's own browser is "everywhere else".

**2. There is no `gui` channel, because the dashboard cannot act.** The review's enum lists `gui`.
`app/static/dashboard.js` reads `asks.actions` to show which asks are answered and **never POSTs to
`/actions`**. A household looking at its own open asks has no way to answer one from the page it is
looking at. That is a product hole this spec surfaces; `gui` stays in the enum as the value that path
will use when it exists, and Phase 2 does not invent it.

**3. ρ today counts `acknowledged` as closure, and the rest of the node disagrees.** `app/index.py`'s
`rho()` counts `stage IN ('acknowledged','acted')`. `app/issues/schema.py` sets its
`CLOSED_STAGES` to `("acted", "measured")` and says why in a comment: an ask somebody merely *saw* would
otherwise read as acted on. **Two definitions of "closed the loop" in one node.** The review assumes ρ
is already "over `acted` rows"; it is not. §4 has to choose, and choosing changes the published number.

**4. `measured` can never be written.** `init.sql`'s CHECK allows `acknowledged|acted|measured`;
`POST /actions` refuses anything but the first two; `events` carries a `measured_at` column that no
child can ever fill. The fourth rung of detect→decide→deploy→measure has no writer.

**5. ρ_observed has no source.** The review says it comes "from the rules' `recovery:` blocks, as the
7 Sep decision". **There is no `recovery:` block in `config/rules.yml` or in any pack**, and no decision
record for the 7 September split exists in `docs/decisions/`. The second number is a name with nothing
behind it until §4 defines the block.

### And one more thing that does not exist

**The funnel was fixture-only.** `app/issues/engine.py::compute` never emitted `funnel`; the dashboard bound
`funnel: issues.funnel || null` and its tile therefore drew on a captured snapshot and never on a live
node. The review says "`/rho` returns both and the funnel" — the funnel was something to *build*.

**Built in v0.68** (`app/index.py::_funnel`, returned under `/rho`). Verified on node #1: 162 asked,
0 acknowledged, 30 acted, 5 measured, median detect-to-act 115 min.

---

## §2 · `actions.channel` — how the request arrived

```sql
ALTER TABLE actions ADD COLUMN IF NOT EXISTS channel TEXT;
```

Values: `lan` · `token` · `telegram` · `lxmf` · `mcp` · `gui` · `cli`.

**Set by the handler from how the request arrived, never from the body.** A body field would be a
claim; this is an observation, and it is the same rule PR #93 applies to a child's `node` name.

How each is decided, in `POST /actions` and nowhere else:

| value | the handler's test |
|---|---|
| `lan` | `_is_local(request)` and no `X-Agent` header — a shell in the container |
| `mcp` | `_is_local(request)` and an `X-Agent` header — `app/agent.py` |
| `telegram` | `X-Agent` ends `/telegram` |
| `lxmf` | `actor` matches `^lxmf:` **and** the request carried `ACT_TOKEN` |
| `cli` | `ACT_TOKEN`/`ADMIN_TOKEN` and `User-Agent: curl` from loopback |
| `token` | any other authenticated request — the honest default |
| `gui` | reserved; no writer until the page has one (§1.2) |

`cli` is added to the review's enum because `planetai act` exists and is the path a keeper actually
uses. A value the code cannot produce is worse than one it can.

## §3 · `actions.principal` — who, without naming a person

```sql
ALTER TABLE actions ADD COLUMN IF NOT EXISTS principal TEXT;
ALTER TABLE actions ADD COLUMN IF NOT EXISTS model_recorded BOOLEAN NOT NULL DEFAULT FALSE;
```

Derived by the handler, never posted. **It must be stable enough to count distinct answerers and never
enough to name one**, which is the same refusal `docs/SPEC_custody.md §4` makes about what an event may
carry.

| channel | `principal` |
|---|---|
| `lan`, `cli` | `local` — a shell on the node is the household; `$(whoami)` does **not** travel |
| `token` | the token's role: `act` or `admin`, never the token |
| `telegram` | `tg:` + first 12 hex of `sha256(chat_id + NODE_NAME)` |
| `lxmf` | `lxmf:` + first 12 hex of the source hash (already a hash; truncated for symmetry) |
| `mcp` | the `X-Agent` value, which is a name the operator chose, plus `model_recorded = TRUE` |

**`$(whoami)` stops reaching the database.** `bin/planetai`'s `cmd_act` puts a Unix login name into
`actor` today; on a personal machine that is a person's name, and `actor` is not redacted anywhere.
`actor` stays as the free-text field a household may write what it likes in — it never leaves the node
— and `principal` is the field the Index and the parent may see.

**The chat id is salted with the node name** so the same hash cannot be correlated across two nodes.

### The note rule, which is the point of the whole section

**A row with `model_recorded = TRUE` and no human message is refused, 400.**

Today `app/agent.py::act` is declared `def act(alert_id: int, note: str = "acted", agent: str = "agent")`
— **`note` has a default**, so a model can record that a human acted while carrying none of the human's
words. That is a model writing the product's headline number about a conversation it may have had with
itself.

So: when `model_recorded` is true, `note` must be present, must not be one of the placeholders the
code ships today (`acted`, `acted (via reticulum)`, empty), and is stored verbatim. `app/agent.py` loses
the default and the tool's docstring says the human's words are required. `app/agent_loop.py`'s
Telegram path passes the message through — it already has it in `parts[2]` and already falls back to
`"acted"`, which this forbids.

**Not refused:** a human on any channel recording with no note. A person typing `planetai act 12` is
present and says so by being there. Only a model asserting a human's action needs the human's words.

---

## §4 · Two published numbers

### ρ_reported — as today, with one decision to make

The funnel over the `actions` ledger. **§1.3 is the decision:** today's query counts
`acknowledged` as closure and `app/issues/` does not.

**Recommend: ρ_reported counts `acted` and `measured` only**, matching `CLOSED_STAGES`, because "the
share of act alerts a human *answered*" is what the Index is told the number means and seeing an alert
is not answering it. **This lowers the published number on every node**, which is the right direction
for a number that has been counting glances, and it must be said in the CHANGELOG in those words.

Striking this keeps today's definition and the two halves of the node keep disagreeing.

### `measured` is derived from rule silence, and that is not ρ_observed

The funnel's fourth stage had a worse problem than a missing source: **nothing could write it.**
`POST /actions` accepts `acknowledged` and `acted` only (`app/main.py::post_action`), so a stage the
schema documents and the page was to draw was structurally zero on every node that has ever run.

It is now derived, not posted. `run_rules` re-raises an alert the moment its cooldown expires and the
condition still holds, so an act followed by `index.MEASURED_WINDOW_MIN` of silence *from a rule the node
still evaluates* is that condition having stopped being true. No household is asked to learn a habit and
the answer is retroactive: node #1 read 5 of 30 on the day it shipped, having never recorded one.

**Two guards, because the naive version lies.** The window (2880 min) must outlast the slowest act-level
cooldown or a rule merely waiting its turn is called cleared — `tests/test_share.py` fails if a pack adds
a slower one. And only live rule ids count: a retired rule cannot fire whatever anyone does, so its
silence is not evidence. Without that second guard node #1 read **8**, three of them free — two
`_test/hello-<epoch>` alerts and one `indoor_pm25_high` from before pack ids were namespaced.

**This is not ρ_observed and does not displace it.** It answers *whether* the condition stopped holding,
never *when* — the proof is a window, so `latency_minutes.measured` is `null` on purpose and a median of
window-ends would be a constant 48h dressed as a measurement. ρ_observed below asks a sharper question a
rule has to declare: the metric came back under a named threshold inside a named time. When a pack writes
its first `recovery:` block the two stand side by side — the declared one sharper and narrower, this one
answering on every rule from day one. Neither is the other's estimate.

### ρ_observed — and the block it needs first

The review defines it from the rules' `recovery:` blocks. §1.5: no such block exists. So this spec has
to define it, and this is the largest piece of Phase 2:

```yaml
# in a pack's rules.yml, beside the rule that raises the alert
- id: pm25_act
  ...
  recovery:
    within: PT6H        # how long after the alert the condition has to have stopped holding
    sql: |              # returns one row when it has; the rule's own metric, its own threshold
      SELECT 1 FROM stats WHERE metric='pm25' AND mean_1h < 35 AND ...
```

ρ_observed is then: of the act-level alerts raised in the window whose rule carries a `recovery:` block,
the share whose block returned a row inside `within`. **It measures the place, not the ledger** — it
needs no human to type anything, which is exactly why it is worth having beside a number that does.

**Its denominator is not ρ_reported's.** Only rules with a `recovery:` block count, and on the day this
ships that is zero rules. ρ_observed is `null` until a pack writes one, and a `null` that says "no rule
has declared what recovery looks like" is honest; a `0.0` would not be.

### Both, published

Two `fci-cells-v0` rows under `Governance|<scale>`, distinguished by `unit`:

```
unit: "rho_reported — share of act alerts a person answered within 24h (30d)"
unit: "rho_observed — share of act alerts whose condition recovered within the rule's window (30d)"
```

`GET /rho` returns `{reported: {...}, observed: {...}, funnel: {...}}` — and **the funnel has to be
built** (§1.6), as the four stages detect→decide→deploy→measure with counts, which is what the
dashboard's existing tile already expects to be handed.

**The report gains a ρ sentence, which it does not have today.** `app/report.py` puts
`b["rho"]` in the bundle and no template ever renders it. The sentence names both numbers **when they
differ by more than 0.15 absolute**, and otherwise names ρ_reported alone — because two numbers in a
household's morning message need a reason to both be there.

---

## §5 · What does not change

- **`POST /actions` stays open on loopback and token-gated elsewhere.** The decision stands; the row
  now says so in `channel` instead of leaving it to be inferred. Not reopened here.
- **No one-action-per-alert cap.** Two people who both acted are both recording something true.
- **`actor` stays free text and stays on the node.** Nothing about what a household writes changes.
- **The `events` push gains `channel` and nothing else.** No principal, no actor, no note — the refusal
  in `docs/SPEC_custody.md §4` holds: timestamps carry everything ρ needs and none of the facts a
  household would mind travelling. A parent learns that a district's answers came by radio rather than
  by app; it does not learn whose radio.
- **`fci-cells-v0`'s row shape.** Two rows, same seven (or eight) fields, distinguished by `unit`.

---

## §6 · The tests

`tests/test_rho.py` — a new suite, so `tests/all`'s count moves (NEXT_RELEASE rule 1; PR #95 also moves
it, and the two must not merge in the same hour).

1. one row per channel, each with the expected `principal`, asserted against the handler and not a copy
2. `$(whoami)` posted as `actor` does not appear in `principal`
3. the same Telegram chat id gives a different `principal` on two different `NODE_NAME`s
4. a model `act` with no `note`, and with each shipped placeholder, is **refused 400**
5. a model `act` with a human's message is accepted and stores it verbatim
6. a human `act` with no note is accepted
7. both cells present and distinct on a fixture where the two numbers differ
8. ρ_observed is `null`, not `0.0`, when no rule declares a `recovery:` block
9. `events` rows carry `channel` and carry no `principal`, `actor` or `note`

Each of 2, 4 and 9 written **failing first**, the way `tests/test_custody.py` records at its head.
`tests/test_custody.py` and `tests/test_logic.py` are not modified and must stay green.

---

## §7 · What Tomas is being asked

| § | the call | if struck |
|---|---|---|
| 1.1 | record `/actions` as **loopback-open, token elsewhere** — the review's "open on the LAN" is not what the code does | re-open a decision this spec was told not to re-open |
| 4 | **ρ_reported counts `acted`+`measured`, not `acknowledged`** — this *lowers* every node's published number | keep today's query, and keep two definitions of "closed" in one node |
| 4 | ρ_observed is **`null` until a rule declares `recovery:`**, not `0.0` | publish a zero that means "nobody wrote a rule" |
| 4 | the report names both only when they differ by **> 0.15** | name both always, or never |
| 3 | `principal` is derived and hashed; `$(whoami)` stops travelling | leave a Unix login name in a column that reaches a parent |
| 2 | `cli` added to the channel enum; `gui` reserved with no writer | an enum that does not match the code |

**And one thing that is a product decision, not a spec one:** the dashboard cannot close a loop (§1.2).
Every other surface can. If ρ is the product, the page the household actually looks at is the strangest
place for it to be unanswerable — but adding a button is an `app/static/*` change under
`docs/NEXT_RELEASE.md` rule 2 and belongs in its own release.

**Phase 2 begins on "go", not before.**
