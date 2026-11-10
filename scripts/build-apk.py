"""构建 Win-Pad Connect Pad 的 debug APK（无需 Gradle）。

依赖：Android SDK platforms;android-34 + build-tools;34.0.0，JDK 17。

用法：
    set ANDROID_SDK_ROOT=%LOCALAPPDATA%\\Android\\Sdk
    python scripts\\build-apk.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK = Path(os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or
           Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk")
JAVA_HOME = Path(os.environ.get("JAVA_HOME", r"C:\Program Files\Java\jdk-17.0.1"))
BUILD_TOOLS = SDK / "build-tools" / "34.0.0"
ANDROID_JAR = SDK / "platforms" / "android-34" / "android.jar"
APP = ROOT / "src" / "pad-android" / "app" / "src" / "main"
WORK = Path(os.environ.get("WPC_APK_WORK", Path(tempfile.gettempdir()) / "wpc-apk-work"))
DIST = ROOT / "dist"
VERSION_NAME = "1.0.0"
VERSION_CODE = 1
MIN_SDK = 26
TARGET_SDK = 34


def run(*args: object, **kwargs) -> None:
    cmd = [str(a) for a in args]
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)


def main() -> int:
    for required in (BUILD_TOOLS / "aapt2.exe", BUILD_TOOLS / "d8.bat",
                     BUILD_TOOLS / "apksigner.bat", ANDROID_JAR):
        if not required.exists():
            print(f"缺少 Android SDK 组件：{required}")
            print("请安装 platforms;android-34 与 build-tools;34.0.0，并设置 ANDROID_SDK_ROOT。")
            return 1

    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(APP, WORK / "app")
    app = WORK / "app"
    for name in ("gen", "classes", "dex"):
        (WORK / name).mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["JAVA_HOME"] = str(JAVA_HOME)
    env["PATH"] = str(JAVA_HOME / "bin") + os.pathsep + env.get("PATH", "")

    aapt2 = BUILD_TOOLS / "aapt2.exe"
    res_zip = WORK / "res.zip"
    run(aapt2, "compile", "--dir", app / "res", "-o", res_zip)

    base_apk = WORK / "base.apk"
    gen = WORK / "gen"
    run(
        aapt2, "link",
        "-o", base_apk,
        "-I", ANDROID_JAR,
        "--manifest", app / "AndroidManifest.xml",
        "--java", gen,
        "--min-sdk-version", MIN_SDK,
        "--target-sdk-version", TARGET_SDK,
        "--version-code", VERSION_CODE,
        "--version-name", VERSION_NAME,
        res_zip,
    )

    java_files = sorted((app / "java").rglob("*.java")) + sorted(gen.rglob("R.java"))
    classes = WORK / "classes"
    run(
        JAVA_HOME / "bin" / "javac.exe",
        "--release", "11", "-encoding", "UTF-8",
        "-cp", ANDROID_JAR, "-d", classes, *java_files,
        env=env,
    )

    dex_dir = WORK / "dex"
    run(
        BUILD_TOOLS / "d8.bat",
        "--release", "--min-api", MIN_SDK,
        "--lib", ANDROID_JAR,
        "--output", dex_dir,
        *sorted(classes.rglob("*.class")),
        env=env,
    )

    unsigned = WORK / "unsigned.apk"
    with zipfile.ZipFile(base_apk) as src, zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.write(dex_dir / "classes.dex", "classes.dex")

    aligned = WORK / "aligned.apk"
    run(BUILD_TOOLS / "zipalign.exe", "-f", "-p", "4", unsigned, aligned, env=env)

    keystore = ROOT / "build" / "debug.keystore"
    keystore.parent.mkdir(parents=True, exist_ok=True)
    if not keystore.exists():
        run(
            JAVA_HOME / "bin" / "keytool.exe",
            "-genkeypair", "-v",
            "-keystore", keystore,
            "-storepass", "android", "-keypass", "android",
            "-alias", "androiddebugkey",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
            "-dname", "CN=Android Debug,O=Android,C=US",
            env=env,
        )

    DIST.mkdir(parents=True, exist_ok=True)
    final = DIST / f"Win-Pad-Connect-Pad-{VERSION_NAME}.apk"
    run(
        BUILD_TOOLS / "apksigner.bat", "sign",
        "--ks", keystore,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        "--out", final,
        aligned,
        env=env,
    )
    run(BUILD_TOOLS / "apksigner.bat", "verify", "--print-certs", final, env=env)
    print(f"APK: {final} ({final.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
