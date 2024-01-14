from datetime import datetime
from typing import Counter, List, Literal, Optional, Tuple

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.db.components import PredictionEvent

DATA_REGION = Literal["CN", "US"]


class Contest(Document):
    titleSlug: str
    title: str
    startTime: datetime
    duration: int
    endTime: datetime
    past: bool
    update_time: datetime = Field(default_factory=datetime.utcnow)
    predict_time: Optional[datetime] = None
    user_count_us: Optional[int] = None
    user_count_cn: Optional[int] = None
    convolution_array: Optional[int] = None
    prediction_progress: Optional[List[PredictionEvent]] = None

    class Settings:
        indexes = [
            IndexModel("titleSlug", unique=True),
            "title",
            "startTime",
            "endTime",
            "predict_time",
        ]


class ContestRecord(Document):
    contest_name: str
    contest_id: int
    username: str
    user_slug: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    rank: int
    score: int
    finish_time: datetime
    data_region: DATA_REGION

    class Settings:
        indexes = [
            "contest_name",
            "username",
            "user_slug",
            "rank",
            "data_region",
        ]


class ContestRecordPredict(ContestRecord):
    # Predicted records' will be inserted only once, won't update any fields.
    # Records in this collection can be used to calculated MSE directly even after a long time because it won't change.
    insert_time: datetime = Field(default_factory=datetime.utcnow)
    attendedContestsCount: Optional[int] = None
    old_rating: Optional[float] = None
    new_rating: Optional[float] = None
    delta_rating: Optional[float] = None
    predict_time: Optional[datetime] = None


class ContestRecordArchive(ContestRecord):
    # Archived records will be updated.
    # LeetCode would rejudge some submissions(cheat detection, add test cases, etc.)
    update_time: datetime = Field(default_factory=datetime.utcnow)
    real_time_rank: Optional[list] = None


class Question(Document):
    question_id: int
    credit: int
    title: str
    title_slug: str
    update_time: datetime = Field(default_factory=datetime.utcnow)
    contest_name: str
    qi: int
    real_time_count: Optional[List[int]] = None
    # For every question, save the quantiles of users' ratings who passed that question.
    user_ratings_quantiles: Optional[List[float]] = None
    # For every question, save the rating bins for users who passed each question.
    # Each tuple represents a rating range, and the second element is the count of users within that range.
    # For example, if 888 users have ratings in the range `[1100, 1150)`, the tuple would be `(1100, 888)`.
    # The default range is 50, maintaining consistency with the distribution chart on LeetCode user homepages.
    user_ratings_bins: Optional[List[Tuple[int, int]]] = None
    average_fail_count: Optional[int] = None
    lang_counter: Optional[Counter] = None
    difficulty: Optional[float] = None
    # For every question, save the first 10 users who finished this question
    first_ten_users: Optional[List[Tuple[str, datetime]]] = None
    topics: Optional[List[str]] = None

    class Settings:
        indexes = [
            "question_id",
            "title_slug",
            "contest_name",
        ]


class Submission(Document):
    # these four can be used as compound Index
    contest_name: str
    username: str
    data_region: DATA_REGION
    question_id: int
    date: datetime
    fail_count: int
    credit: int
    submission_id: int
    status: int
    contest_id: int
    update_time: datetime = Field(default_factory=datetime.utcnow)
    # watch out: US data_region doesn't have `lang` field before weekly-contest-364
    lang: Optional[str] = None

    class Settings:
        indexes = [
            "contest_name",
            "username",
            "data_region",
            "question_id",
            "date",
        ]


class User(Document):
    username: str
    user_slug: str
    data_region: DATA_REGION
    attendedContestsCount: int
    rating: float
    update_time: datetime = Field(default_factory=datetime.utcnow)
    # TODO: add historical ranking field, save into an array. (ranking.length = attendedContestsCount)

    class Settings:
        indexes = [
            "username",
            "user_slug",
            "data_region",
            "rating",
        ]
