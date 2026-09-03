"""Pinned versions, download URLs and checksums for Easy-R5.

Single source of truth. Pure stdlib-free constants — imported by algorithms,
``java_env`` and the test suite, so it must have no side effects and no imports.

Upgrading R5 or Java is a deliberate, tested change (ADR-0002). Bump the numbers
here, recompute ``R5_JAR_SHA256`` and re-run the M1 acceptance checks.
"""

# --- R5 engine (ADR-0002) ---------------------------------------------------
R5_VERSION = "7.6"
R5_JAR_FILENAME = "r5-v7.6-all.jar"
R5_JAR_URL = (
    "https://github.com/conveyal/r5/releases/download/v7.6/r5-v7.6-all.jar"
)
# Conveyal publishes only .md5/.sha1 for the release asset. This SHA-256 was
# computed once from the official jar and cross-checked against the published
# .sha1 (63e5d0df5fede001e48b58f2804a5e0b76f1806b). Never weaken to MD5.
R5_JAR_SHA256 = "8bf56cd06964c42ff4b776977d3c39118692bdf3349dc01959d899ec20fb289e"  # pragma: allowlist secret
R5_JAR_MIN_BYTES = 55 * 1024 * 1024
R5_JAR_MAX_BYTES = 80 * 1024 * 1024
# The network.dat format string this R5 build reads/writes
# (KryoNetworkSerializer.NETWORK_FORMAT_VERSION). Networks in any other format
# fail to load with an intelligible error — that is expected, not a bug.
R5_NETWORK_FORMAT_VERSION = "nv5"

# --- Java runtime (ADR-0001/0002) -----------------------------------------
# JDK, not JRE: the runner is compiled with javac at setup time.
JDK_FEATURE_VERSION = 21
JDK_IMAGE_TYPE = "jdk"
# Adoptium v3 "latest" assets endpoint. x64 only (see DownloadR5); arm64 users
# are pointed at a manual download.
ADOPTIUM_LATEST_URL = (
    "https://api.adoptium.net/v3/assets/latest/{feature}/hotspot"
    "?architecture=x64&image_type={image}&os={os}&vendor=eclipse"
)

# --- Runner ---------------------------------------------------------------
RUNNER_MAIN_CLASS = "EasyR5Runner"
RUNNER_SOURCE_FILENAME = "EasyR5Runner.java"

USER_AGENT = "easy-R5/0.1.0"
