"""Single-service demo launcher: migrations, web workers and bounded maintenance."""

import os
import signal
import subprocess
import sys
import threading


def main():
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
    stop = threading.Event()
    web = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "gunicorn",
            "config.wsgi:application",
            "--bind",
            "0.0.0.0:" + os.environ.get("PORT", "8000"),
            "--workers",
            "2",
            "--access-logfile",
            "-",
        ]
    )

    def shutdown(*_):
        stop.set()
        web.terminate()

    def maintain():
        while not stop.is_set():
            for command in ("publish_due", "cleanup_demos", "clearsessions"):
                try:
                    subprocess.run([sys.executable, "manage.py", command], check=True, timeout=25)
                except (subprocess.SubprocessError, OSError) as error:
                    print(f"Maintenance {command} failed: {error}", file=sys.stderr, flush=True)
            stop.wait(60)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    thread = threading.Thread(target=maintain, daemon=True)
    thread.start()
    try:
        return web.wait()
    finally:
        stop.set()
        thread.join(timeout=55)


if __name__ == "__main__":
    raise SystemExit(main())
