"""Redact synthetic session/CSRF credentials and local source paths before sharing."""

import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def sanitise_trace(path):
    secrets = set()

    def collect(value):
        if isinstance(value, dict):
            if str(value.get("name", "")).lower() in {
                "csrfmiddlewaretoken",
                "csrftoken",
                "sessionid",
                "authorization",
            }:
                token = value.get("value")
                if isinstance(token, str) and token:
                    secrets.add(token.encode())
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    path = Path(path)
    temporary = path.with_suffix(".sanitised.zip")
    with ZipFile(path) as source:
        files = {
            name: source.read(name)
            for name in source.namelist()
            if not name.endswith(".stacks") and "resources/src@" not in name
        }
    for data in files.values():
        secrets.update(re.findall(rb"(?:csrfmiddlewaretoken|csrftoken|sessionid)=(\w+)", data))
        for line in data.splitlines():
            try:
                collect(json.loads(line))
            except (ValueError, UnicodeDecodeError):
                pass
    with ZipFile(temporary, "w", ZIP_DEFLATED) as target:
        for name, data in files.items():
            for token in secrets:
                data = data.replace(token, b"REDACTED")
            for home in (
                str(Path.home()),
                str(Path.home()).replace("\\", "\\\\"),
                Path.home().as_posix(),
            ):
                data = data.replace(home.encode(), b"<local-user>")
            target.writestr(name, data)
    temporary.replace(path)
