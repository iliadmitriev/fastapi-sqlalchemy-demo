import datetime
import json
import random

import pytest

from conftest import random_str


@pytest.mark.asyncio
async def test_health(get_client):
    response = await get_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ok", "code": 0}


@pytest.mark.asyncio
@pytest.mark.usefixtures("add_some_users")
async def test_user_stream(get_client):
    async with get_client.stream("GET", "/user") as response:
        async for line in response.aiter_lines():
            data = json.loads(line)
            assert 'id' in data
            assert 'name' in data
            assert 'login' in data


@pytest.mark.asyncio
@pytest.mark.usefixtures("add_some_users")
async def test_user_stream_break(get_client):
    async with get_client.stream("GET", "/user", timeout=0.1) as response:
        async for line in response.aiter_lines():
            assert line


@pytest.mark.asyncio
@pytest.mark.usefixtures("add_some_users")
async def test_gen_stream(get_client):
    async with get_client.stream("GET", "/gen", timeout=0.3) as response:
        async for data in response.aiter_bytes():
            assert isinstance(data, bytes)


@pytest.mark.asyncio
@pytest.mark.usefixtures("add_some_users")
async def test_post_user(get_client):
    login = random_str()
    response = await get_client.post("/user", json={
        "name": "John Doe",
        "login": login
    })
    assert response.status_code == 200
    data = response.json()
    assert data.pop("id") > 0
    assert data == {"name": "John Doe", "login": login}

    response = await get_client.post("/user", json={
        "name": "John Doe",
        "login": login
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_item_post(get_client, db_test_engine, add_some_users):
    user = random.choice(add_some_users)

    dt_str = datetime.datetime.now().isoformat()
    title_str = random_str(20)
    response = await get_client.post("/item", json={
        "weight": 3.14,
        "released": dt_str,
        "title": title_str,
        "user_id": user.id
    })
    assert response.status_code == 200
    data = response.json()
    assert data.pop("id") > 0
    assert data == {"weight": 3.14, "released": dt_str, "title": title_str, "user_id": user.id}

    response = await get_client.post("/item", json={
        "weight": 3.14,
        "released": dt_str,
        "title": title_str,
        "user_id": 0
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_item_patch(get_client, db_test_engine, add_some_users):
    user = random.choice(add_some_users)

    dt_str = datetime.datetime.now().isoformat()
    title_str = random_str(20)
    response = await get_client.post("/item", json={
        "weight": 3.14,
        "released": dt_str,
        "title": title_str,
        "user_id": user.id
    })
    assert response.status_code == 200
    data = response.json()
    item_id = data.pop("id")
    assert data == {"weight": 3.14, "released": dt_str, "title": title_str, "user_id": user.id}

    # successful patch
    response = await get_client.patch(f"/item/{item_id}", json={
        "weight": 666.0
    })
    assert response.status_code == 200
    assert response.json().get("weight") == 666.0

    # patch with non-existing user
    response = await get_client.patch(f"/item/{item_id}", json={
        "user_id": 0
    })
    assert response.status_code == 400

    # patch non-existing item
    response = await get_client.patch(f"/item/5000000", json={
        "weight": 666.0
    })
    assert response.status_code == 404

    # patch non-existing item
    response = await get_client.patch(f"/item/{item_id}", json={
        "some_field_dont_exist": 666.0
    })
    assert response.status_code == 200
