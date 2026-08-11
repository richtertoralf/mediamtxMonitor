#!/bin/bash


# ============================================================================
# 📱 MediaMTX Streammonitor (Hochkant-Ansicht für Smartphone via Termux/SSH)
#
# Dieses Skript ruft über die MediaMTX-API eine Liste aller aktiven Streams ab
# und zeigt sie in einer hochkant-freundlichen Darstellung an – ideal zur 
# Nutzung auf Smartphones (z. B. über Termux mit SSH-Verbindung).
#
# Es werden folgende Informationen je Stream angezeigt:
# - Streamname
# - Quellentyp (z. B. srt, rtmp, webrtc)
# - Track-Übersicht (z. B. video, audio)
# - Empfangene und gesendete Bytes (in Megabyte)
# - Aktive Leser (readers) wie HLS, WebRTC etc.
#
# Nur "ready == true"-Streams werden gelistet. Die Ausgabe ist kompakt und 
# übersichtlich strukturiert – optimiert für schmale Displays.
# ============================================================================


API_URL="http://localhost:9997/v3/paths/list"

# Farben (Terminal-freundlich)
BOLD=$(tput bold)
BLUE=$(tput setaf 4)
RESET=$(tput sgr0)

# Funktion zur Umrechnung von Bytes in Megabytes
bytes_to_mb() {
    local bytes="$1"
    awk "BEGIN { printf \"%.1f\", $bytes / (1024 * 1024) }"
}

echo "🔍 Aktive MediaMTX-Streams:"
echo ""

# Abrufen der JSON-Daten von der API
json_data=$(curl -s "$API_URL")

# Verarbeiten der Streams
echo "$json_data" | jq -r '
.items[] |
select(.online == true) |
[.name, .source.type, ([.tracks2[].codec] | join(", ")), .inboundBytes, .outboundBytes, ([.readers[].type] | join(", "))] |
@tsv' | while IFS=$'\t' read -r name type tracks bytes_rx bytes_tx readers; do
    status="✅"
    [ -z "$readers" ] && readers="–"
    rx_mb=$(bytes_to_mb "$bytes_rx")
    tx_mb=$(bytes_to_mb "$bytes_tx")

    echo -e "📺 Stream:   ${BOLD}${BLUE}$name${RESET}"
    echo "🎬 Quelle:   $type"
    echo "🎵 Tracks:   $tracks"
    echo "⬇️ Bytes Rx: ${rx_mb} MB"
    echo "⬆️ Bytes Tx: ${tx_mb} MB"
    echo "👀 Leser:    $readers"
    echo "--------------------------------"
done
