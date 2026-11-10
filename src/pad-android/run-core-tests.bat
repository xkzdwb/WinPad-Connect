@echo off
rem 在无 Android SDK 的机器上验证纯 Java 核心逻辑（Json / profile / RTT / 吞吐建议 / 四指手势）。
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".core-out" rmdir /s /q ".core-out"
mkdir ".core-out"
javac -encoding UTF-8 -d ".core-out" ^
  "app\src\main\java\com\padlink\pad\core\Json.java" ^
  "app\src\main\java\com\padlink\pad\core\HostProfile.java" ^
  "app\src\main\java\com\padlink\pad\core\RttStats.java" ^
  "app\src\main\java\com\padlink\pad\core\Throughput.java" ^
  "app\src\main\java\com\padlink\pad\core\FourFingerTapDetector.java" ^
  "app\src\test\java\com\padlink\pad\core\CoreTests.java"
if errorlevel 1 goto :fail
java -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -cp ".core-out" com.padlink.pad.core.CoreTests
if errorlevel 1 goto :fail
echo.
echo Core tests OK.
exit /b 0

:fail
echo.
echo Core tests FAILED.
exit /b 1
