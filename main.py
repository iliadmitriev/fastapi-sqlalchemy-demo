import asyncio
import logging
from typing import List, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import StreamingResponse

from db import Item, User, engine
from logs import RouterLoggingMiddleware
from schemas import ItemDB, ItemPost, UserDB, UserPost

app = FastAPI()

# app.add_middleware(
#     RouterLoggingMiddleware,
#     logger=logging.getLogger(__name__)
# )


@app.get("/")
async def home():
    return {"message": "ok", "code": 0}


async def gen_response(request, count: int = 10000):
    try:
        print(f"client, connected {request.client}. start streaming")
        for c in range(count):
            await asyncio.sleep(0.1)
            yield b"some chunk"
    except asyncio.CancelledError:
        print(f"client, disconnected {request.client}")


@app.get("/gen")
async def gen(request: Request):
    return StreamingResponse(gen_response(request))


async def users_stream() -> AsyncIterator[bytes]:
    try:
        async with AsyncSession(engine) as session:
            result = await session.stream_scalars(select(User).order_by(User.id))
            async for user in result:
                await asyncio.sleep(0.1)
                yield UserDB.from_orm(user).json()
    except asyncio.CancelledError:
        pass


@app.get("/user")
async def get_users():
    return StreamingResponse(users_stream())


@app.post("/user", response_model=UserDB)
async def post_item(user: UserPost):
    async with AsyncSession(engine) as session:
        new_user = User.from_pd(user)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
    return new_user


@app.post("/item", response_model=ItemDB)
async def post_item(item: ItemPost):
    async with AsyncSession(engine) as session:
        try:
            user = await session.get(User, item.user_id)
            new_item = Item(**item.dict(), user=user)
            session.add(new_item)
            await session.flush()

        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Item is not added")

        await session.commit()
        await session.refresh(new_item)

    return new_item

if __name__ == '__main__':
    uvicorn.run(app)
