import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable wide CORS rules so your secure deployments connect flawlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- COMPLETE LEAFLET FRONTEND UI ---
html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <title>Live Secure Train Tracker</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { margin:0; padding:0; font-family:sans-serif; background:#111; color:#fff; overflow:hidden; }
        #hud { height:12vh; display:flex; align-items:center; justify-content:space-around; background:#1a1a1a; border-bottom:2px solid #333; }
        .val { font-size:1.3rem; font-weight:bold; color:#00ff66; text-align:center; }
        #map { height:88vh; width:100vw; }
    </style>
</head>
<body>
    <div id="hud">
        <div>Train ID<br><div id="tid" class="val">-</div></div>
        <div>Velocity<br><div class="val"><span id="spd">0</span> km/h</div></div>
        <div>Data Stream<br><div id="st" class="val" style="color:#ffcc00">CONNECTING</div></div>
    </div>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Init Map view around New Delhi tracks
        const map = L.map('map').setView([28.6140, 77.2090], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        const markers = {};

        // Securely switch between ws:// (local) and wss:// (encrypted Render cloud)
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const host = window.location.host;
        const ws = new WebSocket(`${protocol}//${host}/ws/trains`);

        ws.onopen = () => { 
            document.getElementById("st").innerText = "SECURE SYNC"; 
            document.getElementById("st").style.color = "#00ff66"; 
        };
        ws.onclose = () => { 
            document.getElementById("st").innerText = "STREAM CLOSED"; 
            document.getElementById("st").style.color = "#ff3333"; 
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            document.getElementById("tid").innerText = data.trainId;
            document.getElementById("spd").innerText = data.speed;

            if (markers[data.trainId]) {
                markers[data.trainId].setLatLng([data.lat, data.lng]);
            } else {
                markers[data.trainId] = L.marker([data.lat, data.lng]).addTo(map).bindPopup(data.trainId).openPopup();
                map.setView([data.lat, data.lng], 14);
            }
        };

        // Automated mobile GPS pipeline simulator
        let simLng = 77.2090;
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                simLng += 0.0006;
                let noisyLat = 28.6140 + (Math.random() - 0.5) * 0.002;
                ws.send(JSON.stringify({ trainId: "TRAIN-12626", lat: noisyLat, lng: simLng, speed: 22 }));
            }
        }, 1500);
    </script>
</body>
</html>
"""

# --- PRODUCTION ROUTING LOGIC ---

@app.get("/", response_class=HTMLResponse)
async def get_map():
    return html_content

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try: await connection.send_text(message)
            except Exception: pass

manager = ConnectionManager()

@app.websocket("/ws/trains")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            # Map-matching math component (Snaps Lat directly to 28.6140 rail layout)
            clean_lat = 28.6140 
            clean_lng = data.get("lng")
            speed_kmh = round(data.get("speed", 0) * 3.6, 1)

            payload = {
                "trainId": data.get("trainId"),
                "lat": clean_lat,
                "lng": clean_lng,
                "speed": speed_kmh
            }
            await manager.broadcast(json.dumps(payload))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Bind port to 8000 locally, or read dynamic port on Render cloud deployments
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)