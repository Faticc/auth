package net.faticc.reauth;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;

import net.faticc.reauth.auth.GameSession;
import net.minecraft.client.Minecraft;
import net.minecraft.util.Session;

/**
 * Replaces the running client's login session so the next server join uses a
 * different account -- no game restart.
 *
 * The Minecraft singleton holds its {@code Session} in a private final field
 * whose name is SRG-obfuscated at runtime, so the field is located by its
 * TYPE ({@link Session}) rather than by name. A fresh {@link Session} is built
 * via its public 1.7.10 constructor (compiled against MCP names, remapped by
 * reobfuscation) and assigned in place.
 */
public final class SessionSwapper {

    private SessionSwapper() {
    }

    public static synchronized void apply(GameSession gs) throws Exception {
        Minecraft mc = Minecraft.getMinecraft();
        Session session = new Session(gs.username, gs.uuid, gs.accessToken,
                "mojang");

        Field target = null;
        for (Field f : Minecraft.class.getDeclaredFields()) {
            if (Session.class.isAssignableFrom(f.getType())) {
                target = f;
                break;
            }
        }
        if (target == null) {
            throw new IllegalStateException(
                    "Session field not found on Minecraft");
        }

        target.setAccessible(true);
        clearFinal(target);
        target.set(mc, session);
    }

    private static void clearFinal(Field field) throws Exception {
        if ((field.getModifiers() & Modifier.FINAL) == 0) {
            return;
        }
        // Works on the Java 8 runtime that Minecraft 1.7.10 uses.
        Field modifiers = Field.class.getDeclaredField("modifiers");
        modifiers.setAccessible(true);
        modifiers.setInt(field, field.getModifiers() & ~Modifier.FINAL);
    }
}
