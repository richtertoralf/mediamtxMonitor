#!/bin/bash

OUTPUT="filemap.sh"
PROJECT_ROOT="/opt/mediamtx-monitoring-backend"
SRC_DIR="\$HOME/scripts/mediamtxmon"
IGNORE_FILE=".filemapignore"

# 🧩 Datei-Mapping vorbereiten
declare -A files_by_group

# Gruppenzuordnung basierend auf Zielverzeichnis
function classify_file() {
  case "$1" in
    */bin/*) echo "📦 Python-Module" ;;
    */config/*) echo "⚙️ Konfiguration" ;;
    */static/css/*) echo "🎨 CSS" ;;
    */static/js/*) echo "🧩 JavaScript-Module" ;;
    */static/*) echo "🖥️ HTML & Assets" ;;
    */) echo "📁 Sonstiges" ;;
    *) echo "📚 Sonstiges" ;;
  esac
}

# 🛑 .filemapignore verarbeiten
ignore_prune_args=()
ignore_name_args=()

if [[ -f "$IGNORE_FILE" ]]; then
  while IFS= read -r pattern; do
    [[ -z "$pattern" || "$pattern" == \#* ]] && continue
    clean_pattern="${pattern#/}"
    clean_pattern="${clean_pattern%/}"
    fullpath="$PROJECT_ROOT/$clean_pattern"

    if [[ "$pattern" == */* || -d "$fullpath" || "$clean_pattern" != "${clean_pattern##*/}" ]]; then
      ignore_prune_args+=(-path "$fullpath" -prune -o)
    else
      ignore_name_args+=(! -name "$clean_pattern")
    fi
  done < "$IGNORE_FILE"
fi

# 🔍 Alle passenden Dateien finden
find "$PROJECT_ROOT" "${ignore_prune_args[@]}" -type f "${ignore_name_args[@]}" -print | while read -r path; do
  file=$(basename "$path")
  dir=$(dirname "$path")
  group=$(classify_file "$dir")
  files_by_group["$group"]+="$file|$dir"$'\n'
done

# 📝 HEADER schreiben
{
  echo "#!/bin/bash"
  echo ""
  echo "SRC=$SRC_DIR"
  echo ""
  echo "declare -A FILES=("

  # 🔠 Alphabetische Gruppenausgabe
  for group in "${!files_by_group[@]}"; do
    echo ""
    echo "  # $group"
    echo -n "${files_by_group[$group]}" | sort | uniq | while IFS="|" read -r file dir; do
      echo "  [$file]=\"$dir\""
    done
  done

  echo ")"
} > "$OUTPUT"

# 🔍 Suche nach systemd-Units zu mediamtx
echo "" >> "$OUTPUT"
echo "# 🔧 systemd-Units (automatisch erkannt)" >> "$OUTPUT"

while IFS= read -r unitfile; do
  filename=$(basename "$unitfile")
  echo "  [$filename]=\"/etc/systemd/system\"" >> "$OUTPUT"
done < <(find /etc/systemd/system -maxdepth 1 -type f -name 'mediamtx*.service')


chmod +x "$OUTPUT"
echo "✅ filemap.sh wurde erfolgreich strukturiert erzeugt."
