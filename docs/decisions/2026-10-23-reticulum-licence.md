# Reticulum's licence, read against the node

**Read 23 October 2026.** The bridge has installed `rns` and `lxmf` since v0.8 (4 September 2026) and nobody had read
their licence for the node. SPEC_fablab §7 (branch `lab-services-2026-10-23`) now points lab and community nodes at
Reticulum for discovery and parent links, so it was read before that goes further. This record pins both packages
and says what the licence means for each use. Tomas decided the four open questions the same day; they are at the end.

## What the node does with Reticulum

All of it is in one optional container, compose profile `reticulum`, off until an operator runs `planetai reticulum`.
Node #1 runs it.

- `app/Dockerfile.reticulum` installs `rns`, `lxmf` and `httpx` from PyPI. The image is built on the operator's
  machine. Fab City publishes no image, and the release tarball holds only the Dockerfile and the bridge.
- `app/reticulum_bridge.py` imports `RNS` and `LXMF` and does three things: an LXMF address that sends `act`-level
  alerts out, an inbox where `act <id> [note]` becomes a row in `actions`, and, with `RETICULUM_PRESENCE=1`, a
  `planetai.presence` announce carrying the node's name, a coarse H3 cell, its version and kind. Peers it hears are
  kept in the container's `/data` and shown on the Network tab.
- `docs/NETWORKING.md` and `docs/site/channels.md` describe the same three. `docs/SPEC_discovery.md` §6 plans to merge
  radio and tailnet peers into one list. `docs/SPEC_identity.md` borrows the bridge's volume pattern for the node key
  and sends nothing over Reticulum.

## The licence

`rns` and `lxmf` carry the same text, the Reticulum License. Only the copyright lines differ (2016–2026 for
Reticulum, 2020–2025 for LXMF). It is the MIT licence with two conditions added before the notice condition:

> - The Software shall not be used in any kind of system which includes amongst
>   its functions the ability to purposefully do harm to human beings.
>
> - The Software shall not be used, directly or indirectly, in the creation of
>   an artificial intelligence, machine learning or language model training
>   dataset, including but not limited to any use that contributes to the
>   training or development of such a model or algorithm.

