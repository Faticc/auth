package net.faticc.reauth.auth;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/**
 * GribLand login over the launcher HTTP API. Pure Java (HttpURLConnection +
 * the Gson that ships inside Minecraft 1.7.10), mirroring the repo's Python
 * `gribland_auth` package.
 *
 * Two steps:
 *   1. POST /authentication/login   -> JWT access token
 *   2. GET  /minecraft/createSession/{client} (Bearer) -> game session
 *      (uuid + token + username) the client uses to join servers.
 */
public final class GribLandAuth {

    public static final String PROVIDER = "gribland";

    private static final String[] DOMAINS = {
            "launcher.gribland.net", "launcher-cf.gribland.net"
    };
    private static final String USER_AGENT = "GribLand";
    private static final int TIMEOUT_MS = 10_000;
    private static final String OTP_MARKER = ".otp_";
    private static final String OTP_INCORRECT = "messages.login.otp_incorrect";

    private GribLandAuth() {
    }

    public static GameSession login(String username, String password,
                                    String code, String clientName)
            throws AuthException {
        if (clientName == null || clientName.isEmpty()) {
            throw new AuthException(
                    "client name is required for GribLand "
                            + "(e.g. SKYDRIVE-HITECH-TEST)",
                    "INVALID_ARGUMENT");
        }

        JsonObject body = new JsonObject();
        body.addProperty("ident", username);
        body.addProperty("password", password);
        if (code != null && !code.isEmpty()) {
            body.addProperty("code", code);
        }

        Response login = request("POST", "/authentication/login",
                body.toString(), null);

        if (login.status != 200) {
            String message = errorText(login);
            if (message.contains(OTP_MARKER)) {
                if (message.equals(OTP_INCORRECT)) {
                    throw new AuthException(message, "MFA_INVALID");
                }
                throw new AuthException("MFA required", "MFA");
            }
            throw new AuthException(message, errorCode(login.status));
        }

        String accessToken = str(login.json, "accessToken", "access_token");
        if (accessToken == null) {
            throw new AuthException("Unexpected server response", "UNKNOWN");
        }

        Response session = request("GET",
                "/minecraft/createSession/" + clientName, null, accessToken);
        if (session.status != 200) {
            throw new AuthException(errorText(session),
                    errorCode(session.status));
        }

        JsonObject data = session.json;
        if (data != null && data.has("data") && data.get("data").isJsonObject()) {
            data = data.getAsJsonObject("data");
        }
        String uuid = str(data, "uuid");
        String token = str(data, "accessToken", "access_token");
        String name = str(data, "username", "name");
        if (uuid == null || token == null || name == null) {
            throw new AuthException("Unexpected server response", "UNKNOWN");
        }
        return new GameSession(uuid, token, name, PROVIDER);
    }

    /* ----------------------------- transport --------------------------- */

    private static final class Response {
        final int status;
        final JsonObject json;

        Response(int status, JsonObject json) {
            this.status = status;
            this.json = json;
        }
    }

    private static Response request(String method, String path, String body,
                                    String bearer) throws AuthException {
        AuthException last = null;
        for (String domain : DOMAINS) {
            try {
                return doRequest(domain, method, path, body, bearer);
            } catch (IOException e) {
                last = new AuthException(e.getMessage(), "UNAVAILABLE");
            }
        }
        throw last != null ? last
                : new AuthException("no GribLand host reachable", "UNAVAILABLE");
    }

    private static Response doRequest(String domain, String method, String path,
                                      String body, String bearer)
            throws IOException {
        URL url = new URL("https://" + domain + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(TIMEOUT_MS);
        conn.setReadTimeout(TIMEOUT_MS);
        conn.setRequestMethod(method);
        conn.setRequestProperty("User-Agent", USER_AGENT);
        conn.setRequestProperty("Accept", "application/json");
        if (bearer != null) {
            conn.setRequestProperty("Authorization", "Bearer " + bearer);
        }
        if (body != null) {
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type",
                    "application/json; charset=utf-8");
            byte[] payload = body.getBytes("UTF-8");
            OutputStream os = conn.getOutputStream();
            try {
                os.write(payload);
            } finally {
                os.close();
            }
        }

        int status = conn.getResponseCode();
        InputStream stream = status >= 400 ? conn.getErrorStream()
                : conn.getInputStream();
        String text = readAll(stream);
        return new Response(status, parse(text));
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) {
            return "";
        }
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        try {
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
            }
        } finally {
            in.close();
        }
        return new String(out.toByteArray(), "UTF-8");
    }

    private static JsonObject parse(String text) {
        try {
            JsonElement el = new JsonParser().parse(text);
            if (el.isJsonObject()) {
                return el.getAsJsonObject();
            }
        } catch (RuntimeException ignored) {
            // fall through to a synthetic object below
        }
        JsonObject o = new JsonObject();
        o.addProperty("message",
                text.length() > 200 ? text.substring(0, 200) : text);
        return o;
    }

    /* ----------------------------- helpers ----------------------------- */

    private static String str(JsonObject obj, String... keys) {
        if (obj == null) {
            return null;
        }
        for (String key : keys) {
            if (obj.has(key) && obj.get(key).isJsonPrimitive()) {
                String v = obj.get(key).getAsString();
                if (v != null && !v.isEmpty()) {
                    return v;
                }
            }
        }
        return null;
    }

    private static String errorText(Response r) {
        String m = str(r.json, "message", "error");
        return m != null ? m : "HTTP " + r.status;
    }

    private static String errorCode(int status) {
        switch (status) {
            case 400:
            case 422:
                return "INVALID_ARGUMENT";
            case 401:
                return "UNAUTHENTICATED";
            case 403:
                return "PERMISSION_DENIED";
            case 404:
                return "NOT_FOUND";
            case 429:
                return "RESOURCE_EXHAUSTED";
            default:
                return status >= 500 ? "UNAVAILABLE"
                        : "HTTP_" + status;
        }
    }
}
