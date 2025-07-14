#!/usr/bin/env python3

import requests
import json
import sys # Zum ordnungsgemäßen Beenden des Skripts

MEDIA_MTX_API_URL = "http://localhost:9997"
OUTPUT_FILE_PATH = "/tmp/mediamtx_streams.json"

def fetch_data(endpoint):
    try:
        response = requests.get(f"{MEDIA_MTX_API_URL}{endpoint}")
        response.raise_for_status() # Löst HTTPError bei schlechten Antworten (4xx oder 5xx) aus
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"❌ Fehler: Verbindung zu MediaMTX unter {MEDIA_MTX_API_URL} konnte nicht hergestellt werden. Läuft der Server?", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP-Fehler beim Abrufen von {endpoint}: {e}", file=sys.stderr)
        sys.exit(1)
    except json.decoder.JSONDecodeError:
        print(f"❌ Fehler: Ungültiges JSON von {endpoint} erhalten", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ein unerwarteter Fehler ist aufgetreten: {e}", file=sys.stderr)
        sys.exit(1)

# Hole die Paths-Liste und die SRT-Streams-Liste
# Verwende die fetch_data-Funktion
paths = fetch_data("/v3/paths/list")
srtconns = fetch_data("/v3/srtconns/list")

aggregated = []

for path in paths.get("items", []):
    name = path.get("name")
    source_type = path.get("source", {}).get("type", "unknown")
    tracks = path.get("tracks", [])
    bytes_received = path.get("bytesReceived", 0)
    readers = len(path.get("readers", []))

    entry = {
        "name": name,
        "sourceType": source_type,
        "tracks": tracks,
        "bytesReceived": bytes_received,
        "readers": readers,
    }

    if source_type == "srtConn":
        # suche in den SRT-Daten den passenden Eintrag zum Path-Namen
        srt_data = next((s for s in srtconns.get("items", []) if s.get("path") == name), None)
        if srt_data:
            entry.update({
                "rtt": srt_data.get("msRTT"),
                "recvRateMbps": srt_data.get("mbpsReceiveRate"),
                "linkCapacityMbps": srt_data.get("mbpsLinkCapacity"),
            })
    aggregated.append(entry)

# JSON speichern
with open("/tmp/mediamtx_streams.json", "w") as f:
    json.dump(aggregated, f, indent=2)

print("✅ Aggregiertes JSON wurde in /tmp/mediamtx_streams.json gespeichert.")
