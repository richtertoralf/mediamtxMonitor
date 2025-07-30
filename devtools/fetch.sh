#!/bin/bash

# Datei-Zuordnungen einbinden
source "$(dirname "$0")/filemap.sh"

mkdir -p "$SRC"

keys=("${!FILES[@]}")

echo "🔄 Verfügbare Dateien zum Herunterholen:"
for i in "${!keys[@]}"; do
    printf "%2d) %s → %s\n" "$i" "${keys[$i]}" "${FILES[${keys[$i]}]}"
done

# Prüfe auf --all
if [[ "$1" == "--all" ]]; then
    echo "🚀 Alle Dateien werden geholt..."
    indices=($(seq 0 $((${#keys[@]} - 1))))
else
    read -p "Welche Dateien willst du holen? (z. B. 0 2 3): " -a indices
fi

# Kopiervorgang
for index in "${indices[@]}"; do
    file="${keys[$index]}"
    src="${FILES[$file]}/$file"
    if [[ -f "$src" ]]; then
        cp -p "$src" "$SRC/"
        echo "✅ $file geholt."
    else
        echo "⚠️  $file nicht gefunden in $src"
    fi
done
