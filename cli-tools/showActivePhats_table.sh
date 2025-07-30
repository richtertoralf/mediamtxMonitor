#!/bin/bash

API_URL="http://localhost:9997/v3/paths/list"

echo "🔍 Aktive MediaMTX-Streams:"
echo ""
printf " %-27s %-12s %-24s %-15s %-15s %-10s\n" "Stream Name" "Source" "Tracks" "Bytes Rx" "Bytes Tx" "Readers"
echo "-------------------------------------------------------------------------------------------------------------------------"

# Abrufen der JSON-Daten von der API
json_data=$(curl -s "$API_URL")

# Filtern und Formatieren der gewünschten Informationen für jeden aktiven Stream
echo "$json_data" | jq -r '
.items[] |
select(.ready == true) |
[.name, .source.type, (.tracks | join(", ")), .bytesReceived, .bytesSent, ([.readers[].type] | join(", "))] |
@tsv' | while IFS=$'\t' read -r name type tracks bytes_rx bytes_tx readers; do
    status="✅"  # nur grüner Status, weil .ready bereits true ist
    [ -z "$readers" ] && readers="-"
    printf " %-3s %-24s %-12s %-24s %-15s %-15s %-10s\n" \
           "$status" "$name" "$type" "$tracks" "$bytes_rx" "$bytes_tx" "$readers"
done
