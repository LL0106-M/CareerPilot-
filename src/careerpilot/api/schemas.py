from pydantic import BaseModel, ConfigDict, Field

from careerpilot.support.policy import SupportMode


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8_000)
    support_mode: SupportMode | None = None


class ChatResponse(BaseModel):
    reply: str
    support_mode: SupportMode
    memory_read_status: str
    memory_write_status: str
    dreaming_status: str
