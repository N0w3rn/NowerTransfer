# NowerTransfer

<img src="assets/logo.png" alt="" width="84" align="right">

Send a file to someone through **your own relay**. One window, two buttons.

The person you send the app to does not install anything, does not sign up
anywhere, and does not configure anything. They double-click the `.exe`,
pick *Send* or *Receive*, and the file moves — end-to-end encrypted, over
infrastructure you control.

Sending is a drag of the files onto the window, or a click if you prefer;
receiving is the code phrase and nothing else. The interface is German or
English, switchable in the header.

Under the hood it drives [croc](https://github.com/schollz/croc), which
handles the encryption, the NAT traversal and the relay protocol.

> **Windows only, for now.** That is where it is built, run and tested.
> Nothing is deliberately Windows-bound — croc is fetched per platform
> and the UI is plain tkinter — but no one has run it elsewhere, and
> secrets are only encrypted at rest on Windows (see below). Treat other
> platforms as untested rather than unsupported.

---

## Setup

**1. Run a croc relay** on any server. This is the only infrastructure
needed — ports **9009–9013** have to be reachable:

```yaml
# docker-compose.yml on your server
services:
  croc-relay:
    image: schollz/croc:latest
    restart: unless-stopped
    entrypoint: ["croc"]
    command: ["--pass", "your-relay-password", "relay"]
    ports:
      - "9009-9013:9009-9013"
```

The password is optional; drop `--pass` and croc's default applies.

**2. Point the app at it** and build:

```bash
cp .env.example .env        # RELAY_HOST and RELAY_PASSWORD go here
poe build 1.0.0             # the version this build calls itself
```

**3. Hand out `dist/NowerTransfer.exe`.** That's it.

`poe installer 1.0.0` produces `dist/NowerTransfer-1.0.0-setup.exe`
instead — same app, with a start menu entry and an uninstaller. It
installs for the current user, so there is no administrator prompt.
Releases carry both.

The relay is baked into the binary, so recipients get a working app rather
than a setup task.

---

## Configuration

`.env` covers the normal case, and is the only file you touch. Build
without one and the app asks the user on first start instead.

At runtime the app resolves each value through four layers, later wins:

| Layer | Where | Use for |
|---|---|---|
| build | `.env` from source, baked into the binary by `poe build` | the app you hand out |
| portable | `nowertransfer.toml` next to the `.exe` | preconfiguring a copy without rebuilding |
| user | in-app settings screen | the recipient changing it themselves |
| environment | `NOWERTRANSFER_RELAY`, `NOWERTRANSFER_RELAY_PASSWORD` | CI and scripted runs |

The settings screen shows which layer each value came from, and has a
**Test connection** button. It tests the *address*: whether the relay
answers, and how long that took.

It deliberately does not test the password, and says so on screen.
Measured against a real relay: croc reports a refused relay password
at 0.1 s in one run and never in the next, for the same wrong password
— so a clean result would mean nothing, and reporting it as success
would be worse than reporting nothing. A wrong password surfaces on
the first real transfer, which does say so plainly.

The last three layers live on the user's machine and never appear in
this repository.

### Which relay

`RELAY_MODE`, also changeable in the settings screen:

| Mode | Behaviour |
|---|---|
| `own` (default) | only your relay; fail if it is down |
| `fallback` | prefer yours, switch to croc's public relay if it is down — and say so on screen |
| `public` | always croc's public relay; no relay of your own needed |

File contents are end-to-end encrypted in every mode. What changes is who
gets to see *that* a transfer happened: anything but `own` puts that
metadata in front of a relay somebody else runs, which is why the switch
is never silent.

---

## Development

Needs [uv](https://docs.astral.sh/uv/) and nothing else — it fetches the
right Python itself.

```bash
uv sync       # once: creates .venv from uv.lock
poe croc      # download the croc binary, checksum-verified
poe app       # run from source
poe test      # the test suite
poe lint      # ruff check
poe fmt       # ruff format
poe check     # everything CI runs
poe build 1.0.0
poe installer 1.0.0   # needs Inno Setup: winget install JRSoftware.InnoSetup
poe lock      # after changing dependencies
```

`poe` on its own lists the tasks. `uv sync` is the only command that is
not one, and you run it once. Activate `.venv` — VS Code does it for you
— or prefix with `uv run`.

Versions are pinned in `uv.lock`, which covers Linux, Windows and macOS
in one file. CI runs `uv sync --locked`, which fails if `pyproject.toml`
changed without `poe lock` being run, and the executable is built inside
that same environment — so the binary contains the versions the lockfile
names. `.python-version` is the interpreter to develop against;
`requires-python` stays the supported range.

`tests/test_ui_layout.py` builds the real screens and measures them —
that a button did not get squeezed to one pixel, that the longest code
phrase still fits, that a locked field is visibly locked. It needs a
display, so it skips on a machine without one and runs under `xvfb` in
CI. Deliberately no screenshot comparison: that would go red on a font
change without anything being broken.

### Versioning

**Every build states its version** — `poe build 1.0.0`. Leave it out and
the build refuses, rather than inventing a number nobody can match to a
binary later. Format is `MAJOR.MINOR.PATCH`, optionally marked
(`1.0.0-rc1`, `1.0.0-test`).

The exception is a release, which takes the version from the tag:

```bash
git tag v1.1.0 && git push --tags     # builds and publishes 1.1.0
```

So the number in the window footer is always the one someone actually
downloaded:

| Where it runs | Shows |
|---|---|
| from source (`poe app`) | `dev` |
| tagged release | `1.1.0` |
| `poe build 1.0.0-test` | `1.0.0-test` |
| a bundle with no version stamped | `unknown` |

`VERSION` in `src/nowertransfer/__init__.py` is the single place the
source version is written — `pyproject.toml` reads that same line.

---

## How it works

```
 Sender                    your relay                   Receiver
   │      croc, E2E encrypted   │   croc, E2E encrypted     │
   ├───────────────────────────►│◄──────────────────────────┤
   │        code phrase ─────────── out of band ────────────►│
```

- **The code phrase is the key.** croc derives the encryption key from it
  via PAKE, so it is generated with `secrets`, not `random`, and never
  appears in the process list — it reaches croc through the environment.
  Five words from a 256-word list plus two digits is about **46 bits**,
  and PAKE leaves nothing to grind offline: every guess costs a
  connection to the relay. No two words in the list are one typo apart,
  so a code that was read out loud cannot land on a different valid word.
- **The relay password is a door lock, not a safe.** It keeps strangers
  from using your bandwidth. It does not protect file contents; those are
  encrypted before they ever reach the relay, which stores nothing.
- **Dropped connections retry automatically** until the transfer completes
  or the user cancels. An unreachable relay is told apart from a peer who
  simply has not shown up yet.
- **Secrets on disk are encrypted to the Windows account** that wrote
  them, via DPAPI. That covers the relay password saved in the settings
  screen, and the code phrase *and file paths* of an interrupted send —
  a folder name says what was being sent. A copy of those files on
  another machine or account is useless; code already running as that
  user is not stopped by anything stored locally.
- **The settings directory is restricted to that account.** `chmod` is
  what does it on Linux and macOS; on Windows it does nothing to the
  access control list, so the list is rewritten instead — inheritance
  off, one entry, no Administrators and no SYSTEM. Without that a
  second account on the same machine could read the file, and the
  encryption above would be all that stood between them and it.
- **The relay baked into a build is readable**, and cannot be otherwise —
  a binary has to decrypt its own configuration unattended, so the key
  would travel with it. Treat an `.exe` you hand out as disclosing its
  relay to whoever holds it.

## Layout

```
src/nowertransfer/
  config.py     layered relay configuration
  envfile.py    .env parsing
  codes.py      code-phrase generation
  croc.py       locating the croc binary
  transfer.py   subprocess handling, retries, output parsing
  i18n.py       German / English catalogue
  relaycheck.py the settings screen's connection test
  ui/           theme, fonts, icons, widgets, drag and drop,
                one module per screen
scripts/
  build.py         builds the executable, bakes in the relay
  make_installer.py wraps it in an Inno Setup installer
  make_icon.py     renders assets/icon.ico from the logo
  fetch_croc.py    downloads croc from its GitHub releases
installer/
  NowerTransfer.iss the setup script
assets/
  fonts/        the two bundled faces, with their licences
```

No secrets are committed, and `croc` is not: it is fetched at build time,
pinned to one release in `scripts/fetch_croc.py` and verified against the
SHA-256 that release publishes.

The window's own icons — the arrows, the back chevron, the drop tray —
are not images at all: `ui/icons.py` strokes them onto a canvas from
coordinates, so they stay sharp at any display scaling and take the
colour of whatever they sit on. `scripts/make_icon.py` renders
`assets/icon.ico` from the logo at every size Windows asks for, each
one drawn from the full-size original rather than scaled down from the
next size up, which is what makes a taskbar icon look smeared. Drop an
`assets/logo-small.png` beside the logo and the sizes at 32 pixels and
below are drawn from that instead: the Windows 11 taskbar renders at
24 pixels, which is less room than the full mark needs.

`assets/` holds the logo and icon, which are the app's own, and
`assets/fonts/` the two faces it draws with — [Space
Grotesk](https://github.com/floriankarsten/space-grotesk) and [IBM Plex
Mono](https://github.com/IBM/plex), both under the SIL Open Font License
1.1, whose text ships beside them. They are committed rather than
fetched because they are small, versionless in practice, and the app
should not need the network to look right. Windows loads them for the
running process only, so nothing is installed on the user's machine; if
that fails the app falls back to Segoe UI and Consolas.

**Both sides of a transfer need the same croc major version.** croc 11
changed its PAKE handshake and refuses croc 10 peers outright, so when the
pin moves across a major, every copy you handed out has to be replaced.
The relay is not affected — a croc 11 client talks to a croc 10 relay
fine. The app detects the mismatch and says so instead of retrying.

Tagged releases are built **without** a relay on purpose — a published
binary carrying relay credentials would hand every downloader the keys to
that relay. Build locally to hand out a preconfigured copy.

## License

MIT — see [LICENSE](LICENSE). The bundled fonts are not MIT: both are
SIL Open Font License 1.1, with their texts in `assets/fonts/`. croc,
fetched at build time, is MIT.
