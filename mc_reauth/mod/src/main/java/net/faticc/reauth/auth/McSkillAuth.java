package net.faticc.reauth.auth;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.concurrent.TimeUnit;

import io.grpc.CallOptions;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.MethodDescriptor;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.ClientCalls;

/**
 * MCSkill login over gRPC/TLS, implemented directly against grpc-java with
 * raw byte[] marshallers (no generated protobuf classes). Mirrors the
 * behaviour of the repo's Python `auth` package.
 *
 * Endpoint and message layout come from mcproto:
 *   launchernew.mcskill.ru:443  (TLS)
 *   launcher.AuthService/Login(LoginRequest) -> LoginResponse
 */
public final class McSkillAuth {

    public static final String PROVIDER = "mcskill";

    private static final String HOST = "launchernew.mcskill.ru";
    private static final int PORT = 443;
    private static final long DEADLINE_SECONDS = 15;

    private static final MethodDescriptor.Marshaller<byte[]> BYTES =
            new MethodDescriptor.Marshaller<byte[]>() {
                @Override
                public InputStream stream(byte[] value) {
                    return new ByteArrayInputStream(value);
                }

                @Override
                public byte[] parse(InputStream stream) {
                    try {
                        return readAll(stream);
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                }
            };

    private static final MethodDescriptor<byte[], byte[]> LOGIN =
            MethodDescriptor.<byte[], byte[]>newBuilder()
                    .setType(MethodDescriptor.MethodType.UNARY)
                    .setFullMethodName(MethodDescriptor.generateFullMethodName(
                            "launcher.AuthService", "Login"))
                    .setRequestMarshaller(BYTES)
                    .setResponseMarshaller(BYTES)
                    .build();

    private McSkillAuth() {
    }

    public static GameSession login(String username, String password)
            throws AuthException {
        byte[] request = ProtoCodec.encodeLoginRequest(username, password);

        ManagedChannel channel = ManagedChannelBuilder
                .forAddress(HOST, PORT)
                .useTransportSecurity()
                .build();
        try {
            byte[] response = ClientCalls.blockingUnaryCall(
                    channel,
                    LOGIN,
                    CallOptions.DEFAULT.withDeadlineAfter(
                            DEADLINE_SECONDS, TimeUnit.SECONDS),
                    request);

            ProtoCodec.LoginResult result =
                    ProtoCodec.decodeLoginResponse(response);

            if (result.mfaRequired) {
                throw new AuthException("MFA required", "MFA");
            }
            if (!result.hasSession() || result.uuid == null
                    || result.username == null) {
                throw new AuthException("Unexpected server response", "UNKNOWN");
            }
            return new GameSession(result.uuid, result.sessionId,
                    result.username, PROVIDER);

        } catch (StatusRuntimeException e) {
            String code = e.getStatus().getCode().name();
            String desc = e.getStatus().getDescription();
            throw new AuthException(desc != null ? desc : code, code);
        } finally {
            channel.shutdownNow();
            try {
                channel.awaitTermination(2, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) != -1) {
            out.write(buf, 0, n);
        }
        return out.toByteArray();
    }
}
