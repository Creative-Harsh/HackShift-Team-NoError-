from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal['farmer', 'paravet', 'vet', 'lab', 'admin']
Species = Literal['cattle', 'buffalo', 'goat', 'sheep', 'pig']
SYMPTOMS = {'fever', 'cough', 'nasal_discharge', 'drooling', 'skin_lesions', 'mouth_foot_lesions', 'diarrhea', 'weakness', 'swelling'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class Login(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Register(Login):
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)
    district: str = Field(min_length=2, max_length=100)


class Point(StrictModel):
    type: Literal['Point'] = 'Point'
    coordinates: tuple[float, float]

    @field_validator('coordinates')
    @classmethod
    def coordinates_valid(cls, value):
        lon, lat = value
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError('GeoJSON coordinates must be [longitude -180..180, latitude -90..90]')
        return value


class AnimalInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    pashu_id: str | None = Field(default=None, pattern=r'^\d{12}$')
    species: Species
    breed: str = Field(min_length=1, max_length=80)
    age_months: int = Field(ge=0, le=480)
    gender: Literal['female', 'male']
    owner_id: str | None = None
    location: Point
    village: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=2, max_length=100)


class VaccinationInput(StrictModel):
    vaccine: str = Field(min_length=2, max_length=100)
    date_given: date
    next_due_date: date

    @model_validator(mode='after')
    def valid_dates(self):
        if self.date_given > date.today() or self.next_due_date <= self.date_given:
            raise ValueError('Vaccination must be in the past and next due date after administration')
        return self


class ReportInput(StrictModel):
    client_report_id: UUID
    animal_id: str = Field(min_length=1, max_length=100)
    symptoms: list[str] = Field(default_factory=list, max_length=9)
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    appetite: Literal['normal', 'reduced', 'none'] = 'normal'
    milk_drop_percent: float = Field(default=0, ge=0, le=100)
    activity: Literal['normal', 'reduced', 'recumbent'] = 'normal'
    recent_contact: bool = False
    vaccination_status: Literal['up_to_date', 'overdue', 'unknown'] = 'unknown'
    mortality_count: int = Field(default=0, ge=0, le=1000)
    duration_hours: float = Field(ge=0, le=2160)
    location: Point
    reported_at: datetime | None = None
    image_url: str | None = Field(default=None, max_length=500)
    voice_note_url: str | None = Field(default=None, max_length=500)

    @field_validator('symptoms')
    @classmethod
    def known_symptoms(cls, value):
        if set(value) - SYMPTOMS:
            raise ValueError('Unknown structured symptom')
        return sorted(set(value))

    @field_validator('reported_at')
    @classmethod
    def valid_timestamp(cls, value):
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError('Use a timezone-aware report timestamp')
        value = value.astimezone(timezone.utc)
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('Report time cannot be in the future')
        return value.replace(microsecond=(value.microsecond // 1000) * 1000)

    @field_validator('image_url', 'voice_note_url')
    @classmethod
    def private_media_only(cls, value):
        if value and not re.fullmatch(r'/api/media/[a-zA-Z0-9-]+', value):
            raise ValueError('Upload attachments through the authenticated media endpoint')
        return value
