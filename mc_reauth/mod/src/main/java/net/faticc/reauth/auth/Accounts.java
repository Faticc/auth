package net.faticc.reauth.auth;

/**
 * Entry point for the GUI: resolve credentials to a {@link GameSession} via
 * the chosen provider. MCSkill is the priority provider and the GUI's
 * default selection; GribLand is used only when explicitly chosen.
 */
public final class Accounts {

    private Accounts() {
    }

    public static GameSession authenticate(String provider, String username,
                                           String password, String code,
                                           String clientName)
            throws AuthException {
        if (username == null || username.isEmpty()) {
            throw new AuthException("username is empty", "INVALID_ARGUMENT");
        }
        if (GribLandAuth.PROVIDER.equals(provider)) {
            return GribLandAuth.login(username, password, code, clientName);
        }
        return McSkillAuth.login(username, password);
    }
}
