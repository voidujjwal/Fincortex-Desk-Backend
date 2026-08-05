from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    name: str
    provider: str
    description: str


class AvailableModelsResponse(BaseModel):
    models: list[ModelInfo]