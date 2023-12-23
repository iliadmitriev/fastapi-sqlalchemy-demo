from typing import Annotated

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class AlsoCommonParams(BaseModel):
    a: str = Field(Query(..., example=1, description="this is a"))
    b: int = Field(Query(..., example=2, description="this is b", ge=0))


@app.get("/")
async def get_root(
    params: Annotated[AlsoCommonParams, Depends()],
):
    return {
        "a": params.a,
        "b": params.b,
    }
