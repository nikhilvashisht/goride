import { useMemo, useState } from "react";
import { createRide, getRideStatus, RideRequest, RideStatus } from "./api";
import "./styles.css";

type LogEntry = {
  id: number;
  title: string;
  payload?: unknown;
  time: string;
};

const now = () => new Date().toLocaleTimeString();
const toNumber = (value: string): number | undefined => {
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
};

function App() {
  const [rideId, setRideId] = useState<string>("");
  const [riderId, setRiderId] = useState<string>("");
  const [tier, setTier] = useState<string>("standard");
  const [payment, setPayment] = useState<string>("card");
  const [idemKey, setIdemKey] = useState<string>("");
  const [pickupLat, setPickupLat] = useState<string>("12.9716");
  const [pickupLon, setPickupLon] = useState<string>("77.5946");
  const [destLat, setDestLat] = useState<string>("12.9750");
  const [destLon, setDestLon] = useState<string>("77.6040");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);

  const apiBaseDisplay = useMemo(() => "/v1", []);

  const appendLog = (title: string, payload?: unknown) => {
    setLogs((prev) => [{ id: prev.length + 1, title, payload, time: now() }, ...prev]);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: RideRequest = {
      rider_id: toNumber(riderId),
      pickup: { lat: toNumber(pickupLat) ?? 0, lon: toNumber(pickupLon) ?? 0 },
      destination: { lat: toNumber(destLat) ?? 0, lon: toNumber(destLon) ?? 0 },
      tier,
      payment_method: payment,
      idempotencyKey: idemKey.trim() || undefined,
    };

    appendLog("Sending ride request", payload);
    setLoadingCreate(true);
    try {
      const res = await createRide(payload);
      appendLog("Ride created", res);
      setRideId(String(res.id ?? ""));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      appendLog("Ride request failed", { error: message });
    } finally {
      setLoadingCreate(false);
    }
  };

  const handleStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    const id = toNumber(rideId);
    if (!id) {
      appendLog("Ride id required for status");
      return;
    }
    appendLog(`Fetching /rides/${id}`);
    setLoadingStatus(true);
    try {
      const res: RideStatus = await getRideStatus(id);
      appendLog("Ride status", res);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Lookup failed";
      appendLog("Status check failed", { error: message });
    } finally {
      setLoadingStatus(false);
    }
  };

  const copyPayload = () => {
    const payload: RideRequest = {
      rider_id: toNumber(riderId),
      pickup: { lat: toNumber(pickupLat) ?? 0, lon: toNumber(pickupLon) ?? 0 },
      destination: { lat: toNumber(destLat) ?? 0, lon: toNumber(destLon) ?? 0 },
      tier,
      payment_method: payment,
      idempotencyKey: idemKey.trim() || undefined,
    };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2)).then(() => {
      appendLog("Copied payload", payload);
    });
  };

  const clearLog = () => setLogs([]);

  return (
    <div className="app-shell">
      <header>
        <div>
          <div className="eyebrow">Goride developer console</div>
          <h1>Request rides and inspect status</h1>
          <p className="tip">Calls the FastAPI service on the same origin.</p>
        </div>
        <span className="pill">API base: {apiBaseDisplay}</span>
      </header>

      <main className="grid">
        <section className="card">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Ride</div>
              <h2 style={{ margin: 0 }}>Create a ride</h2>
            </div>
            {rideId && <span className="badge-success">Last ride: {rideId}</span>}
          </div>
          <form onSubmit={handleCreate}>
            <div className="field-grid">
              <div>
                <label htmlFor="rider">Rider ID</label>
                <input id="rider" type="number" value={riderId} onChange={(e) => setRiderId(e.target.value)} placeholder="e.g. 101" />
              </div>
              <div>
                <label htmlFor="tier">Tier</label>
                <select id="tier" value={tier} onChange={(e) => setTier(e.target.value)}>
                  <option value="standard">standard</option>
                  <option value="premium">premium</option>
                </select>
              </div>
              <div>
                <label htmlFor="payment">Payment method</label>
                <select id="payment" value={payment} onChange={(e) => setPayment(e.target.value)}>
                  <option value="card">card</option>
                  <option value="cash">cash</option>
                </select>
              </div>
              <div>
                <label htmlFor="idem">Idempotency-Key</label>
                <input id="idem" value={idemKey} onChange={(e) => setIdemKey(e.target.value)} placeholder="uuid or custom token" />
              </div>
              <div>
                <label htmlFor="pickup-lat">Pickup lat</label>
                <input id="pickup-lat" type="number" step="0.000001" value={pickupLat} onChange={(e) => setPickupLat(e.target.value)} required />
              </div>
              <div>
                <label htmlFor="pickup-lon">Pickup lon</label>
                <input id="pickup-lon" type="number" step="0.000001" value={pickupLon} onChange={(e) => setPickupLon(e.target.value)} required />
              </div>
              <div>
                <label htmlFor="dest-lat">Destination lat</label>
                <input id="dest-lat" type="number" step="0.000001" value={destLat} onChange={(e) => setDestLat(e.target.value)} required />
              </div>
              <div>
                <label htmlFor="dest-lon">Destination lon</label>
                <input id="dest-lon" type="number" step="0.000001" value={destLon} onChange={(e) => setDestLon(e.target.value)} required />
              </div>
            </div>
            <div className="actions">
              <button className="primary" type="submit" disabled={loadingCreate}>
                {loadingCreate ? "Requesting..." : "Request ride"}
              </button>
              <button className="ghost" type="button" onClick={clearLog}>
                Clear log
              </button>
              <button className="ghost" type="button" onClick={copyPayload}>
                Copy payload
              </button>
            </div>
            <p className="tip">Immediate driver discovery may set status to "assigned" or keep it "searching".</p>
          </form>
        </section>

        <section className="card">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Status</div>
              <h2 style={{ margin: 0 }}>Check ride status</h2>
            </div>
          </div>
          <form onSubmit={handleStatus}>
            <div className="field-grid">
              <div>
                <label htmlFor="ride-id">Ride ID</label>
                <input id="ride-id" type="number" value={rideId} onChange={(e) => setRideId(e.target.value)} placeholder="returned id" required />
              </div>
            </div>
            <div className="actions">
              <button className="primary" type="submit" disabled={loadingStatus}>
                {loadingStatus ? "Fetching..." : "Fetch status"}
              </button>
            </div>
            <p className="tip">Uses GET /v1/rides/{"{id}"} to fetch the latest assignment and state.</p>
          </form>
        </section>

        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="section-heading">
            <div>
              <div className="eyebrow">Console</div>
              <h2 style={{ margin: 0 }}>Live responses</h2>
            </div>
          </div>
          <div className="log">
            {logs.length === 0 && <div className="tip">No calls yet. Submit a ride to see responses.</div>}
            {logs.map((entry) => (
              <div key={entry.id} className="log-entry">
                <div className="log-title">{entry.title}</div>
                <div className="log-time">{entry.time}</div>
                {entry.payload !== undefined && (
                  <pre style={{ margin: "4px 0 0" }}>{JSON.stringify(entry.payload, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer>Tip: set VITE_API_BASE to point at a remote gateway if not running the API locally.</footer>
    </div>
  );
}

export default App;
