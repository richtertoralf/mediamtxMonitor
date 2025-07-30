#!/bin/bash

# Spaltenbreiten definieren
col_widths=(6 16 9 28 10 10 10 10)  # Status, IP, State, Path, Recv(MB), RTT, RecvRate, LinkCap

# Erstelle Format-Strings basierend auf den Spaltenbreiten
col_formats=()
for width in "${col_widths[@]}"; do
  col_formats+=("%-${width}s")
done

# Gesamtlänge der Trennlinie berechnen
total_width=$((${#col_widths[@]} - 8 + $(IFS=+; echo "${col_widths[*]}")))
separator_line=$(printf '%*s' "$total_width" '' | tr ' ' '-')

while true; do
  # Abrufen und Formatieren der SRT-Daten
  json_data=$(curl -s http://localhost:9997/v3/srtconns/list)

  clear

  echo "🔍 Aktive SRT-Verbindungen (Publish Streams):"
  echo

  # Tabellenkopf für die Ausgabe
  printf "${col_formats[0]}" "Status"
  printf "${col_formats[1]}" "Remote Address"
  printf "${col_formats[2]}" "State"
  printf "${col_formats[3]}" "Path"
  printf "${col_formats[4]}" "Recv(MB)"
  printf "${col_formats[5]}" "RTT(ms)"
  printf "${col_formats[6]}" "RecvRate"
  printf "${col_formats[7]}\n" "LinkCap."
  echo "$separator_line"

  echo "$json_data" | jq -r '
    .items[] |
    select(.state == "publish") |
    [ .remoteAddr, .state, .path, .bytesReceived, .msRTT, .mbpsReceiveRate, .mbpsLinkCapacity ] |
    @tsv' | awk -F'\t' \
    -v col1="${col_formats[0]}" -v col2="${col_formats[1]}" -v col3="${col_formats[2]}" \
    -v col4="${col_formats[3]}" -v col5="${col_formats[4]}" -v col6="${col_formats[5]}" \
    -v col7="${col_formats[6]}" -v col8="${col_formats[7]}" '
    {
      # Entferne Port aus $1
      split($1, addr, ":")
      ip_only = addr[1]

      # Konvertiere und runde Werte
      recv_mb = sprintf("%d", $4 / (1024 * 1024))  # MB ohne Nachkommastellen
      rtt_ms = sprintf("%.3f", $5)
      recv_rate_mbps = sprintf("%.2f", $6)
      link_capacity_mbps = sprintf("%.2f", $7)

      # Status-Text abhängig von RecvRate
      if ($6 < 0.5) {
        status="LOW "
      } else {
        status="OK  "
      }

      # Ausgabe mit Spalten
      printf col1 col2 col3 col4 col5 col6 col7 col8 "\n", status, ip_only, $2, $3, recv_mb, rtt_ms, recv_rate_mbps, link_capacity_mbps
    }'

  sleep 2
done
