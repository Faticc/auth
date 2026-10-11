package net.faticc.reauth;

import net.faticc.reauth.gui.GuiEventHandler;
import net.minecraftforge.common.MinecraftForge;
import cpw.mods.fml.common.Mod;
import cpw.mods.fml.common.Mod.EventHandler;
import cpw.mods.fml.common.event.FMLInitializationEvent;
import cpw.mods.fml.relauncher.Side;
import cpw.mods.fml.relauncher.SideOnly;

/**
 * Client-only Forge 1.7.10 mod that adds a "switch account" button to the
 * multiplayer (server select) screen and re-authenticates the running client
 * in place against MCSkill (priority) or GribLand.
 */
@Mod(modid = ReAuthMod.MODID, name = ReAuthMod.NAME,
        version = ReAuthMod.VERSION, clientSideOnly = true,
        acceptedMinecraftVersions = "[1.7.10]")
public final class ReAuthMod {

    public static final String MODID = "mcreauth";
    public static final String NAME = "MC ReAuth";
    public static final String VERSION = "0.1.0";

    @EventHandler
    @SideOnly(Side.CLIENT)
    public void init(FMLInitializationEvent event) {
        MinecraftForge.EVENT_BUS.register(new GuiEventHandler());
    }
}
