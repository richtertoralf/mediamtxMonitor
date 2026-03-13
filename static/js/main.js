/**
 * 📡 Mediamtx Stream Monitor – Hauptmodul (dynamisch mit collector.yaml)
 * 
 * Dieses Modul steuert den Hauptablauf:
 * - Holt die aktuellen Streamdaten + Refresh-Intervalle vom Backend
 * - Rendert die Daten im DOM mithilfe externer Module
 * - Aktualisiert die Anzeige regelmäßig basierend auf YAML-Konfiguration
 * 
 * 🔧 Modulübersicht:
 * | Datei         | Aufgabe                                    |
 * | ------------- | ------------------------------------------ |
 * | `main.js`     | Ablaufsteuerung (Daten holen, rendern)     |
 * | `api.js`      | Holt Daten vom Backend (`/api/streams`)    |
 * | `renderer.js` | Rendert Stream-Karten & Reader-Details     |
 * 
 * Autor: snowgames.live
 * Lizenz: MIT
 */


import { fetchStreamsFromApi } from "./api.js";
import { renderStreamCard, updateStreamCard } from "./renderer.js";
import { renderSystemInfo } from "./systeminfo.js";

const container = document.getElementById("streams");
const noStreams = document.getElementById("no-streams");

const streamCards = new Map(); // Name → DOM-Element

let refreshIntervalMs = 5000; // Defaultwert, wird gleich überschrieben
let refreshTimer = null;

async function updateUI() {
  const result = await fetchStreamsFromApi();

  renderSystemInfo(result.systeminfo || {});

  const newInterval = result.streamlist_refresh_ms ?? 5000;

  const streams = result.streams || [];
  const seen = new Set();

  for (const stream of streams) {
    seen.add(stream.name);
    const existingCard = streamCards.get(stream.name);

    if (!existingCard) {
      const newCard = renderStreamCard(stream);
      container.appendChild(newCard);
      streamCards.set(stream.name, newCard);
    } else {
      updateStreamCard(existingCard, stream);
    }
  }

  // 🧹 Entferne veraltete Karten
  for (const [name, card] of streamCards.entries()) {
    if (!seen.has(name)) {
      card.remove();
      streamCards.delete(name);
    }
  }

  // 🔘 Sichtbarkeit "Keine Streams"
  noStreams.style.display = streams.length === 0 ? "block" : "none";

  // ⏱ Intervall bei Bedarf neu setzen
  if (newInterval !== refreshIntervalMs) {
    clearInterval(refreshTimer);
    refreshIntervalMs = newInterval;
    refreshTimer = setInterval(updateUI, refreshIntervalMs);
  }
}


// 🟢 Initiale Ausführung + Intervall starten
updateUI().then(() => {
  refreshTimer = setInterval(updateUI, refreshIntervalMs);
});
