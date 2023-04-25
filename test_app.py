import pytest


@pytest.mark.asyncio
async def test_health(get_client):
    response = await get_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ok", "code": 0}