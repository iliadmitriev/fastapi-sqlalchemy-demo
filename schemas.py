from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserPost(BaseModel):
    id: Optional[int]
    name: str
    login: str


class UserDB(UserPost):
    class Config:
        orm_mode = True


class ItemPost(BaseModel):
    id: Optional[int]
    title: str
    weight: float = 0.0
    released: Optional[datetime]
    user_id: int


class ItemDB(ItemPost):
    class Config:
        orm_mode = True

