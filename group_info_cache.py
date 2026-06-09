from __future__ import annotations

import asyncio
import copy
import time
from typing import Any

from astrbot.api import logger
from astrbot.api.star import Context


class GroupInfoCache:
    """从 QQ API 获取群名称和头像的缓存"""

    def __init__(self, context: Context, ttl_seconds: int = 120):
        self.context = context
        self.ttl_seconds = ttl_seconds

        self._lock = asyncio.Lock()
        self._last_refresh_at = 0.0
        self._group_list_cache: list[dict[str, Any]] = []
        self._group_detail_cache: dict[str, dict[str, Any]] = {}

    async def list_groups(self, force: bool = False) -> list[dict[str, Any]]:
        if force or not self._is_fresh() or not self._group_list_cache:
            await self._refresh_group_list(force=force)
        return copy.deepcopy(self._group_list_cache)

    async def get_group(self, group_id: str, force: bool = False) -> dict[str, Any]:
        normalized = str(group_id).strip()
        if not normalized:
            raise ValueError("group_id must not be empty")

        if (
            force
            or not self._is_fresh()
            or normalized not in self._group_detail_cache
        ):
            await self._refresh_group_list(force=force)

        cached = self._group_detail_cache.get(normalized)
        if cached and not force and self._is_fresh():
            return copy.deepcopy(cached)

        detail = await self._load_group_detail(normalized)
        self._group_detail_cache[normalized] = detail
        return copy.deepcopy(detail)

    def invalidate(self, group_id: str | None = None) -> None:
        if group_id:
            self._group_detail_cache.pop(str(group_id).strip(), None)
            return
        self._group_detail_cache.clear()
        self._last_refresh_at = 0.0

    def _is_fresh(self) -> bool:
        return (time.time() - self._last_refresh_at) < self.ttl_seconds

    async def _refresh_group_list(self, force: bool = False) -> None:
        async with self._lock:
            if not force and self._is_fresh() and self._group_list_cache:
                return

            merged: dict[str, dict[str, Any]] = {}

            for client in self._iter_clients():
                try:
                    result = await client.call_action("get_group_list")
                    for item in self._extract_list(result):
                        group_id = str(item.get("group_id", "")).strip()
                        if not group_id or group_id in merged:
                            continue
                        merged[group_id] = self._normalize_group(item)
                except Exception as exc:
                    logger.warning("获取群列表失败: %s", exc)

            self._group_list_cache = list(merged.values())
            self._group_detail_cache = merged
            self._last_refresh_at = time.time()

    async def _load_group_detail(self, group_id: str) -> dict[str, Any]:
        cached = self._group_detail_cache.get(group_id)
        if cached:
            return copy.deepcopy(cached)

        for client in self._iter_clients():
            try:
                result = await client.call_action(
                    "get_group_info", group_id=int(group_id)
                )
                info = self._extract_object(result)
                if info:
                    detail = self._normalize_group(info)
                    self._group_detail_cache[group_id] = detail
                    return copy.deepcopy(detail)
            except Exception as exc:
                logger.debug("获取群详情失败 %s: %s", group_id, exc)

        return self._build_fallback_group(group_id)

    def _iter_clients(self) -> list[Any]:
        clients: list[Any] = []
        try:
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import (
                AiocqhttpAdapter,
            )
        except ImportError:
            return clients

        for inst in self.context.platform_manager.platform_insts:
            if not isinstance(inst, AiocqhttpAdapter):
                continue
            try:
                client = inst.get_client()
            except Exception:
                continue
            if client is not None:
                clients.append(client)
        return clients

    @classmethod
    def _normalize_group(cls, raw: dict[str, Any]) -> dict[str, Any]:
        group_id = str(raw.get("group_id", "")).strip()
        return {
            "group_id": group_id,
            "group_name": str(raw.get("group_name", "")).strip()
            or f"群 {group_id}",
            "avatar": cls._build_avatar(group_id),
            "member_count": cls._safe_int(raw.get("member_count"), 0),
            "max_member_count": cls._safe_int(raw.get("max_member_count"), 0),
        }

    @classmethod
    def _build_fallback_group(cls, group_id: str) -> dict[str, Any]:
        return {
            "group_id": group_id,
            "group_name": f"群 {group_id}",
            "avatar": cls._build_avatar(group_id),
            "member_count": 0,
            "max_member_count": 0,
        }

    @staticmethod
    def _build_avatar(group_id: str) -> str:
        return f"https://p.qlogo.cn/gh/{group_id}/{group_id}/640"

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_list(result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_object(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, dict):
                return data
            return result
        return {}
