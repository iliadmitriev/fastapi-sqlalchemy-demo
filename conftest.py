import asyncio
import os
import random
import string
import time
from unittest import mock

import pytest
from asgi_lifespan import LifespanManager
from docker.errors import DockerException
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from db import Base


def try_external_conn_data():
    fields = ["host", "port", "database", "username", "password"]
    prefix = "PYTEST_PG_"
    connection_data = {field: os.environ.get(prefix + field.upper()) for field in fields if
                       prefix + field.upper() in os.environ}
    return connection_data


def random_str(length=10):
    return "".join(random.choices(string.ascii_lowercase, k=length))


def try_docker_container():
    try:
        import docker
    except ImportError:
        raise RuntimeError("docker package not found.\n"
                           "this package along with running docker needed to perform tests.\n"
                           "try to install docker package with pip.\n"
                           "for more information https://docker-py.readthedocs.io/en/stable/index.html")

    try:
        user, password, db = f"user_{random_str(10)}", f"pass_{random_str(10)}", f"db_{random_str(10)}"
        random_port = random.randint(60000, 62000)

        client = docker.from_env()
        container_env = {
            "POSTGRES_PASSWORD": password,
            "POSTGRES_USER": user,
            "POSTGRES_DB": db,
            "POSTGRES_HOST_AUTH_METHOD": "trust",
        }
        container = client.containers.run("postgres:alpine", detach=True, remove=True, auto_remove=True,
                                          ports={f"{5432}/tcp": random_port},
                                          healthcheck={
                                              "test": ["CMD-SHELL", "pg_isready", "-U", user],
                                              "interval": 3_000_000_000,
                                              "timeout": 3_000_000_000,
                                              "retries": 3
                                          },
                                          environment=container_env)

        while container.status != "running" or container.attrs["State"].get("Health", {}).get("Status") != "healthy":
            time.sleep(1)
            container.reload()
    except DockerException as exc:
        raise RuntimeError("Failed to start test database container\n"
                           "Make sure that containerizing system is running and accepting connections.\n"
                           "Also make sure user have appropriate permissions to create and run containers.\n"
                           f"{exc}")

    return {
        "host": "127.0.0.1",
        "port": random_port,
        "database": db,
        "username": user,
        "password": password
    }, container.stop


@pytest.fixture(scope="session")
def pg_connection_data():
    conn = try_external_conn_data()
    if conn:
        yield conn
    else:
        conn, container_stop = try_docker_container()
        yield conn
        container_stop()


@pytest.fixture(scope="session")
async def db_test_engine(pg_connection_data) -> AsyncEngine:
    conn_obj = URL.create(
        drivername="postgresql+asyncpg",
        **pg_connection_data
    )
    engine = create_async_engine(
        conn_obj
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
async def get_app(db_test_engine: AsyncEngine) -> FastAPI:
    with mock.patch("sqlalchemy.ext.asyncio.create_async_engine") as patched_engine:
        patched_engine.return_value = db_test_engine
        from main import app
        async with LifespanManager(app):
            yield app


@pytest.fixture(scope="session")
async def get_client(get_app: FastAPI) -> AsyncClient:
    async with AsyncClient(app=get_app, base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop
    loop.close()
