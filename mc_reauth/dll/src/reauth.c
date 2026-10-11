/*
 * mc_reauth native DLL
 * --------------------
 * Injected into a running Minecraft (javaw.exe) by the administration tool.
 * On load it:
 *   1. grabs the already-running JVM via JNI_GetCreatedJavaVMs,
 *   2. opens a loopback-only control port (127.0.0.1),
 *   3. on each request, hot-swaps the client's in-memory login session
 *      (username / uuid / access token) so the next server join uses the
 *      new account -- no game restart, no re-opening the admin tool.
 *
 * It touches only the session object of the process it is injected into,
 * using the player's own credentials resolved by the Python side against
 * the user's own servers (MCSkill / GribLand). It is an account switcher,
 * not an exploit: it adds no capability a normal re-login would not grant.
 *
 * Session detection is version-tolerant. The 1.7.10 / 1.8.9 / 1.12.2
 * net.minecraft.util.Session class holds exactly three String fields
 * (username, playerID, token); because Forge keeps those *class* names
 * readable at runtime (only field names are SRG-obfuscated), the fields
 * are classified by the SHAPE of their current values rather than by
 * their obfuscated names, so no per-version name table is required. An
 * optional reauth.ini lets the operator pin exact field names for any
 * other client.
 */

#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#include "jni.h"
#include "jvmti.h"

#define DEFAULT_PORT 5151
#define ACC_STATIC 0x0008
#define MAX_STR 1024

static JavaVM *g_vm = NULL;
static HMODULE g_self = NULL;
static volatile LONG g_stop = 0;
static SOCKET g_listen = INVALID_SOCKET;

/* ------------------------------------------------------------------ */
/* logging                                                            */
/* ------------------------------------------------------------------ */

static void log_line(const char *fmt, ...) {
    char buf[1200];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf(buf, sizeof(buf) - 2, fmt, ap);
    va_end(ap);
    buf[sizeof(buf) - 2] = 0;
    strcat(buf, "\n");

    OutputDebugStringA(buf);

    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(g_self, path, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        char *slash = strrchr(path, '\\');
        if (slash) {
            strcpy(slash + 1, "mc_reauth.log");
            FILE *f = fopen(path, "a");
            if (f) {
                fputs(buf, f);
                fclose(f);
            }
        }
    }
}

/* ------------------------------------------------------------------ */
/* config                                                             */
/* ------------------------------------------------------------------ */

static int read_port(void) {
    char *env = getenv("MC_REAUTH_PORT");
    if (env && *env) {
        int p = atoi(env);
        if (p > 0 && p < 65536) {
            return p;
        }
    }
    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(g_self, path, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        char *slash = strrchr(path, '\\');
        if (slash) {
            strcpy(slash + 1, "reauth.ini");
            int p = GetPrivateProfileIntA("reauth", "port", 0, path);
            if (p > 0 && p < 65536) {
                return p;
            }
        }
    }
    return DEFAULT_PORT;
}

/* Optional explicit field-name override from reauth.ini, e.g.
 *   [session]
 *   username=field_74286_a
 *   uuid=field_74287_b
 *   token=field_74285_c
 * Empty when not configured. */
static void read_override(const char *key, char *out, size_t outsz) {
    out[0] = 0;
    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(g_self, path, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        char *slash = strrchr(path, '\\');
        if (slash) {
            strcpy(slash + 1, "reauth.ini");
            GetPrivateProfileStringA("session", key, "", out,
                                     (DWORD)outsz, path);
        }
    }
}

/* ------------------------------------------------------------------ */
/* tiny JSON (flat {"k":"v"} objects only)                            */
/* ------------------------------------------------------------------ */

