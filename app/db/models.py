from typing import Optional
from pydantic import BaseModel, validator
from beanie import Document, Indexed
from datetime import datetime


class Contest(Document):
    contest_name: Indexed(str)
    contest_id: int
    username: Indexed(str)
    user_slug: Indexed(str)
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    rank: Indexed(int)
    score: int
    finish_time: int
    data_region: Indexed(str)

    # @validator('contest_name')
    # def contest_must_be_weekly_or_biweekly(cls, v):
    #     pass


class ContestPredict(Contest):
    insert_time: datetime


class ContestFinal(Contest):
    # leetcode will rejudge some submissions(cheat detection, add test cases, etc.), so will update here.
    update_time: datetime


class User(Document):
    username: Indexed(str)
    user_slug: Indexed(str)
    latest_rating: int
    latest_count: int
    # TODO: add historical rating



