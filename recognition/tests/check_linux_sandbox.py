"""Verify the actual Linux kernel policy in a disposable subprocess, not a mock."""

import errno
import json
import os
import resource
import socket
import subprocess
import sys


def check_network():
    for family, kind in (
        (socket.AF_INET, socket.SOCK_STREAM),
        (socket.AF_INET, socket.SOCK_DGRAM),
        (socket.AF_INET6, socket.SOCK_STREAM),
    ):
        try:
            connection = socket.socket(family, kind)
        except OSError as exc:
            assert exc.errno == errno.EPERM, exc
        else:
            connection.close()
            raise AssertionError("Inference process can open a network socket")


def main():
    if sys.platform != "linux":
        raise SystemExit("Linux is required; no successful result on another OS")
    if "--descendant" in sys.argv:
        check_network()
        return
    if "--child" not in sys.argv:
        env = {
            key: os.environ[key]
            for key in ("PATH", "PYTHONPATH", "LANG")
            if key in os.environ
        }
        env.update(
            WORKER_CHILD="1",
            MEMORY_LIMIT_MB="256",
            CPU_LIMIT_SECONDS="10",
            MAX_FILE_SIZE_MB="1",
        )
        subprocess.run(
            [sys.executable, __file__, "--child"], env=env, check=True, timeout=20
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": [
                        "IPv4 TCP/UDP denied",
                        "IPv6 denied",
                        "policy inherited by exec",
                        "CPU/address-space/file-size/core limits",
                    ],
                }
            )
        )
        return
    from app.execute import apply_limits

    apply_limits()
    check_network()
    assert resource.getrlimit(resource.RLIMIT_CPU) == (10, 10)
    assert resource.getrlimit(resource.RLIMIT_AS) == (256 * 1024 * 1024,) * 2
    assert resource.getrlimit(resource.RLIMIT_FSIZE) == (1024 * 1024,) * 2
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    subprocess.run([sys.executable, __file__, "--descendant"], check=True, timeout=10)


if __name__ == "__main__":
    main()
