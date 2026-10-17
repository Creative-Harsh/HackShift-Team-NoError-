from typing import Literal
from uuid import UUID

from pydantic import Field
from app.schemas import StrictModel

DiseaseCode = Literal['lsd', 'fmd', 'respiratory', 'gastrointestinal']


class Operation(StrictModel):
    operation_id: UUID
    expected_version: int = Field(ge=1)


class Assignment(Operation):
    vet_id: str | None = None


class Review(Operation):
    diagnosis: str = Field(min_length=3, max_length=2000)
    recommendations: str = Field(min_length=3, max_length=4000)


class SampleRequest(Operation):
    test_type: str = Field(min_length=3, max_length=160)
    disease_code: DiseaseCode | None = None
    notes: str = Field(default='', max_length=2000)


class LabUpdate(Operation):
    status: Literal['received', 'testing', 'positive', 'negative', 'inconclusive']
    result_notes: str = Field(default='', max_length=4000)
    confirmed_disease: DiseaseCode | None = None
    attachment_url: str | None = Field(default=None, pattern=r'^/api/media/[a-zA-Z0-9-]+$')


class CaseTransition(Operation):
    status: Literal['treatment', 'closed']
    note: str = Field(min_length=3, max_length=4000)
