from pydantic import BaseModel, ConfigDict


class CenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    department_id: int | None
