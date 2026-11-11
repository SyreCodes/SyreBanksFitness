from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class FAQ(BaseModel):
    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=2000)


class ProgramIntroduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cover_media_id: str | None = None
    intro_media_id: str | None = None
    demonstration_media_ids: list[str] = Field(default_factory=list, max_length=6)
    environment: Literal['Home', 'Gym', 'Either'] = 'Either'
    equipment: list[str] = Field(default_factory=list, max_length=12)
    days_per_week: int = Field(default=3, ge=1, le=7)
    minutes_per_session: int = Field(default=45, ge=10, le=180)
    suitability: str = Field(default='', max_length=3000)
    philosophy: str = Field(default='', max_length=3000)
    support: list[str] = Field(default_factory=list, max_length=20)
    measurement: str = Field(default='', max_length=3000)
    expectations: str = Field(default='', max_length=3000)
    faq: list[FAQ] = Field(default_factory=list, max_length=12)


class PriceInput(BaseModel):
    currency: Literal['RWF', 'USD']
    amount_minor: int = Field(ge=0, le=1_000_000_000)
    pricing_type: Literal['one_time', 'monthly', 'annual'] = 'one_time'


class CatalogInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default='', max_length=1000)
    full_description: str = Field(default='', max_length=12000)
    type: Literal['COACHING', 'MEMBERSHIP', 'DIGITAL'] = 'COACHING'
    status: Literal['DRAFT', 'PUBLISHED', 'ARCHIVED'] = 'DRAFT'
    active: bool = True
    featured: bool = False
    categories: list[str] = Field(default_factory=list, max_length=12)
    features: list[str] = Field(default_factory=list, max_length=30)
    prices: list[PriceInput] = Field(default_factory=list, max_length=2)
    program_ids: list[str] = Field(default_factory=list, max_length=50)
    cover_media_id: str | None = None
    preview_media_id: str | None = None
    paid_media_ids: list[str] = Field(default_factory=list, max_length=20)
    support_level: str = Field(default='', max_length=1000)
    duration: str = Field(default='', max_length=500)
    renewal: str = Field(default='', max_length=1000)
    cancellation: str = Field(default='', max_length=1000)
    suitability: str = Field(default='', max_length=2000)
    delivery: str = Field(default='', max_length=1000)
    availability: Literal['COMING_SOON', 'ENROLLMENT_OPEN', 'WAITLIST'] = 'COMING_SOON'
    faq: list[FAQ] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def unique_prices(self):
        if len({price.currency for price in self.prices}) != len(self.prices):
            raise ValueError('Configure each currency once')
        return self


class EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(default='', max_length=40)
    goal: str = Field(min_length=2, max_length=200)
    experience: Literal['Beginner', 'Intermediate', 'Advanced']
    environment: Literal['Home', 'Gym', 'Either']
    equipment: list[str] = Field(default_factory=list, max_length=12)
    training_days: list[int] = Field(min_length=1, max_length=7)
    obstacle: str = Field(default='', max_length=2000)
    program_id: str | None = None
    product_id: str | None = None
    kind: Literal['ENROLLMENT', 'WAITLIST', 'CONSULTATION'] = 'ENROLLMENT'
    consent: Literal[True]
    consent_version: str = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def valid_days(self):
        if len(set(self.training_days)) != len(self.training_days) or any(day not in range(1, 8) for day in self.training_days):
            raise ValueError('Choose distinct training days')
        return self


class GrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: str
    key: Literal['exercise_library', 'program_access', 'digital_product']
    resource_id: str = ''
    source_type: Literal['MANUAL', 'PILOT'] = 'PILOT'
    reason: str = Field(min_length=5, max_length=1000)
    expires_at: datetime


class LaunchFlags(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enrollment: bool = True
    digital_store: bool = True
    program_discovery: bool = True
