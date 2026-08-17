/**
 * 📡 API-Modul zur Abfrage von Streamdaten vom FastAPI-Backend
 * 
 * Diese Funktion ruft den Endpunkt `/api/streams` auf und gibt ein JSON-Objekt zurück:
 * {
 *   streams: [...],                 // Liste der aktuellen Streams
 *   collected_at: Number | null,    // Zeitpunkt des letzten Collector-Snapshots
 *   snapshot_refresh_ms: Number,   // Intervall für Snapshot-Reload
 *   streamlist_refresh_ms: Number, // Intervall für Streamliste
 *   monitor_version: String | null // Version des MediaMTX Monitor
 * }
 * 
 * @returns {Promise<Object>} - Datenobjekt oder leeres Fallback-Objekt bei Fehlern
 */
export async function fetchStreamsFromApi() {
  try {
    const res = await fetch("/api/streams");
    if (!res.ok) throw new Error(`API antwortete mit Status ${res.status}`);
    const data = await res.json();
    return data;
  } catch (err) {
    console.error("❌ Fehler beim API-Fetch:", err);
    return {
      streams: [],
      streamlist_refresh_ms: 1000
    };
  }
}
