package net.faticc.reauth.auth;

/**
 * Provider-neutral result of a login: exactly what the Minecraft client needs
 * to authenticate a server join (the Yggdrasil joinServer / hasJoined pair).
 */
public final class GameSession {
    public final String uuid;
    public final String accessToken;
    public final String username;
    public final String provider;

    public GameSession(String uuid, String accessToken, String username,
                       String provider) {
        this.uuid = uuid;
        this.accessToken = accessToken;
        this.username = username;
        this.provider = provider;
    }
}
