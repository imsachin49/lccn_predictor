import asyncio
import copy
from datetime import datetime, timedelta
from typing import List, Optional

from loguru import logger
import httpx
from beanie.odm.operators.update.general import Set

from app.constants import DEFAULT_NEW_USER_RATING, DEFAULT_NEW_USER_ATTENDED_CONTESTS_COUNT
from app.crawler.utils import multi_http_request
from app.db.models import ContestRecordArchive, User, ContestRecordPredict
from app.utils import exception_logger_reraise


async def multi_upsert_user(
        graphql_response_list: List[Optional[httpx.Response]],
        multi_request_list: List[ContestRecordPredict | ContestRecordArchive],
) -> None:
    update_tasks = list()
    for response, contest_record in zip(graphql_response_list, multi_request_list):
        try:
            data = response.json().get("data", {}).get("userContestRanking")
            logger.info(f"contest_record={contest_record}, data={data}")
            if data is None:
                logger.info(f"new user found, contest_record={contest_record}. graphql data is None")
                attended_contests_count = DEFAULT_NEW_USER_ATTENDED_CONTESTS_COUNT
                rating = DEFAULT_NEW_USER_RATING
            else:
                attended_contests_count = data["attendedContestsCount"]
                rating = data["rating"]
            user = User(
                username=contest_record.username,
                user_slug=contest_record.user_slug,
                data_region=contest_record.data_region,
                attendedContestsCount=attended_contests_count,
                rating=rating,
            )
        except Exception as e:
            # This is a bug that will cause **inaccurate prediction**, because missing user in User collection
            # will be processed as new user using default value (rating, count)=(1500, 0).
            # possible reasons:
            # 1. `response` could be `None` because failed times reached `retry_num` in `multi_http_request` function.
            # 2. graphql result userContestRanking doesn't have `attendedContestsCount` or `rating` key.
            logger.exception(f"user parse error. response={response} contest_record={contest_record} Exception={e}")
            continue
        update_tasks.append(
            User.find_one(
                User.username == user.username,
                User.data_region == user.data_region,
            ).upsert(
                Set(
                    {
                        User.update_time: user.update_time,
                        User.attendedContestsCount: user.attendedContestsCount,
                        User.rating: user.rating,
                    }
                ),
                on_insert=user,
            )
        )
    await asyncio.gather(*update_tasks)


async def multi_request_user_cn(
        cn_multi_request_list: List[ContestRecordPredict | ContestRecordArchive],
) -> None:
    cn_response_list = await multi_http_request(
        {
            contest_record.user_slug: {
                "url": "https://leetcode.cn/graphql/noj-go/",
                "method": "POST",
                "json": {
                    "query": """
                             query userContestRankingInfo($userSlug: String!) {
                                    userContestRanking(userSlug: $userSlug) {
                                        attendedContestsCount
                                        rating
                                    }
                                }
                             """,
                    "variables": {"userSlug": contest_record.user_slug},
                },
            }
            for contest_record in cn_multi_request_list
        },
        concurrent_num=5,
    )
    await multi_upsert_user(cn_response_list, cn_multi_request_list)
    cn_multi_request_list.clear()


async def multi_request_user_us(
        us_multi_request_list: List[ContestRecordPredict | ContestRecordArchive],
) -> None:
    us_response_list = await multi_http_request(
        {
            contest_record.username: {
                "url": "https://leetcode.com/graphql/",
                "method": "POST",
                "json": {
                    "query": """
                             query getContestRankingData($username: String!) {
                                userContestRanking(username: $username) {
                                    attendedContestsCount
                                    rating
                                }
                             }
                             """,
                    "variables": {"username": contest_record.username},
                },
            }
            for contest_record in us_multi_request_list
        },
        concurrent_num=5,
    )
    await multi_upsert_user(us_response_list, us_multi_request_list)
    us_multi_request_list.clear()


@exception_logger_reraise
async def save_users_of_contest(
        contest_name: str,
        predict: bool,
        concurrent_num: int = 200,
) -> None:
    if predict:
        to_be_queried = ContestRecordPredict.find(
            ContestRecordPredict.contest_name == contest_name,
            ContestRecordPredict.score != 0,  # for prediction, just focus on records which have a score.
            batch_size=10,
        )
    else:
        to_be_queried = ContestRecordArchive.find(
            ContestRecordArchive.contest_name == contest_name,
            batch_size=10,
        )
    cn_multi_request_list = list()
    us_multi_request_list = list()
    async for contest_record in to_be_queried:
        if predict and await User.find_one(
            User.username == contest_record.username,
            User.data_region == contest_record.data_region,
            User.update_time > datetime.utcnow() - timedelta(hours=36),  # skip if user was updated in last 36 hours.
        ) is not None:
            logger.info(f"user was updated in last three days, won't update. "
                        f"contest_record = {contest_record} ")
            continue
        if len(cn_multi_request_list) + len(us_multi_request_list) >= concurrent_num:
            logger.trace(f"for loop run multi_request_list "
                         f"cn_multi_request_list={cn_multi_request_list} "
                         f"us_multi_request_list={us_multi_request_list}")
            await asyncio.gather(
                multi_request_user_cn(cn_multi_request_list),
                multi_request_user_us(us_multi_request_list),
            )
        if contest_record.data_region == "CN":
            cn_multi_request_list.append(contest_record)
        elif contest_record.data_region == "US":
            us_multi_request_list.append(contest_record)
        else:
            logger.critical(f"fatal error: data_region is not CN or US. contest_record={contest_record}")
    logger.trace(f"rest of run run multi_request_list "
                 f"cn_multi_request_list={cn_multi_request_list} "
                 f"us_multi_request_list={us_multi_request_list}")
    await asyncio.gather(
        multi_request_user_cn(cn_multi_request_list),
        multi_request_user_us(us_multi_request_list),
    )

