# -------------------------------
# Request Model
# -------------------------------
from pydantic import BaseModel


class Query(BaseModel):
    user_query: str
