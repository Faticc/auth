package net.faticc.reauth.auth;

/** A login failure, carrying a short machine code (e.g. MFA, UNAUTHENTICATED). */
public final class AuthException extends Exception {
    private static final long serialVersionUID = 1L;

    public final String code;

    public AuthException(String message, String code) {
        super(message);
        this.code = code;
    }

    public boolean isMfa() {
        return "MFA".equals(code) || "MFA_INVALID".equals(code);
    }
}
