package net.faticc.reauth.gui;

import org.lwjgl.input.Keyboard;

import net.faticc.reauth.SessionSwapper;
import net.faticc.reauth.auth.Accounts;
import net.faticc.reauth.auth.AuthException;
import net.faticc.reauth.auth.GameSession;
import net.faticc.reauth.auth.GribLandAuth;
import net.faticc.reauth.auth.McSkillAuth;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiButton;
import net.minecraft.client.gui.GuiScreen;
import net.minecraft.client.gui.GuiTextField;

/**
 * Login form for switching the running client's account. Opened from the
 * button added to the multiplayer screen. Network calls run off the render
 * thread; the resulting session is applied on the next client tick.
 */
public final class GuiAccountSwitch extends GuiScreen {

    private static final int ID_PROVIDER = 1;
    private static final int ID_LOGIN = 2;
    private static final int ID_BACK = 3;

    private final GuiScreen parent;

    private GuiTextField userField;
    private GuiTextField passField;   // displays asterisks only
    private GuiTextField codeField;   // GribLand 2FA
    private GuiTextField clientField; // GribLand client name
    private GuiButton providerButton;
    private GuiButton loginButton;

    private final StringBuilder password = new StringBuilder();
    private int provider = 0; // 0 = MCSkill (priority/default), 1 = GribLand

    private volatile boolean busy;
    private volatile GameSession pending;
    private volatile String pendingError;
    private String status = "";

    public GuiAccountSwitch(GuiScreen parent) {
        this.parent = parent;
    }

    @Override
    public void initGui() {
        Keyboard.enableRepeatEvents(true);
        this.buttonList.clear();

        int cx = this.width / 2;
        userField = new GuiTextField(this.fontRendererObj, cx - 100, 50, 200, 20);
        userField.setMaxStringLength(64);
        String current = Minecraft.getMinecraft().getSession().getUsername();
        userField.setText(current == null ? "" : current);

        passField = new GuiTextField(this.fontRendererObj, cx - 100, 85, 200, 20);
        passField.setMaxStringLength(256);

        codeField = new GuiTextField(this.fontRendererObj, cx - 100, 120, 95, 20);
        codeField.setMaxStringLength(16);
        clientField = new GuiTextField(this.fontRendererObj, cx + 5, 120, 95, 20);
        clientField.setMaxStringLength(64);

        providerButton = new GuiButton(ID_PROVIDER, cx - 100, 150, 95, 20,
                providerLabel());
        loginButton = new GuiButton(ID_LOGIN, cx + 5, 150, 95, 20, "Войти");
        this.buttonList.add(providerButton);
        this.buttonList.add(loginButton);
        this.buttonList.add(new GuiButton(ID_BACK, cx - 100, 185, 200, 20,
                "Назад"));
    }

    @Override
    public void onGuiClosed() {
        Keyboard.enableRepeatEvents(false);
    }

    private boolean isGribland() {
        return provider == 1;
    }

    private String providerLabel() {
        return isGribland() ? "GribLand" : "MCSkill";
    }

    @Override
    protected void actionPerformed(GuiButton button) {
        switch (button.id) {
            case ID_PROVIDER:
                provider = 1 - provider;
                providerButton.displayString = providerLabel();
                break;
            case ID_LOGIN:
                startLogin();
                break;
            case ID_BACK:
                this.mc.displayGuiScreen(parent);
                break;
            default:
                break;
        }
    }

    private void startLogin() {
        if (busy) {
            return;
        }
        final String user = userField.getText().trim();
        final String pass = password.toString();
        final String code = codeField.getText().trim();
        final String client = clientField.getText().trim();
        final String prov = isGribland()
                ? GribLandAuth.PROVIDER : McSkillAuth.PROVIDER;

        busy = true;
        status = "Авторизация...";
        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    pending = Accounts.authenticate(prov, user, pass,
                            code.isEmpty() ? null : code,
                            client.isEmpty() ? null : client);
                } catch (AuthException e) {
                    pendingError = e.isMfa()
                            ? "Требуется код 2FA"
                            : e.getMessage() + " [" + e.code + "]";
                } catch (Throwable e) {
                    pendingError = "Ошибка: " + e.getMessage();
                }
            }
        }, "mcreauth-login");
        t.setDaemon(true);
        t.start();
    }

    @Override
    public void updateScreen() {
        userField.updateCursorCounter();
        passField.updateCursorCounter();
        codeField.updateCursorCounter();
        clientField.updateCursorCounter();

        GameSession done = pending;
        if (done != null) {
            pending = null;
            busy = false;
            try {
                SessionSwapper.apply(done);
                status = "Вошли как " + done.username
                        + " (" + done.provider + ")";
            } catch (Throwable e) {
                status = "Сессия получена, но не применена: " + e.getMessage();
            }
        }
        String err = pendingError;
        if (err != null) {
            pendingError = null;
            busy = false;
            status = err;
        }
    }

    @Override
    protected void keyTyped(char typedChar, int keyCode) {
        if (keyCode == Keyboard.KEY_ESCAPE) {
            this.mc.displayGuiScreen(parent);
            return;
        }
        if (passField.isFocused()) {
            if (keyCode == Keyboard.KEY_BACK) {
                if (password.length() > 0) {
                    password.setLength(password.length() - 1);
                }
            } else if (typedChar >= 32 && typedChar != 127) {
                password.append(typedChar);
            }
            passField.setText(mask(password.length()));
            passField.setCursorPositionEnd();
            return;
        }
        userField.textboxKeyTyped(typedChar, keyCode);
        if (isGribland()) {
            codeField.textboxKeyTyped(typedChar, keyCode);
            clientField.textboxKeyTyped(typedChar, keyCode);
        }
        if (keyCode == Keyboard.KEY_RETURN) {
            startLogin();
        }
    }

    @Override
    protected void mouseClicked(int mouseX, int mouseY, int mouseButton) {
        super.mouseClicked(mouseX, mouseY, mouseButton);
        userField.mouseClicked(mouseX, mouseY, mouseButton);
        passField.mouseClicked(mouseX, mouseY, mouseButton);
        if (isGribland()) {
            codeField.mouseClicked(mouseX, mouseY, mouseButton);
            clientField.mouseClicked(mouseX, mouseY, mouseButton);
        }
    }

    @Override
    public void drawScreen(int mouseX, int mouseY, float partialTicks) {
        drawDefaultBackground();

        int cx = this.width / 2;
        drawCenteredString(this.fontRendererObj, "Смена аккаунта",
                cx, 25, 0xFFFFFF);

        drawString(this.fontRendererObj, "Логин", cx - 100, 40, 0xA0A0A0);
        drawString(this.fontRendererObj, "Пароль", cx - 100, 75, 0xA0A0A0);

        userField.drawTextBox();
        passField.drawTextBox();

        if (isGribland()) {
            drawString(this.fontRendererObj, "Код 2FA", cx - 100, 110, 0xA0A0A0);
            drawString(this.fontRendererObj, "Клиент", cx + 5, 110, 0xA0A0A0);
            codeField.drawTextBox();
            clientField.drawTextBox();
        }

        super.drawScreen(mouseX, mouseY, partialTicks);

        if (status != null && !status.isEmpty()) {
            int color = status.startsWith("Вошли") ? 0x55FF55 : 0xFFAA55;
            drawCenteredString(this.fontRendererObj, status, cx, 212, color);
        }
    }

    @Override
    public boolean doesGuiPauseGame() {
        return false;
    }

    private static String mask(int length) {
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append('*');
        }
        return sb.toString();
    }
}
