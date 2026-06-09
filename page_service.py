from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger

from .group_info_cache import GroupInfoCache

DEFAULT_GROUP_ID = "__default__"
_INTERNAL_STATE_FILE = "_internal_state.json"


class PageService:
    def __init__(self, config: AstrBotConfig, plugin_dir: Path, group_cache: GroupInfoCache, on_config_saved: Callable[[], None] | None = None):
        self.config = config
        self.plugin_dir = plugin_dir
        self.group_cache = group_cache
        self._on_config_saved = on_config_saved
        self.schema = self._load_schema()
        self._internal_cache: dict[str, Any] | None = None

    def _load_schema(self) -> dict[str, Any]:
        schema_path = self.plugin_dir / "_conf_schema.json"
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Failed to load _conf_schema.json: {exc}")
            return {}

    # ── internal state (separate JSON file, not in main config) ──

    def _get_internal_path(self) -> Path:
        return self.plugin_dir / _INTERNAL_STATE_FILE

    def _load_internal(self) -> dict[str, Any]:
        if self._internal_cache is not None:
            return self._internal_cache
        path = self._get_internal_path()
        try:
            self._internal_cache = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._internal_cache = {}
        # 迁移旧数据
        migrated = False
        if "disposal" not in self._internal_cache and "disposal" in self.config:
            self._internal_cache["disposal"] = copy.deepcopy(self.config["disposal"])
            migrated = True
        if "enabled_groups" not in self._internal_cache and "enabled_groups" in self.config:
            self._internal_cache["enabled_groups"] = copy.deepcopy(self.config["enabled_groups"])
            migrated = True
        if migrated:
            self._save_internal()
        return self._internal_cache

    def _save_internal(self) -> None:
        path = self._get_internal_path()
        path.write_text(json.dumps(self._internal_cache or {}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_internal(self, key: str, default: Any = None) -> Any:
        return self._load_internal().get(key, default)

    def _set_internal(self, key: str, value: Any) -> None:
        self._load_internal()
        self._internal_cache[key] = value
        self._save_internal()

    @property
    def default_schema(self) -> dict[str, Any]:
        """群级别配置的 schema（group_configs.template_list.default_config.items）"""
        group_configs_schema = self.schema.get("group_configs", {})
        templates = group_configs_schema.get("templates", {})
        default_config = templates.get("default_config", {})
        return default_config.get("items", {})

    @property
    def global_schema(self) -> dict[str, Any]:
        """全局配置 schema（排除 group_configs）"""
        result = {}
        for key, value in self.schema.items():
            if key != "group_configs":
                result[key] = value
        return result

    # ── bootstrap ──

    async def get_bootstrap(self) -> dict[str, Any]:
        groups = [self._build_default_entry()]
        live_groups = await self.group_cache.list_groups()

        for cfg in self._get_group_configs():
            group_id = cfg.get("group_id", "")
            live_info = self._find_live_group(live_groups, group_id)
            groups.append(self._build_group_entry(cfg, live_info))

        return {
            "schema": {
                "global": self.global_schema,
                "default": self.default_schema,
            },
            "groups": groups,
            "global_config": self._get_global_config(),
        }

    # ── available groups ──

    async def get_available_groups(self) -> list[dict[str, Any]]:
        """返回尚未配置的群列表"""
        live_groups = await self.group_cache.list_groups()
        existing_ids = {str(cfg.get("group_id", "")) for cfg in self._get_group_configs()}
        available = []
        for g in live_groups:
            gid = str(g.get("group_id", ""))
            if gid and gid not in existing_ids:
                available.append(g)
        return available

    # ── config read ──

    def _get_global_config(self) -> dict[str, Any]:
        """读取所有全局配置项（排除 group_configs）"""
        result = {}
        for key in self.schema:
            if key != "group_configs" and key in self.config:
                result[key] = copy.deepcopy(self.config[key])
        return result

    def _get_group_configs(self) -> list[dict[str, Any]]:
        """获取群级别配置列表（与 config.py 共享 self.config['group_configs']）"""
        return copy.deepcopy(self.config.get("group_configs", []))

    def _get_default_group_config(self) -> dict[str, Any]:
        """获取默认群配置（disposal.default 或从全局配置推断）"""
        disposal = self._get_internal("disposal", {})
        if "default" in disposal:
            return copy.deepcopy(disposal["default"])
        # 从全局配置推断默认值
        result = {}
        for key in self.default_schema:
            if key != "group_id" and key in self.config:
                result[key] = copy.deepcopy(self.config[key])
        return result

    # ── config write ──

    def _notify_config_changed(self) -> None:
        """通知插件重新加载配置（更新运行时属性）"""
        if self._on_config_saved:
            try:
                self._on_config_saved()
            except Exception as exc:
                logger.warning(f"Failed to notify config change: {exc}")

    def _save_config(self) -> None:
        self.config.save_config()
        self._notify_config_changed()

    def _save_group_configs(self, group_configs: list[dict[str, Any]]) -> None:
        """保存群配置列表，写入 self.config['group_configs']（与 config.py 共享）"""
        self.config["group_configs"] = group_configs
        self._save_config()

    def _save_default_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """保存默认群配置（仅保存非空数据，避免覆盖）"""
        if data:
            disposal = self._get_internal("disposal", {})
            disposal["default"] = data
            self._set_internal("disposal", disposal)
            self._save_config()
        return self._build_default_entry()

    def _save_global_config(self, data: dict[str, Any]) -> None:
        """保存全局配置项"""
        for key, value in data.items():
            if key != "group_configs":
                self.config[key] = value
        self._save_config()

    # ── single group CRUD ──

    async def get_group_config(self, group_id: str) -> dict[str, Any]:
        if group_id == DEFAULT_GROUP_ID:
            return self._build_default_group_detail()

        live_info = None
        try:
            live_info = await self.group_cache.get_group(group_id)
        except Exception:
            pass

        group_configs = self._get_group_configs()
        for cfg in group_configs:
            if str(cfg.get("group_id", "")) == str(group_id):
                return self._build_group_detail(cfg, live_info)

        raise ValueError(f"Group config not found: {group_id}")

    def save_group_config(self, group_id: str, data: dict[str, Any], global_config: dict[str, Any] | None = None) -> dict[str, Any]:
        if group_id == DEFAULT_GROUP_ID:
            # 保存全局配置
            if global_config:
                self._save_global_config(global_config)
            return self._save_default_config(data)

        return self._save_custom_group_config(group_id, data)

    def _save_custom_group_config(self, group_id: str, data: dict[str, Any]) -> dict[str, Any]:
        group_configs = self._get_group_configs()

        found = False
        for cfg in group_configs:
            if str(cfg.get("group_id", "")) == str(group_id):
                template_key = cfg.get("__template_key", "default_config")
                cfg.clear()
                cfg.update(data)
                cfg["group_id"] = group_id
                cfg["__template_key"] = template_key
                found = True
                break

        if not found:
            data["group_id"] = group_id
            data["__template_key"] = "default_config"
            group_configs.append(data)

        self._save_group_configs(group_configs)

        for cfg in group_configs:
            if str(cfg.get("group_id", "")) == str(group_id):
                return self._build_group_entry(cfg)

        return self._build_group_entry({"group_id": group_id, **data})

    def delete_group_config(self, group_id: str) -> None:
        group_configs = self._get_group_configs()
        group_configs = [c for c in group_configs if str(c.get("group_id", "")) != str(group_id)]
        self._save_group_configs(group_configs)

    # ── entry builders (list) ──

    def _build_default_entry(self) -> dict[str, Any]:
        return {
            "group_id": DEFAULT_GROUP_ID,
            "group_name": "默认全局配置",
            "avatar": "",
            "is_default_group": True,
            "config": self._get_default_group_config(),
        }

    def _build_group_entry(
        self,
        cfg: dict[str, Any],
        live_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        group_id = str(cfg.get("group_id", ""))

        group_name = f"群 {group_id}"
        avatar = GroupInfoCache._build_avatar(group_id) if group_id else ""
        member_count = 0

        if live_info:
            group_name = live_info.get("group_name", group_name)
            avatar = live_info.get("avatar", avatar)
            member_count = live_info.get("member_count", 0)

        return {
            "group_id": group_id,
            "group_name": group_name,
            "avatar": avatar,
            "member_count": member_count,
            "is_default_group": False,
            "config": copy.deepcopy(cfg),
        }

    # ── entry builders (detail) ──

    def _build_default_group_detail(self) -> dict[str, Any]:
        return {
            "group_id": DEFAULT_GROUP_ID,
            "group_info": {
                "group_id": DEFAULT_GROUP_ID,
                "group_name": "默认全局配置",
                "avatar": "",
                "member_count": 0,
            },
            "is_default_group": True,
            "config": self._get_default_group_config(),
        }

    def _build_group_detail(
        self,
        cfg: dict[str, Any],
        live_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        group_id = str(cfg.get("group_id", ""))

        group_name = f"群 {group_id}"
        avatar = GroupInfoCache._build_avatar(group_id) if group_id else ""
        member_count = 0

        if live_info:
            group_name = live_info.get("group_name", group_name)
            avatar = live_info.get("avatar", avatar)
            member_count = live_info.get("member_count", 0)

        return {
            "group_id": group_id,
            "group_name": group_name,
            "group_info": {
                "group_id": group_id,
                "group_name": group_name,
                "avatar": avatar,
                "member_count": member_count,
            },
            "is_default_group": False,
            "config": copy.deepcopy(cfg),
        }

    # ── helpers ──

    @staticmethod
    def _find_live_group(
        live_groups: list[dict[str, Any]], group_id: str
    ) -> dict[str, Any] | None:
        for g in live_groups:
            if str(g.get("group_id", "")) == str(group_id):
                return g
        return None
