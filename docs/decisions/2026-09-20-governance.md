# Governance in files, and the things a file cannot do

**20 September 2026. Proposed, not decided.** Drafted from §14 of the 18 September design review. The
review dated this record to the 18th; it is dated the 20th because that is when it was written, which
is the convention `2026-09-10-custody.md` set.

## What was decided

Nothing yet. Six files are drafted — `GOVERNANCE.md`, `MAINTAINERS.md`, `.github/CODEOWNERS`, and
additions to `CONTRIBUTING.md`, `SECURITY.md` and `README.md` — and they describe a shape. This record
is the other half: **what a person has to do by hand before the shape is real**, and the corrections
the review's own numbers needed.

## The numbers, re-counted

The review said *"423 commits, 412 by one person under three names, 8 by an AI, 3 by the two external
testers"*. Counted on 20 September:

| | review | actual |
|---|---|---|
| commits, excluding merges | 423 | **441** |
| by Tomas | 412, under **three** names | **431**, under **five** |
| authored by an AI | 8 | **8** |
| by external contributors | 3, by **two** testers | **2**, by **one** (Lucas, under two identities) |
| carrying `Co-Authored-By: Claude` | — | **331 (75%)** |

Two of those matter. **Only one external person has ever committed**, not two — so the bus factor is
worse than the review said, not better. And three quarters of the history was written with a model,
which is a governance fact the review did not count and `GOVERNANCE.md` now names.

Tomas's five identities: `Tomas Diez <tomasdiez@gmail.com>` (332), `t <t@t>` (94),
`Tomas Diez <tomas@fab.city>` (3), `tomasdiez <tomasdiez@gmail.com>` (1),
`Tomas Diez <fablabbali@fabalabbali.local>` (1). A `.mailmap` would collapse them and is a five-minute
job nobody has done; it is not governance, but it is why every count of this repository has been wrong.

Day 19 of a project whose `PRODUCT.md:79` says *"if it's Tomas past day 30, the product is a hobby"*.

## What the review got wrong about access, and it changes the first action

**`@lucfabcity` already holds full admin on `fabcity/planetai-node`** — verified against the GitHub API
on 20 September. So does `@tomasdiez`. A third collaborator, `@pipezulu`, holds pull-only.

The review's first hand-action was "add Lucas as a GitHub maintainer with merge rights". That is done
and has been for a while. **What is actually owed is the opposite direction**: a person has held admin
on a repository that ships to households without any file saying he does, without a written scope, and
— as far as this record can tell — without having been asked to be answerable for anything.

So the first action is not granting access. It is asking.

## What Tomas has to do by hand

Each of these is a thing no file in the repository can do.

1. **Ask Lucas to accept a scope.** `MAINTAINERS.md` proposes the installer and the Linux platforms.
   He already has the access; what is missing is his "yes". Until then the two-maintainer rule cannot
   run, and `.github/CODEOWNERS` lists one owner on lines that want two.
2. **Name `@pipezulu`, or correct the row.** `MAINTAINERS.md` has a section for the methodology owner —
   read access, no merge rights, deliberately — with no name in it. An agent should not map a GitHub
   handle to a person it was not told about, so it did not.
3. **Give the Foundation's account the Cloudflare zone and the Airtable base.** Both are personal
   today. The Airtable base is the Fab City Index's spine (7 rows, and
   `awesome-fabcity-data` PR #5 is the plan to move it to git); the Cloudflare zone is `fab.city`, on
   which `index.fab.city`, `planetai.fab.city` and the release mirror all sit.
4. **Move `make ship`'s credentials to a second machine**, so that a release is possible from more than
   one laptop. `tools/ship.sh` needs the site repo and the signing key; neither is on a second machine.
5. **Store the release signing key where two people can reach it.** `docs/SIGNING.md` already
   says the Foundation's password manager plus one copy on the ship machine. As of today the key exists
   in one place, and a node refusing an unsigned update — which is it doing its job — becomes a node
   nobody can update if that place is lost.
6. **Decide the licence**, which is its own record and its own session.

## Branch protection: the settings to flip, and why this record does not flip them

**`main` is not protected.** No required reviews, no required status checks, no push restriction. Every
rule in `GOVERNANCE.md` and every line of `.github/CODEOWNERS` is therefore a promise between people.

The settings, for when there are two maintainers to carry them:

| setting | value | why |
|---|---|---|
| Require a pull request before merging | on | `main` is the beta channel; a direct push reaches the next tarball |
| Required approvals | **1** | not 2 — see below |
| Require review from Code Owners | on | this is what makes `.github/CODEOWNERS` do anything at all |
| Dismiss stale approvals on new commits | on | an approval is of a diff, not of a branch |
| Require status checks to pass | on: `lint`, `amd64-linux`, `Ubuntu Server 22.04` | the gates that already run |
| Require branches to be up to date | on | `tests/all`'s suite count merges cleanly and wrongly; NEXT_RELEASE rule 1 |
| Restrict who can push | maintainers | |
| Allow force pushes / deletions | off | |
| Include administrators | **off, for now** | see below |

**Required approvals is 1 and not 2, and administrators are exempt, until `MAINTAINERS.md` has two
confirmed names.** A two-review rule on a one-maintainer project does not make the project careful, it
makes it stop — and the predictable response to a rule that stops the work is to turn the rule off,
after which there is no rule. Raise it to 2 and include administrators in the same PR that moves
Lucas from `proposed` to active, and record that as a second entry here.

## What this costs if it is wrong

Little, and that is the argument for doing it now. Six files and no code: `make lint` reads them,
`check_docs.py` checks their links, and nothing a node runs changes. The expensive version of this
decision is the one taken in month eight, when there are thirty nodes, a second operator organisation
and a licence argument, and the answer to "who decides" has to be invented under pressure by people who
did not write the code.

The real risk is the opposite: that these files are drafted, never confirmed, and become a description
of a project that does not work that way — which is worse than no file, because a reader believes it.
The six hand-actions above are the difference, and five of them are conversations rather than commits.

## Not decided here

- **The licence.** `docs/decisions/2026-09-18-licence.md`, a separate record and a separate session.
  `GOVERNANCE.md`'s "a second organisation running nodes under the name" is a placeholder for it.
- **The Foundation's trademark position.** Not stated from memory, and not guessed.
- **Whether the Foundation-dissolution clause binds anything.** `GOVERNANCE.md` states an intent. For
  it to be an instrument the Foundation would have to hold the things it would be passing on, and
  today it holds none of them — which is actions 3, 4 and 5 above.
