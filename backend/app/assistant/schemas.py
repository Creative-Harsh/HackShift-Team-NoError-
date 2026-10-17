from typing import Literal

from pydantic import Field, StrictBool, field_validator
from app.schemas import StrictModel

Language = Literal['en', 'hi', 'hinglish']
Intent = Literal['photo', 'voice_note', 'add_animal', 'vaccination', 'history', 'lookup', 'sample',
    'diagnosis', 'recommendations', 'treatment', 'lab_result', 'urgent_cases', 'outbreak', 'track', 'report', 'animals', 'help', 'unknown']
Page = Literal['home', 'animals', 'animal_new', 'animal_detail', 'report', 'cases', 'case_detail', 'laboratory', 'outbreaks', 'unknown']


class PageContext(StrictModel):
    page: Page
    targets: list[str] = Field(default_factory=list, max_length=60)
    case_id: str | None = Field(default=None, max_length=100)


class MessageInput(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    language: Language = 'en'
    external_consent: bool = False
    context: PageContext | None = None


class IntentExtraction(StrictModel):
    intent: Intent
    evidence: str = Field(max_length=200)


class Observations(StrictModel):
    symptoms: dict[str, StrictBool | None] = Field(default_factory=dict)
    appetite: Literal['normal', 'reduced', 'none'] | None = None
    activity: Literal['normal', 'reduced', 'recumbent'] | None = None
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    duration_hours: float | None = Field(default=None, ge=0, le=2160)
    mortality_count: int | None = Field(default=None, ge=0, le=1000)

    @field_validator('symptoms')
    @classmethod
    def known_symptoms(cls, value):
        from app.schemas import SYMPTOMS
        if set(value) - SYMPTOMS:
            raise ValueError('Unknown symptom concept')
        if any(v is not None and type(v) is not bool for v in value.values()):
            raise ValueError('Symptoms must be true, false or unknown')
        return value


class ConcernInput(StrictModel):
    animal_id: str = Field(min_length=1, max_length=100)
    observations: Observations
    verified: Literal[True]

    @field_validator('verified', mode='before')
    @classmethod
    def explicit_verification(cls, value):
        if value is not True:
            raise ValueError('Explicit observation verification is required')
        return value


class GuidanceResponse(StrictModel):
    intent: Intent = 'unknown'
    target: str | None = None
    message_key: Literal['unknown', 'consent', 'denied', 'point', 'statusMissing'] = 'unknown'
    source: Literal['local', 'gemini', 'fallback'] = 'local'
    case_status: str | None = None
    # No provider prose, arbitrary URLs/selectors, form values or executable actions.