static int json_get(const char *src, const char *key,
                    char *out, size_t outsz) {
    char pat[64];
    _snprintf(pat, sizeof(pat), "\"%s\"", key);
    pat[sizeof(pat) - 1] = 0;

    const char *p = strstr(src, pat);
    if (!p) {
        return 0;
    }
    p += strlen(pat);
    while (*p && *p != ':') {
        p++;
    }
    if (*p != ':') {
        return 0;
    }
    p++;
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    if (*p != '"') {
        return 0;
    }
    p++;

    size_t i = 0;
    while (*p && *p != '"' && i + 1 < outsz) {
        if (*p == '\\' && p[1]) {
            p++;
            switch (*p) {
                case 'n': out[i++] = '\n'; break;
                case 't': out[i++] = '\t'; break;
                case 'r': out[i++] = '\r'; break;
                default:  out[i++] = *p;   break;
            }
        } else {
            out[i++] = *p;
        }
        p++;
    }
    out[i] = 0;
    return 1;
}

/* ------------------------------------------------------------------ */
/* value-shape classifiers                                            */
/* ------------------------------------------------------------------ */

static int looks_like_uuid(const char *s) {
    size_t len = strlen(s);
    size_t hex = 0;
    size_t i;
    if (len == 32) {
        for (i = 0; i < len; i++) {
            if (isxdigit((unsigned char)s[i])) {
                hex++;
            }
        }
        return hex == 32;
    }
    if (len == 36) {
        for (i = 0; i < len; i++) {
            if (i == 8 || i == 13 || i == 18 || i == 23) {
                if (s[i] != '-') {
                    return 0;
                }
            } else if (!isxdigit((unsigned char)s[i])) {
                return 0;
            }
        }
        return 1;
    }
    return 0;
}

static int looks_like_username(const char *s) {
    size_t len = strlen(s);
    size_t i;
    if (len < 1 || len > 16) {
        return 0;
    }
    for (i = 0; i < len; i++) {
        char c = s[i];
        if (!(isalnum((unsigned char)c) || c == '_')) {
            return 0;
        }
    }
    return 1;
}

/* ------------------------------------------------------------------ */
/* JVMTI helpers                                                      */
/* ------------------------------------------------------------------ */

static jvmtiEnv *get_jvmti(void) {
    jvmtiEnv *jvmti = NULL;
    if ((*g_vm)->GetEnv(g_vm, (void **)&jvmti, JVMTI_VERSION_1_0) != JNI_OK) {
        return NULL;
    }
    return jvmti;
}

/* Find a loaded class by its JVM type signature (e.g.
 * "Lnet/minecraft/util/Session;"). Returns a local ref or NULL. */
static jclass find_class_by_sig(jvmtiEnv *jvmti, JNIEnv *env,
                                const char *want) {
    jint count = 0;
    jclass *classes = NULL;
    jclass found = NULL;
    jint i;

    if ((*jvmti)->GetLoadedClasses(jvmti, &count, &classes)
            != JVMTI_ERROR_NONE) {
        return NULL;
    }
    for (i = 0; i < count; i++) {
        char *sig = NULL;
        if ((*jvmti)->GetClassSignature(jvmti, classes[i], &sig, NULL)
                == JVMTI_ERROR_NONE && sig) {
            if (!found && strcmp(sig, want) == 0) {
                found = (*env)->NewLocalRef(env, classes[i]);
            }
            (*jvmti)->Deallocate(jvmti, (unsigned char *)sig);
        }
    }
    (*jvmti)->Deallocate(jvmti, (unsigned char *)classes);
    return found;
}

/* Locate the Minecraft client singleton via its static self-referencing
 * field (Minecraft.theMinecraft / field_71432_P on 1.7.10). */
