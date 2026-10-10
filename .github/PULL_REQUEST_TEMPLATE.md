## What this changes, and why

<!-- One or two sentences. What was wrong or missing, and what this does about it. -->

## Who wrote it

A person is responsible for every pull request here, whatever wrote the code. Tick one:

- [ ] I wrote this myself.
- [ ] I wrote this with an agent. It was: <!-- Claude Code, Codex, Cursor, a local model… -->

If you used an agent, also tick this:

- [ ] I read every line of this diff and I understand what it does.

A pull request opened by an agent with nobody behind it is closed unread. This is not a rule about tools —
use whatever helps. It is that a node runs in somebody's home, on their machine, next to their family, and
somebody has to be answerable for what it does there.

## Checks

- [ ] `make lint` and `make test` pass on my machine.
- [ ] If I added a lint gate, I broke something on purpose first and watched it fail.
- [ ] No secrets, no `.env`, no tokens, and no log lines containing `api.telegram.org/bot`.
- [ ] My commits are signed off (`git commit -s`).
- [ ] This is not a pack for one place: that goes to fabcity/planetai-wild-packs. A pack here is a promotion.

## How I know it works

<!-- What you actually ran or observed. "It should work" is not this. If it touched a node, say which one
     and what it did afterwards. -->
