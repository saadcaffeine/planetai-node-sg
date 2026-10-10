# The release signing key

Since v0.60 a node refuses an update it cannot attribute. The key that makes that work was issued on 19
September 2026 and lives outside this repository (§3). This is the runbook for the person who holds it:
how it was made, where its public half is copied, how a release is signed, and how to rotate it. An agent
never makes or handles this key: a private key an agent generated is a private key that was in a transcript.

## 1. Make the key

On your own machine, once:

```bash
mkdir -p -m 700 ~/.planetai
ssh-keygen -t ed25519 -f ~/.planetai/release_key -C fabcity
```

**The `mkdir` is not optional.** `ssh-keygen` does not create the parent directory, and on a machine
that has never held this key there is none — it asks for the passphrase twice, then says `Saving key
… failed: No such file or directory` and you type it again from the start. `700` because the private
half lives there. (Cost this exact round trip on 19 Sep 2026, on the first machine that ever ran it.)

Give it a passphrase. `tools/release.sh` reads the key through `ssh-agent`, so `ssh-add
~/.planetai/release_key` once per session is the whole cost of having one.

## 2. Publish the public half

```bash
printf 'fabcity %s fabcity\n' "$(awk '{print $1" "$2}' ~/.planetai/release_key.pub)"
```

Read out of `release_key.pub`, which `ssh-keygen` wrote beside the private half. `ssh-keygen -y -f
~/.planetai/release_key` gives the same bytes but asks for the passphrase to do it, and there is no
reason to type a passphrase to read something public.

That one line replaces the signer line in **four** files. They must end up byte-identical;
`tests/test_release_consistency.sh` fails if they do not. **It was issued on 19 September 2026, so
those files no longer carry a placeholder** — anything that keyed off that string had to be rekeyed
to the signer line's shape instead, which is what `install-smoke.yml` and the consistency test now
do. If you rotate the key, grep for `fabcity ssh-ed25519` rather than for a placeholder.

| file | why it has its own copy |
|---|---|
| `tools/allowed_signers` | the one a release is signed and verified against |
| `install` | runs before there is a node; cannot read a file out of the tarball it is checking |
| `update.sh` | same, and it is the file that refuses a bad update |
| `bin/planetai` | so `planetai version` can say what the node trusts |

Then put the fingerprint — `ssh-keygen -lf ~/.planetai/release_key.pub | awk '{print $2}'` — into
`SECURITY.md`, where the `SHA256:…` line still says *not yet issued*. Commit all five together.

## 3. Where the key lives

- **The Foundation's password manager.** The private key file and its passphrase, as two separate
  entries. This is the copy that survives a laptop.
- **One working copy** at `~/.planetai/release_key` on the machine that cuts releases, and nowhere else.

Not in this repository (`tools/release.sh` refuses a key whose directory is inside it), not in the
tarball, not in CI, not in a log. CI signs with a throwaway key it generates per run and never sees this
one — if a job ever needs the real key, something has been designed wrong.

## 4. Cutting a release

```bash
ssh-add ~/.planetai/release_key
PLANETAI_SIGNING_KEY=~/.planetai/release_key tools/release.sh 0.60
```

It refuses before it tags if the key is missing, is inside the repository, or is not the key
`tools/allowed_signers` publishes — that last one is the quiet failure, where everything signs happily
and every node then refuses.

`PLANETAI_UNSIGNED=1` builds a tarball nobody signed, for a test you will throw away. It says so in red
at both ends.

## 5. Rotation

Two releases, never one.

1. **Add** the new public line to `tools/allowed_signers` and the three embedded copies, *beside* the
   old one, both with the principal `fabcity`. Ship a release signed with the **old**
   key. Every node now accepts either.
2. Wait until nodes have taken that release — `planetai doctor` shows the row, and the fleet is small
   enough to ask. Then ship a release signed with the **new** key.
3. **Remove** the old line in the release after that.

A node only ever learns a new key by installing an update signed with a key it already trusts, so the
order matters: remove the old line too early and any node that has not updated yet is stranded on a key
nothing signs with. There is no recovery from that over the network — it is a person, at the machine.

If the key is believed lost or copied, that patience is not available: publish the new line, ship, and
say so in `SECURITY.md` and the changelog. A node that has not updated will refuse the new release and
have to be reinstalled by hand. Two copies in two places is what stops this being likely.

## 6. Cloudflare is now a mirror, not the source

`planetai.fab.city/node0/get` is one bucket with one writer and no history a reader can check. It is
still where nodes fetch from by default, but it is no longer what they trust: the signature is. Every
release also goes to a GitHub Release, with the same bytes and the same signature, and a node reads
that instead with one variable:

```bash
PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/v0.60 \
  bash -c "$(curl -fsSL planetai.fab.city/install)"
```

So a compromised bucket is now a detectable event rather than a silent one, and there is somewhere else
to send a tester while it is sorted out.
