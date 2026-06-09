from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context

try:
    from quart import jsonify as quart_jsonify
    from quart import request as quart_request_obj
except ImportError:
    quart_jsonify = None
    quart_request_obj = None

from .group_info_cache import GroupInfoCache
from .page_service import PageService

PLUGIN_NAME = "astrbot_plugin_group_geetest_verify"


class WebController:
    def __init__(self, context: Context, config: AstrBotConfig, plugin_dir: Path, on_config_saved=None):
        self.context = context
        self.group_cache = GroupInfoCache(context)
        self.service = PageService(config, plugin_dir, self.group_cache, on_config_saved=on_config_saved)

    def register_routes(self) -> None:
        routes = [
            ("/settings/bootstrap", self.page_bootstrap, ["GET"], "Load page bootstrap data"),
            ("/settings/available-groups", self.page_available_groups, ["GET"], "List groups without config"),
            ("/settings/group", self.page_get_group, ["GET"], "Get one group config"),
            ("/settings/group", self.page_save_group, ["POST"], "Save a group config"),
            (
                "/settings/group/delete",
                self.page_delete_group,
                ["POST"],
                "Delete a group config",
            ),
        ]
        for path, handler, methods, desc in routes:
            self.context.register_web_api(
                f"/{PLUGIN_NAME}{path}",
                self._wrap_handler(handler),
                methods,
                desc,
            )

    @staticmethod
    def _check_quart_available() -> None:
        if quart_jsonify is None or quart_request_obj is None:
            raise RuntimeError("Web framework is unavailable")

    @staticmethod
    def _jsonify(payload: dict[str, Any]):
        WebController._check_quart_available()
        return cast(Callable[[dict[str, Any]], Any], quart_jsonify)(payload)

    @staticmethod
    def _request():
        WebController._check_quart_available()
        return cast(Any, quart_request_obj)

    def _wrap_handler(
        self, handler: Callable[[], Awaitable]
    ) -> Callable[[], Awaitable]:
        async def wrapped():
            self._check_quart_available()
            try:
                return await handler()
            except ValueError as exc:
                return self._jsonify({"ok": False, "message": str(exc)}), 400
            except Exception as exc:
                logger.exception("Geetest verify page request failed")
                return self._jsonify({"ok": False, "message": str(exc)}), 500

        wrapped.__name__ = handler.__name__
        return wrapped

    async def page_bootstrap(self):
        data = await self.service.get_bootstrap()
        return self._jsonify({"ok": True, "data": data})

    async def page_available_groups(self):
        data = await self.service.get_available_groups()
        return self._jsonify({"ok": True, "data": data})

    async def page_get_group(self):
        request = self._request()
        group_id = request.args.get("group_id", "")
        data = await self.service.get_group_config(group_id)
        return self._jsonify({"ok": True, "data": data})

    async def page_save_group(self):
        payload = await self._request().get_json(force=True, silent=True) or {}
        group_id = payload.get("group_id")
        config = payload.get("config")
        global_config = payload.get("global_config")
        result = self.service.save_group_config(group_id, config, global_config)
        return self._jsonify(
            {"ok": True, "message": "Group config saved", "data": result}
        )

    async def page_delete_group(self):
        payload = await self._request().get_json(force=True, silent=True) or {}
        group_id = payload.get("group_id")
        self.service.delete_group_config(group_id)
        return self._jsonify(
            {"ok": True, "message": f"Group config for {group_id} deleted"}
        )
