# Goride API Documentation

This document lists all API endpoints, their HTTP method, request schema, and example responses.

Base path: `/v1`

---

## POST /v1/rides
- Method: POST
- Description: Create a ride request. Attempts to match a nearby driver immediately.
- Request JSON schema:

```json
{
  "rider_id": 123,            // optional, integer
  "pickup": {"lat": 12.34, "lon": 56.78},
  "destination": {"lat": 12.35, "lon": 56.79},
  "tier": "standard",       // optional, string
  "payment_method": "card"  // optional, string
}
```

- Headers:
  - `Idempotency-Key` (optional): a unique string to make this request idempotent.

- Response (201/200):

```json
{
  "id": 42,
  "status": "assigned",   // or "searching" / "no_driver"
  "pickup": {"lat": 12.34, "lon": 56.78},
  "destination": {"lat": 12.35, "lon": 56.79}
}
```

---

## GET /v1/rides/{id}
- Method: GET
- Description: Retrieve ride status and assignment (if any).
- Path params: `id` (integer)
- Response:

```json
{
  "id": 42,
  "status": "assigned",
  "pickup": {...},
  "destination": {...},
  "assignment": {
    "id": 7,
    "driver_id": 10,
    "status": "offered"
  }
}
```

---

## POST /v1/drivers/{id}/location
- Method: POST
- Description: Send driver location updates (frequent, 1–2 per second).
- Path params: `id` (driver id)
- Request JSON schema:

```json
{
  "lat": 12.34,
  "lon": 56.78
}
```

- Response:

```json
{ "status": "ok" }
```

---

## POST /v1/drivers/{id}/accept
- Method: POST
- Description: Driver accepts an assignment offer.
- Path params: `id` (driver id)
- Request JSON schema:

```json
{ "assignment_id": 7 }
```

- Response:

```json
{ "trip_id": 100, "status": "ongoing" }
```

---

## POST /v1/trips/{id}/end
- Method: POST
- Description: End a trip, calculate fare, and create a payment.
- Path params: `id` (trip id)
- Request JSON schema:

```json
{ "end_lat": 12.36, "end_lon": 56.80 }
```

- Response:

```json
{ "trip_id": 100, "fare": 12.34, "status": "completed" }
```

---

## POST /v1/payments
- Method: POST
- Description: Trigger the payment flow for a trip's payment record.
- Request JSON schema:

```json
{ "trip_id": 100, "method": "card" }
```

- Response:

```json
{ "payment_id": 200, "status": "pending" }
```

Notes:
- Payments are simulated in the sample implementation; in production this will call an external PSP and record provider responses.

---

Idempotency and error models
- Endpoints that create resources (e.g., `POST /v1/rides`) accept `Idempotency-Key` header to avoid duplicate entries on retries.

