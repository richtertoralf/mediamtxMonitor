#!/bin/bash

# Datei-Zuordnungen einbinden
source "$(dirname "$0")/filemap.sh"

# Auswahl anzeigen
echo "🔧 Verfügbare Dateien zum Zurückspielen:"
keys=("${!FILES[@]}")
for i in "${!keys[@]}"; do
    printf "%2d) %s\n" "$i" "${keys[$i]}"
done

read -p "Welche Dateien willst du zurückspielen? (z. B. 0 2 4): " -a indices

# Kopieren
for index in "${indices[@]}"; do
    file="${keys[$index]}"
    target="${FILES[$file]}"
    src="$SRC/$file"

    if [[ -f "$src" ]]; then
        echo "→ Kopiere $file nach $target ..."
        sudo cp -p "$src" "$target/"
        sudo chown mediamtxmon:mediamtxmon "$target/$file"
        [[ "$file" == *.py ]] && sudo chmod +x "$target/$file"
        echo "✅ $file deployed."
    else
        echo "⚠️  Datei $file nicht vorhanden in $SRC"
    fi
done
