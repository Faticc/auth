# mc_reauth — live Minecraft account switcher

Re-authenticate / switch the Minecraft account of an **already-running**
client at any moment — no game restart and no re-opening the administration
tool. It authenticates against your own server ecosystems using the auth
packages already in this repository:

- **MCSkill** (`auth`, gRPC) — the **priority** provider
- **GribLand** (`gribland_auth`, launcher HTTP API)

and then injects the resulting game session (uuid / access token / username)
into the live client.

> **Scope & intent.** This is an account switcher for *your own* accounts on
> *your own* servers. The native module only touches the login `Session`
> object of the process it is injected into, using credentials you supply.
> It grants nothing a normal re-login would not — it just avoids the restart.
> It is not an exploit and does not bypass any server-side security.

---

## How it fits together

```
          credentials                 session JSON (loopback only)
 operator ──────────▶ Python layer ───────────────────────▶ native DLL
                      (auth / gribland_auth)   127.0.0.1    (inside javaw.exe)
                               │                                  │
                      resolves GameSession              JVMTI: find & mutate
                      (uuid, token, username)           net.minecraft.util.Session
```

1. Your admin tool injects `reauth-x64.dll` / `reauth-x86.dll` into the
   running `javaw.exe` (injection is done by *your* tool — this project does
   not ship an injector).
2. On load the DLL grabs the running JVM (`JNI_GetCreatedJavaVMs`), attaches
   a thread, and listens on `127.0.0.1:5151` (loopback only — never exposed
   off the machine).
3. To switch accounts, the Python layer logs in (MCSkill first), gets a
   `GameSession`, and sends it to that port. The DLL locates the client's
   session object via JVMTI and updates the username / uuid / token in place.
   The next server join uses the new account.

The control protocol is one line of JSON:

```
-> {"uuid":"...","accessToken":"...","username":"..."}\n
<- {"ok":true,"username":"...","strategy":"value-shape"}\n
```

so the admin tool can speak it directly (any language) instead of calling
the Python CLI, if preferred.

---

## Universality & the obfuscation question

**Forge 1.7.10 keeps the Minecraft *class* names readable at runtime**
(`net.minecraft.client.Minecraft`, `net.minecraft.util.Session`); only the
*field* names are SRG-obfuscated (`field_74286_a`, …). The DLL therefore does
**not** rely on field names. The classic `Session` class has exactly three
`String` fields — `username`, `playerID`, `token` — so the DLL identifies
them by the **shape of their current values**:

- the value matching a UUID (32 hex, or 8-4-4-4-12 dashed) → **uuid**
- the value matching `^[A-Za-z0-9_]{1,16}$` → **username**
- the remaining string → **access token**

This value-shape strategy works across the whole classic-`Session` family
(**1.7.10 / 1.8.9 / 1.12.2**) regardless of obfuscation. Detection order:

1. **`reauth.ini` override** — exact field names, if you set them.
2. **Readable-name heuristic** — for dev / Mojang-mapped builds.
3. **Value-shape** — the obfuscation-proof default.

Newer versions (1.16+) renamed `Session` → `net.minecraft.client.User` with a
different field layout; the DLL will try it and apply the fields it can
classify, but **full coverage of every version/launcher is not guaranteed**.
For an unusual client, pin the field names in `reauth.ini` (see that file)
and no rebuild is needed. The DLL writes a `mc_reauth.log` next to itself
recording which strategy and which fields it used.

---

## Build (native DLL)

Requires the mingw-w64 cross-compiler (or MSVC/MSYS2 on Windows — the source
is plain C99 + Win32 + JNI/JVMTI, no third-party deps):

```bash
sudo apt-get install gcc-mingw-w64-x86-64 gcc-mingw-w64-i686   # Debian/Ubuntu
cd mc_reauth/dll
./build.sh        # -> build/reauth-x64.dll and/or build/reauth-x86.dll
```

- Use **reauth-x64.dll** for 64-bit `javaw.exe` (most modern launchers).
- Use **reauth-x86.dll** for 32-bit `javaw.exe` (common with 1.7.10).

Inject the DLL whose bitness matches the target JVM. Put the optional
`reauth.ini` in the same folder as the DLL.

---

## Use (Python layer)

From the repository root (so the `auth` / `gribland_auth` packages import):

```bash
# install the backends + this tool
pip install -e .
pip install -e mc_reauth/python
```

Switch the live client (password from `MC_REAUTH_PASSWORD` or a prompt):

```bash
# MCSkill (priority provider)
python -m mc_reauth switch --username admin

# GribLand (needs the launcher client name)
python -m mc_reauth switch --provider gribland \
    --username admin --client-name SKYDRIVE-HITECH-TEST

# Just resolve the session without touching the game (debug)
python -m mc_reauth switch --username admin --print-only

# Is an agent listening?
python -m mc_reauth ping
```

Programmatically:

```python
from mc_reauth import authenticate, apply_session

session = authenticate(username="admin", password=pw, provider="mcskill")
apply_session(session, host="127.0.0.1", port=5151)
```

See `examples/switch_account.py`.

### Priority & fallback

`authenticate()` uses **MCSkill by default**. GribLand is contacted only when
you explicitly select it, or pass `fallback=True` — so a password is never
forwarded to a second ecosystem behind your back.

---

## Layout

```
mc_reauth/
  dll/                 native Windows module (injected into javaw.exe)
    src/reauth.c       JVM attach + loopback control + JVMTI session swap
    include/jni_md.h   Windows JNI defs (jni.h/jvmti.h pulled from your JDK)
    build.sh           cross-compile x64 + x86
    reauth.ini         optional port + field-name overrides
  python/mc_reauth/    auth orchestration + control client + CLI
  python/tests/        unit tests (stub backends, no network)
  examples/
```

This subproject is self-contained and can be lifted into its own repository
unchanged; only the two `import auth` / `import gribland_auth` references tie
it to this repo (satisfy them with `pip install` or `PYTHONPATH`).

## Tests

```bash
PYTHONPATH=mc_reauth/python python -m unittest discover -s mc_reauth/python/tests
```
