# MC ReAuth — Forge 1.7.10 account switcher

A **pure-Java, client-only Forge mod for Minecraft 1.7.10**. It adds a button to
the **multiplayer (server select) screen**; pressing it opens a small login
form that re-authenticates the running client against **MCSkill** (priority)
or **GribLand** and swaps the account **without restarting the game**.

No DLL, no injector, no external process, no local bridge — everything runs
inside the game JVM.

> Account switcher for *your own* accounts on *your own* servers, using your
> own credentials. The mod only replaces this client's own login session;
> it grants nothing a normal re-login wouldn't.

## How it works

- **Button**: a Forge `GuiScreenEvent` handler adds the button to
  `GuiMultiplayer` and opens `GuiAccountSwitch` when clicked
  (`gui/GuiEventHandler.java`, `gui/GuiAccountSwitch.java`).
- **MCSkill** (`auth/McSkillAuth.java`): gRPC/TLS call to
  `launchernew.mcskill.ru:443`, service `launcher.AuthService/Login`. Instead
  of a generated protobuf runtime it uses grpc-java with raw `byte[]`
  marshallers and a tiny hand-written protobuf codec
  (`auth/ProtoCodec.java`), so the only heavy dependency is grpc itself.
- **GribLand** (`auth/GribLandAuth.java`): plain HTTPS to
  `launcher.gribland.net` using the JDK and the Gson already bundled in
  Minecraft 1.7.10 — no extra dependency.
- **Session swap** (`SessionSwapper.java`): builds a new
  `net.minecraft.util.Session(name, uuid, token, "mojang")` and assigns it to
  the `Minecraft` singleton's session field. The field is found **by type**
  (not by name) so runtime SRG obfuscation of the field name doesn't matter.

The protobuf message layout and endpoint were reconstructed from
`github.com/Faticc/mcproto`; the `.proto` files are in `proto/` for reference
(they are **not** compiled — `ProtoCodec` encodes the messages directly).

## Build

Requires **JDK 8** and the legacy **ForgeGradle** toolchain for 1.7.10 (FG
`1.2-SNAPSHOT` + Gradle ~2.14), plus the shadow plugin. MCSkill's gRPC is
bundled into the mod jar:

```bash
cd mc_reauth/mod
./gradlew setupDecompWorkspace     # first time only
./gradlew build                    # -> build/libs/mc-reauth-mod-0.1.0.jar
```

Dependencies bundled (see `build.gradle`):

- `io.grpc:grpc-netty-shaded:1.60.0` — gRPC transport. It **shades its own
  Netty**, so it won't clash with Minecraft 1.7.10's Netty 4.0.10, and it
  bundles `tcnative`/BoringSSL so TLS+ALPN work on Java 8.
- `io.grpc:grpc-stub`, `grpc-core`, `grpc-api` (1.60.0).

`build.gradle` relocates Guava (`com.google.common`) because MC 1.7.10 ships
Guava 17 while grpc needs a newer one.

> **Not built/verified in this environment.** The repo tooling here can't run a
> 1.7.10 ForgeGradle build, so the jar was not produced or launched. The
> dependency-free protobuf codec (`ProtoCodec`) is unit-tested; the Forge/grpc
> wiring is written to spec but should be built in a real 1.7.10 workspace.
> Two spots are the most likely to need a tweak for your exact setup:
> 1. the `reobf { shadowJar { ... } }` wiring (differs between ForgeGradle
>    forks), and
> 2. the Guava relocation / `mergeServiceFiles()` (so grpc's
>    `ManagedChannelProvider` ServiceLoader entry survives shading).

## Install & use

1. Drop the built jar into `.minecraft/mods/` (Forge 1.7.10 profile).
2. Launch the game, open **Multiplayer**.
3. Click the account button (top-left). In the form: pick **MCSkill**
   (default) or **GribLand**, enter login + password (+ 2FA code and client
   name for GribLand), press **Войти**.
4. On success the client's account is switched immediately — connect to a
   server as usual, no restart.

## Limitations

- Targets **1.7.10** specifically (uses that version's `Session` constructor
  and GUI events). The universal, any-version path is the DLL in `../dll/`.
- MCSkill requires the bundled grpc/TLS stack; if your pack's environment
  blocks it, GribLand (pure HTTP) still works.
- Passwords are held only in memory for the login call and never written to
  disk.
