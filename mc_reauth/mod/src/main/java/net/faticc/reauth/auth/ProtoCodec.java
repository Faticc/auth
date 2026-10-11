package net.faticc.reauth.auth;

import java.io.ByteArrayOutputStream;
import java.io.UnsupportedEncodingException;

/**
 * Hand-rolled protobuf (proto3) reader/writer for the handful of MCSkill auth
 * messages the mod needs. Using this instead of a generated protobuf runtime
 * keeps the shaded dependency set tiny (only grpc, no protobuf-java) and
 * avoids running protoc at build time.
 *
 * Only the wire types used by these messages are implemented:
 *   0 = varint, 2 = length-delimited (string / embedded message).
 * Unknown fields are skipped so forward-compatible server changes do not break
 * decoding.
 */
public final class ProtoCodec {

    private ProtoCodec() {
    }

    /* ----------------------------- writing ----------------------------- */

    public static byte[] encodeLoginRequest(String username, String password) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        writeString(out, 1, username);
        writeString(out, 2, password);
        return out.toByteArray();
    }

    private static void writeString(ByteArrayOutputStream out, int field,
                                    String value) {
        if (value == null) {
            return;
        }
        byte[] bytes = utf8(value);
        writeVarint(out, ((long) field << 3) | 2);
        writeVarint(out, bytes.length);
        out.write(bytes, 0, bytes.length);
    }

    private static void writeVarint(ByteArrayOutputStream out, long value) {
        while (true) {
            if ((value & ~0x7FL) == 0) {
                out.write((int) value);
                return;
            }
            out.write(((int) value & 0x7F) | 0x80);
            value >>>= 7;
        }
    }

    private static byte[] utf8(String s) {
        try {
            return s.getBytes("UTF-8");
        } catch (UnsupportedEncodingException e) {
            throw new RuntimeException(e); // UTF-8 is always available
        }
    }

    /* ----------------------------- reading ----------------------------- */

    /** Parsed LoginResponse. Exactly one of (session) or (mfaRequired) is set. */
    public static final class LoginResult {
        public String sessionId;
        public String uuid;
        public String username;
        public boolean mfaRequired;

        public boolean hasSession() {
            return sessionId != null;
        }
    }

    public static LoginResult decodeLoginResponse(byte[] data) {
        LoginResult result = new LoginResult();
        Reader r = new Reader(data, 0, data.length);
        while (r.hasMore()) {
            long tag = r.readVarint();
            int field = (int) (tag >>> 3);
            int wire = (int) (tag & 7);
            if (field == 3 && wire == 2) {           // session_data
                byte[] sub = r.readBytes();
                parseSession(sub, result);
            } else if (field == 4 && wire == 2) {    // mfa_required
                r.readBytes();
                result.mfaRequired = true;
            } else {
                r.skip(wire);
            }
        }
        return result;
    }

    private static void parseSession(byte[] data, LoginResult result) {
        Reader r = new Reader(data, 0, data.length);
        while (r.hasMore()) {
            long tag = r.readVarint();
            int field = (int) (tag >>> 3);
            int wire = (int) (tag & 7);
            if (field == 1 && wire == 2) {           // id
                result.sessionId = r.readString();
            } else if (field == 2 && wire == 2) {    // profile
                parseProfile(r.readBytes(), result);
            } else {
                r.skip(wire);
            }
        }
    }

    private static void parseProfile(byte[] data, LoginResult result) {
        Reader r = new Reader(data, 0, data.length);
        while (r.hasMore()) {
            long tag = r.readVarint();
            int field = (int) (tag >>> 3);
            int wire = (int) (tag & 7);
            if (field == 1 && wire == 2) {           // uuid
                result.uuid = r.readString();
            } else if (field == 2 && wire == 2) {    // username
                result.username = r.readString();
            } else {
                r.skip(wire);                        // skin_url etc.
            }
        }
    }

    /** Minimal cursor over a protobuf byte buffer. */
    private static final class Reader {
        private final byte[] buf;
        private int pos;
        private final int end;

        Reader(byte[] buf, int pos, int end) {
            this.buf = buf;
            this.pos = pos;
            this.end = end;
        }

        boolean hasMore() {
            return pos < end;
        }

        long readVarint() {
            long value = 0;
            int shift = 0;
            while (pos < end) {
                byte b = buf[pos++];
                value |= (long) (b & 0x7F) << shift;
                if ((b & 0x80) == 0) {
                    return value;
                }
                shift += 7;
            }
            throw new IllegalStateException("truncated varint");
        }

        byte[] readBytes() {
            int len = (int) readVarint();
            if (len < 0 || pos + len > end) {
                throw new IllegalStateException("bad length-delimited field");
            }
            byte[] out = new byte[len];
            System.arraycopy(buf, pos, out, 0, len);
            pos += len;
            return out;
        }

        String readString() {
            byte[] b = readBytes();
            try {
                return new String(b, "UTF-8");
            } catch (UnsupportedEncodingException e) {
                throw new RuntimeException(e);
            }
        }

        void skip(int wire) {
            switch (wire) {
                case 0:
                    readVarint();
                    break;
                case 1:
                    pos += 8;
                    break;
                case 2:
                    // Two statements on purpose: readVarint() advances pos as
                    // it reads the length, and `pos += readVarint()` would
                    // capture the old pos before that advance (off-by-one).
                    int len = (int) readVarint();
                    pos += len;
                    break;
                case 5:
                    pos += 4;
                    break;
                default:
                    throw new IllegalStateException("unknown wire type " + wire);
            }
            if (pos > end) {
                throw new IllegalStateException("overran buffer");
            }
        }
    }
}
