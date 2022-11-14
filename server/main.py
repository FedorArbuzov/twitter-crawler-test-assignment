import os
import json

import redis
from fastapi import FastAPI, Depends, status
from fastapi.responses import JSONResponse
from fastapi_asyncpg import configure_asyncpg

app = FastAPI()
r = redis.Redis(host='localhost', port=6379, db=0)
CHANNEL_NAME = os.environ.get('CHANNEL_NAME', 'notification')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/foo')
db = configure_asyncpg(app, DATABASE_URL)


@db.on_init
async def initialization(conn):
    # db initialization code here
    await conn.fetch("DROP TABLE IF EXISTS  users;")
    await conn.fetch("DROP SEQUENCE IF EXISTS tasks;")
    
    await conn.fetch("CREATE SEQUENCE tasks START 1;")
    res = await conn.fetch('''CREATE TABLE users (
        task_id       integer,
        status        varchar,
        twitter_id    varchar,
        name          varchar,
        username      varchar,
        following     integer,
        followers     integer,
        description   varchar,
        tweets        text[]
    );''')
    print('init db')


def get_or_404(data):
    try:
        return JSONResponse(status_code=status.HTTP_200_OK, content=dict(data[0]))
    except IndexError:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={})


@app.get("/api/tweets/{twitter_id}")
async def get_userinfo(twitter_id: str, db=Depends(db.connection)):
    data = await db.fetch(f"SELECT * FROM users WHERE twitter_id='{twitter_id}';")
    return get_or_404(data)


@app.get("/api/user/{username}")
async def get_tweets_by_username(username: str, db=Depends(db.connection)):
    data = await db.fetch(f"SELECT * FROM users WHERE username='{username}';")
    return get_or_404(data)


@app.get("/api/users/status/")
async def check_task_status(task_id: int = 1, db=Depends(db.connection)):
    rows = await db.fetch(f"SELECT username, status FROM users WHERE task_id={task_id};")
    return [dict(r) for r in rows]


@app.post("/api/users")
async def mutate_something_compled(users: list[str], db=Depends(db.connection)):
    users = [user.split('/')[-1] for user in users]
    r.publish(CHANNEL_NAME, json.dumps(users))
    result = await db.fetchrow('''SELECT nextval('tasks');''')
    values = [f"('{user}', {result[0]}, 'pending')" for user in users]
    values = ', '.join(values)
    await db.execute(f'''INSERT INTO users (username, task_id, status)
                            VALUES {values};''')
    return {'id': result[0]}
