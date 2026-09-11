---
name: android-build
description: "Build and test Android projects, preferring disposable Docker builds when a host SDK is unavailable. Use for Android build environment setup, Gradle build/test execution, and APK artifact verification."
---

# Android Builds

Follow the [global Android signing requirements](../../AGENTS.md#android-builds)
for development and debug APK builds, including post-build certificate verification.

When an Android project needs an SDK that is unavailable on the host, prefer a
disposable Docker build over installing or modifying a host Android SDK, unless
the repository documents a different build environment or the user requests one.

Before selecting an image, inspect the project for its compile SDK, explicit
build-tools version, Android Gradle Plugin version, Gradle wrapper version, and
required JDK. Do not assume that every Android project uses the latest SDK. Use a
maintained image such as `ghcr.io/cirruslabs/android-sdk:<api>` that contains the
required platform and tools. Pin the image by digest after verifying it when
reproducibility matters.

Run the container as the host UID/GID so generated files are not root-owned. Give
the tools a writable `HOME`, mount the repository at `/workspace`, and persist a
Gradle cache. Prefer a dedicated container cache, rather than the host Gradle
cache, to avoid lock conflicts with host Gradle daemons. A general command is:

    ANDROID_GRADLE_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/android-gradle"
    mkdir -p "$ANDROID_GRADLE_CACHE"
    docker run --rm --init \
      --user "$(id -u):$(id -g)" \
      --env HOME=/tmp \
      --env GRADLE_USER_HOME=/gradle-cache \
      --mount type=bind,src="$PWD",dst=/workspace \
      --mount type=bind,src="$ANDROID_GRADLE_CACHE",dst=/gradle-cache \
      --mount type=bind,src="$HOME/.android/debug.keystore",dst=/tmp/.android/debug.keystore,readonly \
      --workdir /workspace \
      ghcr.io/cirruslabs/android-sdk:<api>@sha256:<digest> \
      bash gradlew --no-daemon test assembleDebug

Adjust Gradle tasks to the project's documented workflow. Running the wrapper
through `bash` also works when `gradlew` is not executable. Add
`--platform linux/amd64` only when the host is AMD64 or the required Android
tools are known to require AMD64; avoid unnecessary emulation on ARM hosts.

Do not force a locale by default. If established tests are locale-sensitive,
pass the required `JAVA_TOOL_OPTIONS` explicitly and report that requirement.
If a shared Gradle cache is locked, identify the owning process and stop the
relevant daemon with the project's wrapper; do not delete lock files blindly.

After a successful build, verify the artifact type, path, size, checksum, and
ownership with tools such as `file`, `stat`, and `sha256sum`. Compare Git status
before and after the build so generated or source changes are not mistaken for
the requested implementation. Report warnings separately from build failures.
