from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdminUserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["SUPER_ADMIN", "ADMIN", "COACH", "CLIENT", "LEAD"] | None = None
    active: bool | None = None
