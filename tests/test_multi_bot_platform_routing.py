"""多机器人（同类型多个平台适配器实例）路由回归测试。

背景：``Context.get_platform(<适配器类型名>)`` 按 ``meta().name`` 匹配，
永远返回 ``platform_insts`` 中的第一个实例。同类型多账号时，插件会把
发送消息 / 踢人 / 查询用户信息全部路由到第一个机器人（例如 bot1），
而不是真正收到该事件的那个实例（例如 bot3）。
"""

import importlib
import logging
import re
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = REPO_ROOT.name


def _install_runtime_stubs():
    try:
        importlib.import_module("aiohttp")
    except ModuleNotFoundError:
        aiohttp = ModuleType("aiohttp")
        aiohttp.ClientSession = object
        aiohttp.ClientError = Exception
        sys.modules.setdefault("aiohttp", aiohttp)

    try:
        importlib.import_module("aiosqlite")
    except ModuleNotFoundError:
        aiosqlite = ModuleType("aiosqlite")
        aiosqlite.Connection = object
        aiosqlite.Row = object
        sys.modules.setdefault("aiosqlite", aiosqlite)

    try:
        importlib.import_module("astrbot.api.event")
        importlib.import_module("astrbot.api.star")
        importlib.import_module("astrbot.core.config.default")
        return
    except ModuleNotFoundError:
        pass

    astrbot = ModuleType("astrbot")
    astrbot.__path__ = []
    astrbot_api = ModuleType("astrbot.api")
    astrbot_api.__path__ = []
    astrbot_event = ModuleType("astrbot.api.event")
    astrbot_star = ModuleType("astrbot.api.star")
    astrbot_core = ModuleType("astrbot.core")
    astrbot_core.__path__ = []
    astrbot_config = ModuleType("astrbot.core.config")
    astrbot_config.__path__ = []
    astrbot_default = ModuleType("astrbot.core.config.default")

    class EventMessageType:
        GROUP_MESSAGE = "GROUP_MESSAGE"

    class Filter:
        @staticmethod
        def event_message_type(*args, **kwargs):
            return lambda func: func

        @staticmethod
        def command(*args, **kwargs):
            return lambda func: func

    Filter.EventMessageType = EventMessageType

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context=None):
            self.context = context

    class StarTools:
        @staticmethod
        def get_data_dir(_name):
            return REPO_ROOT / ".test-data"

    def register(*args, **kwargs):
        return lambda cls: cls

    logger = logging.getLogger("astrbot-test")
    astrbot_api.logger = logger
    astrbot_api.AstrBotConfig = dict
    astrbot_event.filter = Filter()
    astrbot_event.AstrMessageEvent = AstrMessageEvent
    astrbot_star.Context = Context
    astrbot_star.Star = Star
    astrbot_star.StarTools = StarTools
    astrbot_star.register = register
    astrbot_default.VERSION = "test"

    astrbot.api = astrbot_api
    astrbot.core = astrbot_core
    astrbot_api.event = astrbot_event
    astrbot_api.star = astrbot_star
    astrbot_core.config = astrbot_config
    astrbot_config.default = astrbot_default

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api
    sys.modules["astrbot.api.event"] = astrbot_event
    sys.modules["astrbot.api.star"] = astrbot_star
    sys.modules["astrbot.core"] = astrbot_core
    sys.modules["astrbot.core.config"] = astrbot_config
    sys.modules["astrbot.core.config.default"] = astrbot_default


_install_runtime_stubs()
sys.path.insert(0, str(REPO_ROOT.parent))

plugin_main = importlib.import_module(f"{PACKAGE_NAME}.main")
Plugin = plugin_main.GroupGeetestVerifyPlugin


class FakeClient:
    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return f"<client {self.tag}>"


class FakeInstance:
    def __init__(self, inst_id, adapter_name, client):
        self._meta = SimpleNamespace(id=inst_id, name=adapter_name)
        self._client = client

    def meta(self):
        return self._meta

    def get_client(self):
        return self._client


class FakeContext:
    """复刻 AstrBot Context 的两种查找语义。"""

    def __init__(self, instances):
        self.platform_insts = instances

    def get_platform(self, platform_type):
        for inst in self.platform_insts:
            if inst.meta().name == platform_type:
                return inst
        return None

    def get_platform_inst(self, platform_id):
        for inst in self.platform_insts:
            if inst.meta().id == platform_id:
                return inst
        return None


def build_plugin():
    plugin = object.__new__(Plugin)
    clients = {tag: FakeClient(tag) for tag in ("bot1", "bot2", "bot3")}
    plugin.context = FakeContext(
        [
            FakeInstance("bot1", "aiocqhttp", clients["bot1"]),
            FakeInstance("bot2", "aiocqhttp", clients["bot2"]),
            FakeInstance("bot3", "aiocqhttp", clients["bot3"]),
        ]
    )
    return plugin, clients


def make_event(platform_id, bot=None):
    return SimpleNamespace(
        bot=bot,
        get_platform_id=lambda: platform_id,
        get_platform_name=lambda: "aiocqhttp",
    )


class MultiBotPlatformRoutingTests(unittest.TestCase):
    def test_type_name_lookup_can_only_return_first_instance(self):
        """记录触发该 bug 的语义：类型名查找永远命中第一个实例。"""
        plugin, clients = build_plugin()
        self.assertIs(
            plugin.context.get_platform("aiocqhttp").get_client(),
            clients["bot1"],
        )

    def test_event_bound_client_is_preferred(self):
        plugin, _ = build_plugin()
        bound = FakeClient("bot3-bound")
        self.assertIs(plugin._get_platform_client(make_event("bot3", bot=bound)), bound)

    def test_falls_back_to_event_platform_instance_id(self):
        plugin, clients = build_plugin()
        self.assertIs(
            plugin._get_platform_client(make_event("bot3")),
            clients["bot3"],
        )

    def test_each_bot_routes_to_its_own_client(self):
        plugin, clients = build_plugin()
        for tag in ("bot1", "bot2", "bot3"):
            self.assertIs(plugin._get_platform_client(make_event(tag)), clients[tag])

    def test_missing_event_context_raises_instead_of_silently_using_first_bot(self):
        plugin, _ = build_plugin()
        with self.assertRaisesRegex(RuntimeError, "缺少事件上下文"):
            plugin._get_platform_client(None)

    def test_no_call_site_resolves_client_by_adapter_type_name(self):
        """回归护栏：不允许再出现 context.get_platform(...).get_client()。"""
        pattern = re.compile(r"self\.context\.get_platform\([^)\n]*\)\.get_client\(\)")
        for relative in ("platform/platform.py", "core/verifier.py", "main.py"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertIsNone(
                pattern.search(text),
                f"{relative} 仍按适配器类型名解析客户端",
            )


if __name__ == "__main__":
    unittest.main()