Full text at the pinned tags: [Reticulum 1.5.4](https://github.com/markqvist/Reticulum/blob/1.5.4/LICENSE),
[LXMF 1.1.1](https://github.com/markqvist/LXMF/blob/1.1.1/LICENSE). Both match each repository's master on 23 October.

Both conditions were added on 15 April 2025. The last MIT releases are `rns` 0.9.4 and `lxmf` 0.6.3; the first under
the new text are `rns` 0.9.5 (9 May 2025) and `lxmf` 0.7.0 (12 May 2025). The bridge was written in September 2026,
so every node that ever built it installed the Reticulum License. The PyPI wheels carry no licence file, only
`License: Reticulum License` in their metadata.

**It is not an open licence.** A condition on what the software may be used for fails point 6 of the Open Source
Definition and the FSF's freedom 0. Read by the rule we hold sources and dependencies to, `rns` and `lxmf` do not
pass. The 18 September licence record (§1) called the rest of the dependency tree permissive; it did not list these
two.

## Each condition, against what the node does

**No system able to purposefully harm people: no conflict.** The node measures air, heat, sea and land and tells the
people there what to do about them. Nothing in it is built to harm anyone. What an operator wires a node into is
theirs to answer for, and the docs now say so.

**No use in creating a training dataset: no conflict today, close to one in a plan.**

- *The local model.* The node trains nothing; there is no fine-tuning anywhere in `app/` or `docs/`. Ollama answers
  questions, which is inference. The only thing Reticulum brings in that a model can read is an `act` note, the
  household's own words, and those reach a model only on this house's machines while `AGENT_PREFER=private`, the
  default (`app/agent_loop.py`). An operator who chooses an online model should know whether that provider trains on
  what it is sent.
- *SPEC_learn.* Retrieval only: Postgres full-text search over learnings and digests the node computed itself. No
  model is fitted and none of it is exported (§7). Embeddings are allowed later "only if words prove too weak"; using
  a model's embeddings is not training it. If a future step ever fits a model on node data, rows that came in over
  Reticulum stay out of it.
- *The open export.* `/export` is CC BY 4.0, and CC BY lets anyone train on it. What Reticulum puts in it today is one
  number: an `act` sent over LXMF adds a row to `actions`, and ρ in the export is computed over those rows. Alerts in
  the export are written by the node; Reticulum only delivers them. Peers are in no export. The node does not make a
  training set, though somebody else could use the export as one. "Directly or indirectly" has never been tested, so
  this record calls the risk low and keeps it on the list below.
- *Parent links over Reticulum (SPEC_fablab §7).* This is where it would bite. A parent link carries the aggregates
  that become a community cell and then the Fab City Index, which is published openly. Carrying them over Reticulum
  makes Reticulum part of how an open dataset is made, and that dataset can be used to train a model. Discovery over
  Reticulum (presence, as it runs now) does not do that. Parent links should not be built on Reticulum without a
  written answer from Mark Qvist.

**Keep the notice with every copy: met by Fab City, owed by an operator who passes an image on.** Fab City conveys
no copy of either package. An operator who shares the image they built is conveying one and must include the notice;
the wheels do not carry it, so the docs link to it.

## Can an Apache-2.0 node ship this?

Yes. Apache-2.0 sets no condition on a dependency's licence, and the node ships a Dockerfile, not Reticulum. The
operator installs `rns` from PyPI on their own machine and the Reticulum License is between them and Mark Qvist. What
the node owes them is to say so before they turn it on: `docs/site/channels.md` and `docs/NETWORKING.md` now do.

**AGPL-3.0 is the problem.** The 25 September record moves the code to AGPL-3.0-or-later once every contributor has
consented. AGPL §10 forbids imposing further restrictions, and both conditions are further restrictions.
`reticulum_bridge.py` imports `RNS` and `LXMF` into one process, which the FSF reads as one combined work. An AGPL
bridge built on them needs one of the choices below before the relicence PR lands.

## The pins

| package | pin | read from |
|---|---|---|
| `rns` | `1.5.4` | `pip list` in node #1's `planetai-reticulum-1`, 23 Oct 2026 |
| `lxmf` | `1.1.1` | same |
| `httpx` | `0.28.1` | same; BSD-3, pinned so the image builds the same everywhere |

`planetai update` builds only the app image, so a node's bridge keeps the versions it was first built with until
`planetai reticulum` runs again (it builds with `--build`). Nodes built before this change carry whatever PyPI had that
day, all of it under the same licence.

Upstream is already at `rns` 1.5.5 and `lxmf` 1.2.0, under the same text. Moving a pin is its own PR, and it reads
`LICENSE` at the new tag first.

## Decided by Tomas, 23 October

He answered the four questions this record left open:

1. **An optional component under a non-open licence is acceptable.** The bridge stays as it is: off until an
   operator runs `planetai reticulum`, with the licence named on the channels page before they do.
2. **The bridge leaves the core.** It moves out before the relicence PR lands, so the AGPL core never imports `RNS`
   or `LXMF`. Where it goes and how a node installs it is the next piece of work, and until then nothing changes on a
   node. *Done 23 October, on his word:* the bridge is fabcity/planetai-reticulum, Apache-2.0, fetched at a pinned
   commit and built on the node (see the CHANGELOG).
3. **Parent links run on HTTPS over the tailnet.** Reticulum carries discovery (presence) and messages to and from
   people, nothing that becomes an Index cell. SPEC_fablab §7 says the same.
4. **No message to Mark Qvist yet.** The training-dataset clause stays read as in this record, and the question in
   it is kept for when it is needed.

Before he answered, the four options were: keep the bridge, move it to its own repository, or pin `rns` 0.9.4 and
`lxmf` 0.6.3 (the last MIT releases); for AGPL, a §7 exception, the move, or dropping the bridge; for parent links,
HTTPS or asking first.
