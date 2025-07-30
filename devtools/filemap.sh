#!/bin/bash

SRC=$HOME/scripts/mediamtxmon

declare -A FILES=(
  # 📦 Python-Module
  [mediamtx_collector.py]="/opt/mediamtx-monitoring-backend/bin"
  [reader_bitrate.py]="/opt/mediamtx-monitoring-backend/bin"
  [mediamtx_api.py]="/opt/mediamtx-monitoring-backend/bin"
  [mediamtx_snapshots.py]="/opt/mediamtx-monitoring-backend/bin"
  [mediamtx_system.py]="/opt/mediamtx-monitoring-backend/bin"

  # ⚙️ Konfiguration
  [collector.yaml]="/opt/mediamtx-monitoring-backend/config"

  # 🖥️ Frontend
  [index.html]="/opt/mediamtx-monitoring-backend/static"
  [style.css]="/opt/mediamtx-monitoring-backend/static/css"

  # 🧩 JavaScript-Module
  [main.js]="/opt/mediamtx-monitoring-backend/static/js"
  [renderer.js]="/opt/mediamtx-monitoring-backend/static/js"
  [api.js]="/opt/mediamtx-monitoring-backend/static/js"
  [systeminfo.js]="/opt/mediamtx-monitoring-backend/static/js"

  # 📚 Abhängigkeiten
  [requirements.txt]="/opt/mediamtx-monitoring-backend"

  # 📝 Optionales
  [README.md]="/opt/mediamtx-monitoring-backend"
)
