from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "StockFit API is running"


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_items_crud() -> None:
    create_response = client.post(
        "/api/items",
        json={"name": "Protein Bar", "price": 2.99, "in_stock": True},
    )
    assert create_response.status_code == 201
    item = create_response.json()
    item_id = item["id"]

    get_response = client.get(f"/api/items/{item_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Protein Bar"

    patch_response = client.patch(f"/api/items/{item_id}", json={"price": 3.49})
    assert patch_response.status_code == 200
    assert patch_response.json()["price"] == 3.49

    delete_response = client.delete(f"/api/items/{item_id}")
    assert delete_response.status_code == 204
