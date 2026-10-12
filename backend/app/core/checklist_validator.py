from pydantic import BaseModel, Field


class GeneratedChecklistItem(BaseModel):
    item_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    control: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    audit_step: str = Field(min_length=1)