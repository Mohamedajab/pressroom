import json
from pathlib import Path
from zipfile import ZipFile

from scripts.sanitise_trace import sanitise_trace


def test_trace_redacts_credentials_and_local_sources(tmp_path):
    path = tmp_path / "trace.zip"
    data = {
        "headers": [{"name": "cookie", "value": "sessionid=secret-session; csrftoken=secret-csrf"}],
        "attributes": {"name": "csrfmiddlewaretoken", "value": "secret-form"},
        "source": str(Path.home()),
    }
    with ZipFile(path, "w") as trace:
        trace.writestr("0.network", json.dumps(data))
        trace.writestr("0.stacks", "private local source paths")
        trace.writestr("resources/src@code.txt", "private source code")
    sanitise_trace(path)
    with ZipFile(path) as trace:
        contents = trace.read("0.network").decode()
        assert "secret-session" not in contents
        assert "secret-csrf" not in contents
        assert "secret-form" not in contents
        assert "Moham" not in contents
        assert trace.namelist() == ["0.network"]
