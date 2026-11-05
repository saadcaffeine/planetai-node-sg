# Flashing and USB from a laptop on the house LAN

2026-10-27 · Tomas

## The question

The workbench (`/workbench`, framed in the Data door with `allow="serial"`) flashes Bayu and Meshtastic boards
and reads them over USB. Chrome gives a page Web Serial only in a secure context. That means https, or plain http
on `localhost`. A laptop that opens the node at `http://<node LAN IP>:8081` gets no `navigator.serial` and no Cache
Storage either, so Flash and USB stay greyed out and the firmware cache cannot save. It only works on the node
machine itself. How does a second laptop in the house get it, with the internet off?

## What was measured

Google Chrome 156.0.8078.48 on macOS, a fresh profile for each case, launched for real (headed, not headless) and
driven over CDP. The node was a scratch node on main `e86638b`, running natively on this Mac against a throwaway
PostGIS and reached on its LAN address `192.168.68.101`. Node #1 was not touched. Each case asked the page what
the workbench asks (`isSecureContext`, `'serial' in navigator`, `btnusb.disabled`, ESP Web Tools'
`install-unsupported`). It also made a real click that calls `navigator.serial.requestPort()`. If the promise is
still pending 2.5 s later, Chrome's port chooser is open. The same checks ran on the page framed inside an
`<iframe allow="serial">`, the way the Data door frames it.

| case | secure | serial | USB button | flasher | chooser opens | framed | warning |
|---|---|---|---|---|---|---|---|
| `http://localhost:8290` (on the node) | yes | yes | on | supported | yes | n/a | none |
| `http://192.168.68.101:8290` today | no | no | off | unsupported | n/a | n/a | none |
| 1 · `https://…:9443`, self-signed, "Proceed" | yes | yes | on | supported | yes | yes | every 7 days |
| 2 · `http://…:8290` + the Chrome flag | yes | yes | on | supported | yes | yes | none |
| 3 · `https://…:9444`, leaf from a local CA | yes | yes | on | supported | yes | yes | none |

In cases 1, 2 and 3, Cache Storage writes and reads back. Pressing ESP Web Tools' own "Connect and flash" calls
`requestPort` and leaves the chooser open. No ESP board was plugged into the test Mac, so nothing was written to a
chip. The flasher gets as far as the port picker, and from there on it is the same code as on localhost.

Per case, what matters for the choice:

- **Self-signed (1):** Chrome keeps the "Proceed" decision for exactly 7 days. The profile stores
  `decision_expiration_time` 604,800 s after `last_modified`, keyed to the host and the certificate's hash. It
  survived a full browser restart. After a week, or after a new certificate or a new IP, the red "Your connection is
  not private" page comes back. The address bar keeps saying "Not secure" the whole time.
- **The flag (2):** `chrome://flags/#unsafely-treat-insecure-origin-as-secure` was set through the flags page
  itself. Chrome writes it to the profile's `Local State`, and it survived the relaunch. It covers only the exact
  origin typed in. The same node opened through its Tailscale IP was refused again. No code is involved, and
  nothing ever warns.
- **Local CA (3):** not measured the way a person would do it. Chrome 156 has its own store for this
  (`chrome://certificate-manager` › Installed by you › Trusted Certificates › Import), but the import opens the
  native macOS file panel, which the test could not drive without typing into Tomas's own browser. So Chrome was
  told to trust the leaf's key instead (`--ignore-certificate-errors-spki-list`), and macOS
  `security verify-cert` accepted the leaf against the spike CA. The page loaded with no warning and behaved like
  localhost. The proper per-laptop check is still owed.
- **`tailscale cert`:** not run, because issuing writes the machine's name into the public Certificate
  Transparency logs. Tailscale's own docs say the certificate comes from Let's Encrypt through a DNS-01 challenge
  and lasts 90 days. That needs the internet at issue and at every renewal, and the laptop needs Tailscale running
  to resolve `*.ts.net`. If the house is offline when it expires, every laptop gets a certificate error until the
  internet is back. Ruled out. HTTPS is already on for this tailnet (`CertDomains` lists `macbook-pro.tail3050d6.ts.net`).
- **A phone:** not measured. iOS has no Web Serial in any browser. Chrome for Android is reported to have gained
  Web Serial in Chrome 148 (April 2026), with the same secure-context rule and its own `chrome://flags`. Whether
  ESP Web Tools flashes from Android was not tested. A second laptop is the same as the first: each one does its
  own step once (with option 1, again every week).

## The decision

**Option 2, the Chrome flag, with no node code.** Tomas approved it the same day. The only change is the
workbench's "not secure" hint. When the page is served over http and is not a secure context, the USB hint and the
Flash banner name the exact steps for this address:
open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, paste `<location.origin>`, set Enabled,
Relaunch. The page knows its own origin, so the person copies one line. It works offline from the first minute,
and nobody learns to click through a red warning.

Why not the other two:

- 1 makes the node run a second port and a certificate of its own, and in return everyone gets a red warning
  every week. That teaches clicking through certificate warnings, which is the wrong habit.
- 3 is the clean one, but every laptop has to install a CA that could vouch for any website. That means an admin
  password on a Mac or a settings dive on Android. The node would also need a CA, a leaf renewed whenever its
  address changes, and a second port. It is the upgrade path if a class of non-technical people has to flash
  sensors at a lab. In that case the CA should carry a name constraint so it vouches only for the node, which
  was not tested here.

What option 2 asks of the house: the node keeps one address. Give node #1 a DHCP reservation, or use its `.local`
name if mDNS answers on the LAN (it does not always, see the node #1 deployment notes). A change of address means
pasting the new one into the flag.

## Not done

- The hint is the change in `app/static/workbench.html` (key `serial.flag`, three languages). The site's
  `sensors/index.html` gets the same edit, so the two copies stay identical.
- No board was flashed during the spike. Before closing this, someone should flash one real board from a second
  laptop through node #1's LAN address with the flag on.
- The macOS keychain and Chrome's "Installed by you" import for option 3 were not done by hand.
