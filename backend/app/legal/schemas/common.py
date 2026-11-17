from sqlmodel import Field, SQLModel


class IdempotentMutation(SQLModel):
    idempotency_key: str = Field(min_length=8, max_length=256)
    expected_version: int = Field(ge=1)