static jobject find_singleton(jvmtiEnv *jvmti, JNIEnv *env,
                              jclass klass, const char *selfSig) {
    jint fcount = 0;
    jfieldID *fields = NULL;
    jobject inst = NULL;
    jint i;

    if ((*jvmti)->GetClassFields(jvmti, klass, &fcount, &fields)
            != JVMTI_ERROR_NONE) {
        return NULL;
    }
    for (i = 0; i < fcount && !inst; i++) {
        char *name = NULL;
        char *sig = NULL;
        jint mods = 0;
        if ((*jvmti)->GetFieldName(jvmti, klass, fields[i], &name, &sig, NULL)
                == JVMTI_ERROR_NONE) {
            (*jvmti)->GetFieldModifiers(jvmti, klass, fields[i], &mods);
            if (sig && name && strcmp(sig, selfSig) == 0
                    && (mods & ACC_STATIC)) {
                jfieldID sfid = (*env)->GetStaticFieldID(env, klass, name, sig);
                if (sfid) {
                    jobject o = (*env)->GetStaticObjectField(env, klass, sfid);
                    if (o) {
                        inst = o;
                    }
                }
            }
        }
        if (name) (*jvmti)->Deallocate(jvmti, (unsigned char *)name);
        if (sig)  (*jvmti)->Deallocate(jvmti, (unsigned char *)sig);
    }
    (*jvmti)->Deallocate(jvmti, (unsigned char *)fields);
    return inst;
}

/* Get the object held by the first instance field of `klass` whose
 * signature equals `want` (e.g. the Session field inside Minecraft). */
static jobject get_field_obj_by_sig(jvmtiEnv *jvmti, JNIEnv *env,
                                    jclass klass, jobject inst,
                                    const char *want) {
    jint fcount = 0;
    jfieldID *fields = NULL;
    jobject result = NULL;
    jint i;

    if ((*jvmti)->GetClassFields(jvmti, klass, &fcount, &fields)
            != JVMTI_ERROR_NONE) {
        return NULL;
    }
    for (i = 0; i < fcount && !result; i++) {
        char *name = NULL;
        char *sig = NULL;
        jint mods = 0;
        if ((*jvmti)->GetFieldName(jvmti, klass, fields[i], &name, &sig, NULL)
                == JVMTI_ERROR_NONE) {
            (*jvmti)->GetFieldModifiers(jvmti, klass, fields[i], &mods);
            if (sig && name && strcmp(sig, want) == 0
                    && !(mods & ACC_STATIC)) {
                jfieldID fid = (*env)->GetFieldID(env, klass, name, sig);
                if (fid) {
                    result = (*env)->GetObjectField(env, inst, fid);
                }
            }
        }
        if (name) (*jvmti)->Deallocate(jvmti, (unsigned char *)name);
        if (sig)  (*jvmti)->Deallocate(jvmti, (unsigned char *)sig);
    }
    (*jvmti)->Deallocate(jvmti, (unsigned char *)fields);
    return result;
}

static void set_string_field(JNIEnv *env, jobject obj, jfieldID fid,
                             const char *value) {
    jstring js = (*env)->NewStringUTF(env, value);
    (*env)->SetObjectField(env, obj, fid, js);
    (*env)->DeleteLocalRef(env, js);
}

/* ------------------------------------------------------------------ */
/* the actual session swap                                            */
/* ------------------------------------------------------------------ */

/* Collected info about one String field of the session object. */
typedef struct {
    jfieldID fid;
    char name[128];
    char value[MAX_STR];
    int has_value;
} StrField;

