import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from app.main import app
import app.routes as routes
import app.models as models
import app.services as services


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.sets = {}

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hset(self, key, mapping=None):
        self.hashes.setdefault(key, {}).update(mapping or {})

    def smembers(self, key):
        return set(str(x) for x in self.sets.get(key, set()))

    def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    def srem(self, key, member):
        s = self.sets.get(key)
        if s:
            s.discard(member)

    def pipeline(self):
        # for tests we can apply immediately
        return self

    def execute(self):
        return True


@staticmethod
def _override_simulate_payment(payment_id, engine):
    with engine.connect() as conn:
        conn.execute(
            update(models.payments).where(models.payments.c.id == payment_id).values(status=models.PAY_SUCCESS, provider_response={"provider": "test"})
        )


def setup_test_app():
    # in-memory sqlite engine for tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.metadata.create_all(bind=engine)

    # override the get_conn dependency to use our test engine
    def override_get_conn():
        conn = engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[routes.get_conn] = override_get_conn

    # fake redis
    fake_redis = FakeRedis()
    services.redis_client = fake_redis

    # disable expiry worker and replace payment simulator
    services._expire_assignment_worker = lambda *_: None
    services._simulate_payment = lambda pid: _override_simulate_payment(pid, engine)

    client = TestClient(app)
    return client, engine, fake_redis


def test_full_flow_create_ride_match_accept_end_and_pay():
    client, engine, fake_redis = setup_test_app()

    # register a driver near pickup
    driver_id = 1
    pickup = {"lat": 12.9716, "lon": 77.5946}
    r = client.post(f"/v1/drivers/{driver_id}/location", json=pickup)
    assert r.status_code == 200 and r.json()["status"] == "ok"

    # create ride
    ride_payload = {
        "rider_id": 100,
        "pickup": pickup,
        "destination": {"lat": 12.975, "lon": 77.599},
        "tier": "standard",
        "payment_method": "card",
    }
    r = client.post("/v1/rides", json=ride_payload)
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    ride_id = body["id"]

    # check ride status and assignment
    r = client.get(f"/v1/rides/{ride_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("assigned", "no_driver")
    if data.get("assignment"):
        assignment_id = data["assignment"]["id"]
        # accept assignment
        r = client.post(f"/v1/drivers/{driver_id}/accept", json={"assignment_id": assignment_id})
        assert r.status_code == 200
        trip_id = r.json()["trip_id"]

        # end trip
        r = client.post(f"/v1/trips/{trip_id}/end", json={"end_lat": 12.976, "end_lon": 77.600})
        assert r.status_code == 200
        trip_body = r.json()
        assert "fare" in trip_body

        # trigger payment (simulator will immediately mark success in test)
        r = client.post("/v1/payments", json={"trip_id": trip_id})
        assert r.status_code == 200
        pay = r.json()
        assert "payment_id" in pay

