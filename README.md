# 📡 MediaMTX Stream Monitoring

## 🔎 Was macht dieses Projekt?

Dieses Projekt hilft dir, deinen **MediaMTX-Server** einfach und übersichtlich zu überwachen. Du siehst in Echtzeit:
- welche Streams aktiv sind,
- wie viele Daten übertragen werden,
- wie viele Zuschauer (Reader) verbunden sind,
- und bei SRT-Streams zusätzlich wichtige Werte wie RTT und Bandbreite.

So hast du immer den aktuellen Zustand deiner MediaMTX-Instanz im Blick – ohne den Server durch viele einzelne Anfragen zu belasten.

---

## 🛠️ Wie funktioniert es?

Das Monitoring besteht aus drei Bausteinen:

✅ **Backend (Python)**  
- Fragt alle 2 Sekunden die MediaMTX-API ab (`/v3/paths/list` und `/v3/srtconns/list`).
- Verarbeitet die Daten und speichert sie in **Redis**.
- Benachrichtigt alle verbundenen Browser über WebSockets, wenn es neue Daten gibt.

✅ **Redis**  
- Speichert den aktuellen Zustand der Streams.
- Kann auch historische Daten (z. B. RTT-Verlauf) speichern, damit du später Trends analysieren kannst.

✅ **Frontend (Browser)**  
- Lädt beim Start die aktuellen Daten vom Backend.
- Verbindet sich per **WebSocket**, um automatisch aktuelle Infos zu erhalten.
- Zeigt die Daten übersichtlich in Tabellen oder Diagrammen an.

---

## 🏗️ Warum dieser Aufbau?

- Das Backend fragt den MediaMTX-Server nur **einmal** ab, egal wie viele Clients verbunden sind.  
  → Das entlastet den MediaMTX-Server und spart Ressourcen.
- Die Clients müssen **nicht direkt auf den MediaMTX-Server zugreifen**, sondern nur auf das Backend.  
  → Das erhöht die Sicherheit, da du die MediaMTX-API nicht öffentlich zugänglich machen musst.
- Du kannst **beliebig viele Clients** anschließen, ohne den MediaMTX-Server stärker zu belasten.
- Du kannst später leicht neue Features ergänzen, z. B. Speicherung von Langzeit-Daten oder Anzeige der Server-Auslastung (CPU, RAM, Netzwerk).

---

## ⚙️ So ist das System aufgebaut

```scss
[MediaMTX-Server]
│
[Backend] (Python + Redis)
│
[Clients (Browser-Dashboard)]
```


- Das **Backend** sammelt die Daten.
- Es speichert sie in Redis und informiert alle Clients per WebSocket.
- Die **Clients** verbinden sich nur mit dem Backend und zeigen die Daten an.

---

## 📊 Welche Daten werden überwacht?

- Name des Streams (`name`)
- Quelle des Streams (`sourceType`, z. B. srtConn)
- Übertragene Bytes (`bytesReceived`)
- Anzahl der Zuschauer (`readers`)
- Bei SRT-Streams zusätzlich:
  - RTT (`msRTT`)
  - Empfangsrate (`mbpsReceiveRate`)
  - Link-Kapazität (`mbpsLinkCapacity`)

---

## 🚀 Geplante Entwicklungsschritte

1️⃣ **Basis-Backend**  
   - Holt aktuelle Daten vom MediaMTX-Server.
   - Speichert sie in Redis.

2️⃣ **WebSocket-Backend + Frontend**  
   - Erstellt ein Dashboard im Browser.
   - Stellt eine WebSocket-Verbindung her, um aktuelle Daten in Echtzeit anzuzeigen.

3️⃣ **Historische Daten**  
   - Speichert historische Metriken in Redis Streams.
   - Zeigt den Verlauf (z. B. RTT oder Bandbreite) im Frontend als Diagramm an.

4️⃣ **Server-Metriken (später)**  
   - Ein kleiner Agent auf dem MediaMTX-Host erfasst CPU-, RAM- und Netzwerk-Auslastung.
   - Diese Daten werden im Dashboard angezeigt.

---

## 🏁 Nächste Schritte

Eine detaillierte Anleitung zur Installation und zum Starten des Backends, Redis und des Frontends wird hier in Kürze ergänzt.

Bleib dran! 🚀