static const char *apply_session(JNIEnv *env,
                                 const char *uuid,
                                 const char *token,
                                 const char *username) {
    jvmtiEnv *jvmti = get_jvmti();
    if (!jvmti) {
        return NULL; /* caller reports generic failure */
    }

    (*env)->PushLocalFrame(env, 512);

    const char *strategy = NULL;

    jclass mcClass = find_class_by_sig(jvmti, env,
                                       "Lnet/minecraft/client/Minecraft;");
    if (!mcClass) {
        /* Yarn-mapped / newer naming. */
        mcClass = find_class_by_sig(jvmti, env,
                                    "Lnet/minecraft/client/MinecraftClient;");
    }
    if (!mcClass) {
        log_line("[apply] Minecraft class not found among loaded classes");
        (*env)->PopLocalFrame(env, NULL);
        return NULL;
    }

    char mcSig[256];
    {
        char *s = NULL;
        if ((*jvmti)->GetClassSignature(jvmti, mcClass, &s, NULL)
                == JVMTI_ERROR_NONE && s) {
            strncpy(mcSig, s, sizeof(mcSig) - 1);
            mcSig[sizeof(mcSig) - 1] = 0;
            (*jvmti)->Deallocate(jvmti, (unsigned char *)s);
        } else {
            strcpy(mcSig, "Lnet/minecraft/client/Minecraft;");
        }
    }

    jobject mc = find_singleton(jvmti, env, mcClass, mcSig);
    if (!mc) {
        log_line("[apply] Minecraft singleton instance not found");
        (*env)->PopLocalFrame(env, NULL);
        return NULL;
    }

    /* Find the session object. Try the classic Session, then newer User. */
    jobject session = get_field_obj_by_sig(jvmti, env, mcClass, mc,
                                           "Lnet/minecraft/util/Session;");
    if (!session) {
        session = get_field_obj_by_sig(jvmti, env, mcClass, mc,
                                       "Lnet/minecraft/client/User;");
    }
    if (!session) {
        log_line("[apply] session/user field not found on Minecraft");
        (*env)->PopLocalFrame(env, NULL);
        return NULL;
    }

    jclass sClass = (*env)->GetObjectClass(env, session);

    /* Gather all instance String fields and their current values. */
    jint fcount = 0;
    jfieldID *fields = NULL;
    if ((*jvmti)->GetClassFields(jvmti, sClass, &fcount, &fields)
            != JVMTI_ERROR_NONE) {
        (*env)->PopLocalFrame(env, NULL);
        return NULL;
    }

    StrField sf[32];
    int sfn = 0;
    jint i;
    for (i = 0; i < fcount && sfn < 32; i++) {
        char *name = NULL;
        char *sig = NULL;
        jint mods = 0;
        if ((*jvmti)->GetFieldName(jvmti, sClass, fields[i], &name, &sig, NULL)
                == JVMTI_ERROR_NONE) {
            (*jvmti)->GetFieldModifiers(jvmti, sClass, fields[i], &mods);
            if (sig && name && !(mods & ACC_STATIC)
                    && strcmp(sig, "Ljava/lang/String;") == 0) {
                jfieldID fid = (*env)->GetFieldID(env, sClass, name, sig);
                if (fid) {
                    StrField *e = &sf[sfn++];
                    e->fid = fid;
                    strncpy(e->name, name, sizeof(e->name) - 1);
                    e->name[sizeof(e->name) - 1] = 0;
                    e->value[0] = 0;
                    e->has_value = 0;
                    jstring cur = (*env)->GetObjectField(env, session, fid);
                    if (cur) {
                        const char *c =
                            (*env)->GetStringUTFChars(env, cur, NULL);
                        if (c) {
                            strncpy(e->value, c, sizeof(e->value) - 1);
                            e->value[sizeof(e->value) - 1] = 0;
                            e->has_value = 1;
                            (*env)->ReleaseStringUTFChars(env, cur, c);
                        }
                        (*env)->DeleteLocalRef(env, cur);
                    }
                }
            }
        }
        if (name) (*jvmti)->Deallocate(jvmti, (unsigned char *)name);
        if (sig)  (*jvmti)->Deallocate(jvmti, (unsigned char *)sig);
    }
    (*jvmti)->Deallocate(jvmti, (unsigned char *)fields);

    /* 1) explicit field-name overrides from reauth.ini win if present. */
    char ovUser[128], ovUuid[128], ovToken[128];
    read_override("username", ovUser, sizeof(ovUser));
    read_override("uuid", ovUuid, sizeof(ovUuid));
    read_override("token", ovToken, sizeof(ovToken));

    int idxUser = -1, idxUuid = -1, idxToken = -1;
    int j;

    if (ovUser[0] || ovUuid[0] || ovToken[0]) {
        for (j = 0; j < sfn; j++) {
            if (ovUser[0] && strcmp(sf[j].name, ovUser) == 0)  idxUser = j;
            if (ovUuid[0] && strcmp(sf[j].name, ovUuid) == 0)  idxUuid = j;
            if (ovToken[0] && strcmp(sf[j].name, ovToken) == 0) idxToken = j;
        }
        strategy = "ini-override";
    }

    /* 2) readable-name heuristic (dev/mojmap builds). */
    if (idxUser < 0 || idxUuid < 0 || idxToken < 0) {
        for (j = 0; j < sfn; j++) {
            char low[128];
            size_t k;
            for (k = 0; sf[j].name[k] && k < sizeof(low) - 1; k++) {
                low[k] = (char)tolower((unsigned char)sf[j].name[k]);
            }
            low[k] = 0;
            if (idxUuid < 0 && (strstr(low, "uuid") || strstr(low, "playerid")
                    || strcmp(low, "id") == 0)) {
                idxUuid = j;
            } else if (idxToken < 0 && (strstr(low, "token")
                    || strstr(low, "session"))) {
                idxToken = j;
            } else if (idxUser < 0 && (strstr(low, "name")
                    || strstr(low, "user"))) {
                idxUser = j;
            }
        }
        if (strategy == NULL
                && (idxUser >= 0 && idxUuid >= 0 && idxToken >= 0)) {
            strategy = "name-heuristic";
        }
    }

    /* 3) value-shape classification -- the version-tolerant default for
     *    the classic 3-String Session (names are SRG-obfuscated there). */
    if (idxUser < 0 || idxUuid < 0 || idxToken < 0) {
        for (j = 0; j < sfn; j++) {
            if (!sf[j].has_value) {
                continue;
            }
            if (idxUuid < 0 && looks_like_uuid(sf[j].value)) {
                idxUuid = j;
            }
        }
        for (j = 0; j < sfn; j++) {
            if (j == idxUuid || !sf[j].has_value) {
                continue;
            }
            if (idxUser < 0 && looks_like_username(sf[j].value)) {
                idxUser = j;
            }
        }
        /* The remaining String field (classic Session has exactly one
         * left over) is the access token. */
        if (sfn == 3) {
            for (j = 0; j < sfn; j++) {
                if (j != idxUuid && j != idxUser) {
                    if (idxToken < 0) {
                        idxToken = j;
                    }
                }
            }
        }
        if (strategy == NULL) {
            strategy = "value-shape";
        }
    }

    if (idxUser < 0 && idxUuid < 0 && idxToken < 0) {
        log_line("[apply] could not classify any session field (%d strings)",
                 sfn);
        (*env)->PopLocalFrame(env, NULL);
        return NULL;
    }

    if (idxUser >= 0)  set_string_field(env, session, sf[idxUser].fid, username);
    if (idxUuid >= 0)  set_string_field(env, session, sf[idxUuid].fid, uuid);
    if (idxToken >= 0) set_string_field(env, session, sf[idxToken].fid, token);

    log_line("[apply] strategy=%s user=%s(%s) uuid=%s(%s) token=%s(%s)",
             strategy, username,
             idxUser >= 0 ? sf[idxUser].name : "?",
             uuid,
             idxUuid >= 0 ? sf[idxUuid].name : "?",
             "<redacted>",
             idxToken >= 0 ? sf[idxToken].name : "?");

    (*env)->PopLocalFrame(env, NULL);
    return strategy;
}

