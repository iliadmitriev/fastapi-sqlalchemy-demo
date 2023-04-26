import asyncio
from datetime import datetime
from typing import Optional, Self, Type

from pydantic import BaseModel
from sqlalchemy import String, ForeignKey, URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, declared_attr


class Base(DeclarativeBase):

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def update_from_pd(self, source: BaseModel, exclude_unset=True, **kwargs):
        source_dict = source.dict(**kwargs, exclude_unset=exclude_unset)
        for field, value in source_dict.items():
            if hasattr(self, field):
                setattr(self, field, value)

        return self

    @classmethod
    def from_pd(cls, src: BaseModel, exclude_unset=True, **kwargs) -> Self:
        target = cls()

        source_dict = src.dict(**kwargs, exclude_unset=exclude_unset)
        for field, value in source_dict.items():
            if hasattr(cls, field):
                setattr(target, field, value)

        return target


class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    login: Mapped[str] = mapped_column(String(30), unique=True)
    items: Mapped[set['Item']] = relationship("Item", back_populates="user")


class Item(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(40))
    weight: Mapped[float] = mapped_column(default=0.0)
    released: Mapped[Optional[datetime]] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped[User] = relationship("User", back_populates="items")


conn_string = URL.create(
    drivername="postgresql+asyncpg",
    host="localhost",
    port=5432,
    username="user",
    password="secret",
    database="items"
)

engine = create_async_engine(
    conn_string,
    echo=False,
    connect_args={
        "server_settings": {
            "application_name": "fastapi-demo"
        }
    }
)


async def create_database():  # pragma: no cover
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        async with session.begin():
            if not await session.get(User, 1):
                session.add(
                    User(login="ivan", name="Ivanov Ivan")
                )


if __name__ == '__main__':  # pragma: no cover
    """
    docker rm -f items-pg 
    
    docker run -d --name items-pg -e POSTGRES_DB=items \
      -e POSTGRES_USER=user -e POSTGRES_PASSWORD=secret\
      -p 5432:5432 postgres:alpine 
    """
    asyncio.run(create_database())
