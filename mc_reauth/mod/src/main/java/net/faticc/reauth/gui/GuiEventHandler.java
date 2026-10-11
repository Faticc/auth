package net.faticc.reauth.gui;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiButton;
import net.minecraft.client.gui.GuiMultiplayer;
import net.minecraftforge.client.event.GuiScreenEvent;
import cpw.mods.fml.common.eventhandler.SubscribeEvent;

/**
 * Adds the "switch account" button to {@link GuiMultiplayer} and opens the
 * account screen when it is pressed.
 */
public final class GuiEventHandler {

    /** Unlikely to collide with vanilla/other mods' button ids. */
    private static final int BUTTON_ID = 0xACC01;

    @SubscribeEvent
    public void onInitGui(GuiScreenEvent.InitGuiEvent.Post event) {
        if (!(event.gui instanceof GuiMultiplayer)) {
            return;
        }
        // Top-left corner, clear of the vanilla button column.
        GuiButton button = new GuiButton(BUTTON_ID, 6, 6, 120, 20,
                currentLabel());
        event.buttonList.add(button);
    }

    @SubscribeEvent
    public void onAction(GuiScreenEvent.ActionPerformedEvent.Pre event) {
        if (!(event.gui instanceof GuiMultiplayer)) {
            return;
        }
        if (event.button != null && event.button.id == BUTTON_ID) {
            Minecraft.getMinecraft().displayGuiScreen(
                    new GuiAccountSwitch(event.gui));
        }
    }

    private static String currentLabel() {
        String name = Minecraft.getMinecraft().getSession().getUsername();
        return "Аккаунт: " + (name == null || name.isEmpty() ? "?" : name);
    }
}
