import os
import sys
import json
import asyncio
import logging

import asyncpg
import aiohttp
import redis.asyncio as redis


CHANNEL_NAME = os.environ.get('CHANNEL_NAME', 'notification')
BEARER_TOKEN = os.environ.get('BEARER_TOKEN', 'AAAAAAAAAAAAAAAAAAAAADFbbgEAAAAAgbDQ72%2BKSSj4LUlfXndxsYyAs1c%3D7rYx14Ozbpzl7dJF4DkCsWxj198YKHM60emOl7bDtZhO24TQ4h')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/foo')

logger = logging.getLogger('aiohttp_test')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


headers = {
    'Authorization': f'Bearer {BEARER_TOKEN}',
}

GET_USER_INFO = "https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics,description"
GET_USER_TWEETS = "https://api.twitter.com/2/users/{user_id}/tweets"

async def get_user_tweets(user_id, session):
    async with session.get(GET_USER_TWEETS.format(user_id=user_id)) as resp:       
        data = await resp.json()
        data = [tweet['text'] for tweet in data['data']]
        return data

async def download_and_save_user(username: str, conn):
    conn = await asyncpg.connect(DATABASE_URL)
    # write real code here
    logger.debug(f"Start pulling info about user {username}")
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(GET_USER_INFO.format(username=username)) as resp: 
            data = {}
            try:      
                data = await resp.json()                    # Grab response
                data = data['data']
            except KeyError:
                print(data, username)
            logger.debug(data)
            tweets = await get_user_tweets(data['id'], session)
            q = f'''
                UPDATE users SET status='finished', twitter_id='{data['id']}', name='{data['name']}', description=$1,
                following={data['public_metrics']['following_count']}, followers={data['public_metrics']['followers_count']},
                tweets=$2 WHERE username='{username}';
            '''
            await conn.execute(q, data['description'], tweets)
    logger.debug(f"Finish pulling info about user {username}")
    

async def handle_notification():
    r = redis.Redis(host='localhost')
    pubsub = r.pubsub()
    conn = await asyncpg.connect(DATABASE_URL)
    await pubsub.subscribe(CHANNEL_NAME)
    while True:
        message = await pubsub.get_message()
        if message and message["type"] == "message":
            data = json.loads(message["data"])
            print(data)
            for item in data:
                asyncio.create_task(download_and_save_user(item, conn))


if __name__ == "__main__":
    asyncio.run(handle_notification())
    #asyncio.run(download_and_save_user('elonmusk'))