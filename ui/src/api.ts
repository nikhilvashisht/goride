export type RideRequest = {
  rider_id?: number;
  pickup: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  tier?: string;
  payment_method?: string;
  idempotencyKey?: string;
};

export type RideResponse = {
  id: number;
  status: string;
  pickup: { lat: number; lon: number };
  destination: { lat: number; lon: number };
};

export type RideStatus = RideResponse & {
  assignment?: { id: number; driver_id: number; status: string };
};

const apiBase = import.meta.env.VITE_API_BASE || "/v1";

const okOrThrow = async (res: Response) => {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = (body as { detail?: string }).detail || res.statusText;
    throw new Error(message || "Request failed");
  }
  return body;
};

export async function createRide(payload: RideRequest): Promise<RideResponse> {
  const { idempotencyKey, ...body } = payload;
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  const res = await fetch(`${apiBase}/rides`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  return okOrThrow(res);
}

export async function getRideStatus(rideId: number): Promise<RideStatus> {
  const res = await fetch(`${apiBase}/rides/${rideId}`);
  return okOrThrow(res);
}