/* ------------------------------------------------------------------ */
/* control server                                                     */
/* ------------------------------------------------------------------ */

static void send_all(SOCKET s, const char *buf, int len) {
    int off = 0;
    while (off < len) {
        int n = send(s, buf + off, len - off, 0);
        if (n <= 0) {
            break;
        }
        off += n;
    }
}

static void handle_client(JNIEnv *env, SOCKET c) {
    char req[4096];
    int total = 0;
    for (;;) {
        int n = recv(c, req + total, (int)sizeof(req) - 1 - total, 0);
        if (n <= 0) {
            break;
        }
        total += n;
        req[total] = 0;
        if (strchr(req, '\n') || total >= (int)sizeof(req) - 1) {
            break;
        }
    }
    if (total <= 0) {
        return;
    }
    req[total] = 0;

    char uuid[MAX_STR], token[MAX_STR], username[MAX_STR];
    int ok = json_get(req, "uuid", uuid, sizeof(uuid))
           & json_get(req, "accessToken", token, sizeof(token))
           & json_get(req, "username", username, sizeof(username));

    char reply[1024];
    if (!ok) {
        _snprintf(reply, sizeof(reply),
                  "{\"ok\":false,\"error\":\"missing uuid/accessToken/username\"}\n");
        send_all(c, reply, (int)strlen(reply));
        return;
    }

    const char *strategy = apply_session(env, uuid, token, username);
    if (strategy) {
        _snprintf(reply, sizeof(reply),
                  "{\"ok\":true,\"username\":\"%s\",\"strategy\":\"%s\"}\n",
                  username, strategy);
    } else {
        _snprintf(reply, sizeof(reply),
                  "{\"ok\":false,\"error\":\"could not locate or update the "
                  "Minecraft session object\"}\n");
    }
    reply[sizeof(reply) - 1] = 0;
    send_all(c, reply, (int)strlen(reply));
}

