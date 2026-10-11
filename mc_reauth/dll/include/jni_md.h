/*
 * Windows machine-dependent JNI definitions (equivalent to the win32
 * jni_md.h shipped with a Windows JDK). The cross-compiled DLL targets
 * Windows, so the platform JDK's own linux/jni_md.h must not be used.
 *
 * On Win64 (LLP64) `long` is 32-bit, which is the correct width for jint;
 * __stdcall is ignored by the single x64 calling convention and is the
 * right convention on x86, so this header is correct for both bitnesses.
 */

#ifndef _JAVASOFT_JNI_MD_H_
#define _JAVASOFT_JNI_MD_H_

#define JNIEXPORT __declspec(dllexport)
#define JNIIMPORT __declspec(dllimport)
#define JNICALL __stdcall

typedef long jint;
typedef __int64 jlong;
typedef signed char jbyte;

#endif /* !_JAVASOFT_JNI_MD_H_ */
