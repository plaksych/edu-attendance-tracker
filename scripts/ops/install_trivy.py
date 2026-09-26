"""Install the reviewed Linux CI scanner from a checksum-pinned release archive."""

import hashlib
import io
from pathlib import Path
import sys
import tarfile
from urllib.request import urlopen

VERSION = "0.74.0"
SHA256 = "2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a"
URL = f"https://github.com/aquasecurity/trivy/releases/download/v{VERSION}/trivy_{VERSION}_Linux-64bit.tar.gz"


def install(destination):
    with urlopen(URL, timeout=60) as response:
        content = response.read(128 * 1024 * 1024 + 1)
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise ValueError("Trivy release archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        member = archive.getmember("trivy")
        if not member.isfile() or member.size > 256 * 1024 * 1024:
            raise ValueError("Invalid scanner archive member")
        with archive.extractfile(member) as source:
            executable = source.read()
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "trivy"
    path.write_bytes(executable)
    path.chmod(0o755)
    print(f"Installed Trivy {VERSION}; verified archive SHA-256 {SHA256}")


if __name__ == "__main__":
    install(Path(sys.argv[1]))
