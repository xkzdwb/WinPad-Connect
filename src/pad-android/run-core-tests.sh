#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -rf .core-out
mkdir -p .core-out
javac -encoding UTF-8 -d .core-out \
  app/src/main/java/com/padlink/pad/core/Json.java \
  app/src/main/java/com/padlink/pad/core/HostProfile.java \
  app/src/main/java/com/padlink/pad/core/RttStats.java \
  app/src/main/java/com/padlink/pad/core/Throughput.java \
  app/src/main/java/com/padlink/pad/core/FourFingerTapDetector.java \
  app/src/test/java/com/padlink/pad/core/CoreTests.java
java -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -cp .core-out com.padlink.pad.core.CoreTests
