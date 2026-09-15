"""Check effective MediaMTX configuration for installer reuse, read-only.

API checks run after /v3/info. Optional YAML bootstrap requires system PyYAML;
explicit endpoints work with only the standard library.
"""

import json
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen
from urllib.parse import urlsplit


PREVIEW_PATH = "~^__preview__/(.+)$"


def discover_api_url(config_file: str, binary: str) -> str:
    """Bootstrap only the known direct systemd invocation, without overrides."""
    try:
        import yaml
    except ImportError:
        raise ValueError(
            "YAML-Bootstrap benötigt PyYAML für python3 (Debian: python3-yaml). "
            "Vorher bereitstellen oder --mediamtx-api-url ausdrücklich angeben."
        ) from None

    try:
        result = subprocess.run(
            ["systemctl", "show", "mediamtx.service", "--property=MainPID",
             "--property=EnvironmentFiles", "--property=PassEnvironment"],
            check=True, capture_output=True, text=True, timeout=3,
        )
        properties = dict(line.split("=", 1) for line in result.stdout.splitlines())
        pid = int(properties["MainPID"])
        if pid <= 0 or properties.get("EnvironmentFiles") or properties.get("PassEnvironment"):
            raise ValueError
        process = Path("/proc") / str(pid)
        command = (process / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
        if command != [binary.encode(), config_file.encode()]:
            raise ValueError
        environment = (process / "environ").read_bytes().split(b"\0")
        overrides = {b"MTX_API", b"MTX_APIADDRESS", b"MTX_APIENCRYPTION"}
        if any(entry.split(b"=", 1)[0] in overrides for entry in environment):
            raise ValueError
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise ValueError(
            "YAML-Bootstrap nicht eindeutig: Dienstaufruf, Environment-Dateien "
            "oder API-Overrides prüfen; --mediamtx-api-url ausdrücklich angeben."
        ) from None

    try:
        config = yaml.safe_load(Path(config_file).read_text())
        if not isinstance(config, dict) or config.get("api", False) is not True:
            raise ValueError
        address = config.get("apiAddress", ":9997")  # MediaMTX v1.21 default
        encrypted = config.get("apiEncryption", False)
        if not isinstance(address, str) or type(encrypted) is not bool:
            raise ValueError
        parsed = urlsplit("//" + address)
        port = parsed.port
        if port is None or port == 0 or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError
        host = parsed.hostname or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
        if ":" in host:
            host = f"[{host}]"
        url = f"{'https' if encrypted else 'http'}://{host}:{port}"
        validate_url(url)
        return url
    except (OSError, ValueError, yaml.YAMLError):
        raise ValueError(
            "Aus der Datei ist kein eindeutiger aktivierter API-Endpoint ableitbar. "
            "Konfiguration prüfen oder --mediamtx-api-url ausdrücklich angeben."
        ) from None


def read_config(api_base: str, endpoint: str) -> dict:
    """Read one configuration response without exposing response secrets."""
    try:
        with urlopen(api_base.rstrip("/") + endpoint, timeout=3) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (OSError, ValueError):
        raise ValueError(f"MediaMTX-Konfiguration nicht lesbar: {endpoint}") from None


def check_config(api_base: str) -> None:
    """Require enabled WebRTC and the configured on-demand preview path."""
    global_config = read_config(api_base, "/v3/config/global/get")
    if global_config.get("webrtc") is not True:
        raise ValueError("Die laufende MediaMTX-Konfiguration aktiviert WebRTC nicht.")

    page = 0
    while True:
        data = read_config(api_base, f"/v3/config/paths/list?page={page}")
        items = data.get("items")
        page_count = data.get("pageCount")
        if (not isinstance(items, list) or type(page_count) is not int
                or page_count < 0 or any(not isinstance(item, dict) for item in items)):
            raise ValueError("Ungültige MediaMTX-Antwort: /v3/config/paths/list")
        for item in items:
            if item.get("name") == PREVIEW_PATH:
                command = item.get("runOnDemand")
                if isinstance(command, str) and command.strip():
                    return
                raise ValueError("Der __preview__-Path hat keinen runOnDemand-Hook.")
        page += 1
        if page >= page_count:
            break
    raise ValueError("Die laufende MediaMTX-Konfiguration enthält keinen Monitor-__preview__-Path.")


def validate_url(value: str) -> None:
    """Accept explicit HTTP(S) bases without exposing credentials to clients/logs."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise ValueError("Endpoint muss eine HTTP(S)-URL ohne Zugangsdaten, Query oder Fragment sein.") from None


def main() -> int:
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--discover-api":
            print(discover_api_url(sys.argv[2], sys.argv[3]))
        elif len(sys.argv) == 4 and sys.argv[1] == "--validate-urls":
            for value in sys.argv[2:]:
                validate_url(value)
        elif len(sys.argv) == 2:
            validate_url(sys.argv[1])
            check_config(sys.argv[1])
        else:
            raise ValueError("MediaMTX-API-URL muss ausdrücklich angegeben werden.")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
