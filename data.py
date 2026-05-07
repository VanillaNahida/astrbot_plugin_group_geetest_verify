import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from astrbot.api import logger


class VerifyStateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._cache: dict = {}
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def init(self):
        async with self._init_lock:
            if self._initialized:
                return

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row

            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS verify_states (
                    state_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    question TEXT,
                    answer INTEGER,
                    wrong_count INTEGER DEFAULT 0,
                    verify_method TEXT,
                    max_wrong_answers INTEGER DEFAULT 5,
                    verify_time REAL,
                    created_at REAL
                );
            """)
            await self._conn.commit()

            async with self._conn.execute("SELECT * FROM verify_states;") as cur:
                async for row in cur:
                    self._cache[row["state_key"]] = {
                        "status": row["status"],
                        "question": row["question"],
                        "answer": row["answer"],
                        "wrong_count": row["wrong_count"],
                        "verify_method": row["verify_method"],
                        "max_wrong_answers": row["max_wrong_answers"],
                        "verify_time": row["verify_time"],
                        "created_at": row["created_at"],
                    }

            self._initialized = True
            logger.info(f"[Geetest Verify] 初始化验证状态数据库 ({len(self._cache)} 个状态)")

    async def _save_to_db(self, state_key: str, data: dict):
        if not self._conn:
            raise RuntimeError("VerifyStateDB not initialized")

        await self._conn.execute(
            """
            INSERT INTO verify_states(state_key, status, question, answer, wrong_count, verify_method, max_wrong_answers, verify_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                status=excluded.status,
                question=excluded.question,
                answer=excluded.answer,
                wrong_count=excluded.wrong_count,
                verify_method=excluded.verify_method,
                max_wrong_answers=excluded.max_wrong_answers,
                verify_time=excluded.verify_time,
                created_at=excluded.created_at;
            """,
            (
                state_key,
                data.get("status", "pending"),
                data.get("question"),
                data.get("answer"),
                data.get("wrong_count", 0),
                data.get("verify_method"),
                data.get("max_wrong_answers", 5),
                data.get("verify_time"),
                data.get("created_at"),
            ),
        )
        await self._conn.commit()

    async def get(self, state_key: str) -> Optional[dict]:
        return self._cache.get(state_key)

    async def set(self, state_key: str, data: dict):
        if "created_at" not in data:
            existing = self._cache.get(state_key)
            if existing and "created_at" in existing:
                data["created_at"] = existing["created_at"]
            else:
                data["created_at"] = time.time()

        self._cache[state_key] = data
        await self._save_to_db(state_key, data)

    async def update_field(self, state_key: str, field: str, value):
        if state_key not in self._cache:
            return
        self._cache[state_key][field] = value
        await self._save_to_db(state_key, self._cache[state_key])

    async def delete(self, state_key: str):
        self._cache.pop(state_key, None)
        if self._conn:
            await self._conn.execute("DELETE FROM verify_states WHERE state_key = ?", (state_key,))
            await self._conn.commit()

    def contains(self, state_key: str) -> bool:
        return state_key in self._cache

    def get_cached(self, state_key: str) -> Optional[dict]:
        return self._cache.get(state_key)

    def all_keys(self) -> list:
        return list(self._cache.keys())

    async def cleanup_expired(self, max_age_seconds: float = 86400):
        now = time.time()
        expired_keys = []
        for key, data in self._cache.items():
            if data.get("status") in ("verified", "bypassed"):
                created_at = data.get("created_at") or data.get("verify_time") or 0
                if now - created_at > max_age_seconds:
                    expired_keys.append(key)

        for key in expired_keys:
            await self.delete(key)

        if expired_keys:
            logger.info(f"[Geetest Verify] 清理过期验证状态 {len(expired_keys)} 个")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False
