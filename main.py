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
from schemas import ItemDB, ItemPost, UserDB, UserPost, ItemPatch

app = FastAPI()


# app.add_middleware(
#     RouterLoggingMiddleware,
#     logger=logging.getLogger(__name__)
# )


@app.get("/")
async def home():
    return {"message": "ok", "code": 0}


async def gen_response(request, count: int = 5):
    try:
        print(f"client, connected {request.client}. start streaming")
        for c in range(count):
            await asyncio.sleep(0.1)
            yield b"some chunk"
    except asyncio.CancelledError:  # pragma: no cover
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
                yield UserDB.from_orm(user).json() + "\n"
    except asyncio.CancelledError:  # pragma: no cover
        pass


@app.get("/user")
async def get_users():
    return StreamingResponse(users_stream())


@app.post("/user", response_model=UserDB)
async def post_item(user: UserPost):
    try:
        async with AsyncSession(engine) as session:
            new_user = User.from_pd(user)
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
        return new_user
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Can't create user [{user}] with exception: {exc}")


@app.post("/item", response_model=ItemDB)
async def post_item(item: ItemPost):
    async with AsyncSession(engine) as session:
        try:
            user = await session.get(User, item.user_id)
            new_item = Item.from_pd(item)
            new_item.user = user
            session.add(new_item)
            await session.flush()

        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail=f"Data [{item}] is not added")

        await session.commit()
        await session.refresh(new_item)

    return new_item


@app.patch("/item/{item_id}", response_model=ItemDB)
async def patch_item(item: ItemPatch, item_id: int):
    async with AsyncSession(engine) as session:
        try:
            patched_item = await session.get(Item, item_id)

            if not patched_item:
                raise HTTPException(status_code=404, detail=f"Item with id={item_id} is not found")

            patched_item.update_from_pd(item)
            session.add(patched_item)
            await session.flush()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail=f"Item with id={item_id} is not updated with data [{item}]")

        await session.commit()
        await session.refresh(patched_item)
    return patched_item

if __name__ == '__main__': # pragma: no cover
    uvicorn.run(app)