static DWORD WINAPI worker(LPVOID param) {
    (void)param;

    /* Wait for jvm.dll + a live VM (we may be injected very early). */
    int tries;
    for (tries = 0; tries < 600 && !g_stop; tries++) {
        HMODULE jvm = GetModuleHandleA("jvm.dll");
        if (jvm) {
            typedef jint (JNICALL *GetVMs_t)(JavaVM **, jsize, jsize *);
            GetVMs_t fn =
                (GetVMs_t)(void *)GetProcAddress(jvm,
                                                 "JNI_GetCreatedJavaVMs");
            if (fn) {
                JavaVM *vms[4];
                jsize n = 0;
                if (fn(vms, 4, &n) == JNI_OK && n > 0) {
                    g_vm = vms[0];
                    break;
                }
            }
        }
        Sleep(100);
    }
    if (!g_vm) {
        log_line("[worker] no JVM found; giving up");
        return 0;
    }

    JNIEnv *env = NULL;
    if ((*g_vm)->AttachCurrentThread(g_vm, (void **)&env, NULL) != JNI_OK
            || !env) {
        log_line("[worker] AttachCurrentThread failed");
        return 0;
    }

    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        log_line("[worker] WSAStartup failed");
        (*g_vm)->DetachCurrentThread(g_vm);
        return 0;
    }

    int port = read_port();
    g_listen = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_listen == INVALID_SOCKET) {
        log_line("[worker] socket() failed");
        goto done;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK); /* 127.0.0.1 only */

    if (bind(g_listen, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        log_line("[worker] bind(127.0.0.1:%d) failed (err=%d)",
                 port, WSAGetLastError());
        goto done;
    }
    if (listen(g_listen, 4) != 0) {
        log_line("[worker] listen failed");
        goto done;
    }

    log_line("[worker] ready: control on 127.0.0.1:%d", port);

    while (!g_stop) {
        SOCKET c = accept(g_listen, NULL, NULL);
        if (c == INVALID_SOCKET) {
            if (g_stop) {
                break;
            }
            Sleep(50);
            continue;
        }
        handle_client(env, c);
        closesocket(c);
    }

done:
    if (g_listen != INVALID_SOCKET) {
        closesocket(g_listen);
        g_listen = INVALID_SOCKET;
    }
    WSACleanup();
    (*g_vm)->DetachCurrentThread(g_vm);
    log_line("[worker] stopped");
    return 0;
}

/* ------------------------------------------------------------------ */
/* entry point                                                        */
/* ------------------------------------------------------------------ */

BOOL APIENTRY DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved) {
    (void)reserved;
    switch (reason) {
        case DLL_PROCESS_ATTACH:
            g_self = (HMODULE)inst;
            DisableThreadLibraryCalls(inst);
            CreateThread(NULL, 0, worker, NULL, 0, NULL);
            break;
        case DLL_PROCESS_DETACH:
            g_stop = 1;
            if (g_listen != INVALID_SOCKET) {
                closesocket(g_listen);
            }
            break;
        default:
            break;
    }
    return TRUE;
}
