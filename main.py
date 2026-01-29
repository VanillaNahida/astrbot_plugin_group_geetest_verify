import asyncio
import json
import os
import random
import re
from typing import Dict, Any, Tuple, Optional
import aiohttp

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.config.default import VERSION


@register(
    "group_geetest_verify",
    "香草味的纳西妲喵（VanillaNahida）",
    "不穿胖次の小奶猫（NyaNyagulugulu）",
    "入群网页验证插件",
    "1.1.9"
)
class GroupGeetestVerifyPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        
        # 验证状态管理: { "gid:uid": {"status": "pending"|"verified"|"bypassed", "task": asyncio.Task, ...} }
        self.verify_states: Dict[str, Dict[str, Any]] = {}
        
        # 创建全局 aiohttp ClientSession
        self.session = aiohttp.ClientSession()
        
        # 从配置文件 schema 读取默认值
        schema_path = os.path.join(os.path.dirname(__file__), "_conf_schema.json")
        schema_defaults = {}
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
                for key, value in schema.items():
                    schema_defaults[key] = value.get("default")
        except Exception as e:
            logger.warning(f"[Geetest Verify] 读取配置 schema 失败: {e}")
        
        # 从配置文件读取配置，如果不存在则使用 schema 中的默认值
        try:
            self.verification_timeout = self.config.get("verification_timeout", schema_defaults.get("verification_timeout", 300))
            self.max_wrong_answers = self.config.get("max_wrong_answers", schema_defaults.get("max_wrong_answers", 5))
            self.api_base_url = self.config.get("api_base_url", schema_defaults.get("api_base_url", ""))
            self.api_key = self.config.get("api_key", schema_defaults.get("api_key", ""))
            self.enable_geetest_verify = self.config.get("enable_geetest_verify", schema_defaults.get("enable_geetest_verify", False))
            self.enable_level_verify = self.config.get("enable_level_verify", schema_defaults.get("enable_level_verify", False))
            self.min_qq_level = self.config.get("min_qq_level", schema_defaults.get("min_qq_level", 20))
            self.verify_delay = self.config.get("verify_delay", schema_defaults.get("verify_delay", 0))
            self.error_verification = self.config.get("error_verification", schema_defaults.get("error_verification", "{at_user} 你还未完成验证。请在 {timeout} 分钟内输入验证码以完成验证"))
            self.group_configs = self.config.get("group_configs", [])
        except Exception:
            self.verification_timeout = schema_defaults.get("verification_timeout", 300)
            self.max_wrong_answers = schema_defaults.get("max_wrong_answers", 5)
            self.api_base_url = schema_defaults.get("api_base_url", "")
            self.api_key = schema_defaults.get("api_key", "")
            self.enable_geetest_verify = schema_defaults.get("enable_geetest_verify", False)
            self.enable_level_verify = schema_defaults.get("enable_level_verify", False)
            self.min_qq_level = schema_defaults.get("min_qq_level", 20)
            self.verify_delay = schema_defaults.get("verify_delay", 3)
            self.group_configs = []

    def _save_config(self):
        """保存配置到磁盘"""
        try:
            # 更新配置字典
            self.config["verification_timeout"] = self.verification_timeout
            self.config["max_wrong_answers"] = self.max_wrong_answers
            self.config["api_base_url"] = self.api_base_url
            self.config["api_key"] = self.api_key
            self.config["enable_geetest_verify"] = self.enable_geetest_verify
            self.config["enable_level_verify"] = self.enable_level_verify
            self.config["min_qq_level"] = self.min_qq_level
            self.config["verify_delay"] = self.verify_delay
            self.config["error_verification"] = self.error_verification
            self.config["group_configs"] = self.group_configs
            # 保存到磁盘
            self.config.save_config()
            logger.info("[Geetest Verify] 配置已保存到文件")
        except Exception as e:
            logger.error(f"[Geetest Verify] 更新配置失败: {e}")

    def _update_group_config(self, gid: int, **kwargs):
        """更新群级别配置"""
        # 查找群级别配置
        group_config = None
        for config in self.group_configs:
            if str(config.get("group_id")) == str(gid):
                group_config = config
                break
        
        # 如果没有找到群级别配置，创建新的
        if not group_config:
            # 基于默认配置创建新的群配置
            group_config = {
                "__template_key": "default_config",
                "group_id": gid,
                "enabled": False,
                "verification_timeout": self.verification_timeout,
                "max_wrong_answers": self.max_wrong_answers,
                "enable_geetest_verify": self.enable_geetest_verify,
                "enable_level_verify": self.enable_level_verify,
                "min_qq_level": self.min_qq_level,
                "verify_delay": self.verify_delay
            }
            self.group_configs.append(group_config)
        
        # 更新配置项
        for key, value in kwargs.items():
            group_config[key] = value
        
        # 确保配置项完整，如果某些字段缺失，使用默认值填充
        required_fields = ["__template_key", "group_id", "enabled", "verification_timeout", 
                          "max_wrong_answers", "enable_geetest_verify", "enable_level_verify", 
                          "min_qq_level", "verify_delay"]
        
        for field in required_fields:
            if field not in group_config:
                if field == "__template_key":
                    group_config[field] = "default_config"
                elif field == "enabled":
                    group_config[field] = False
                elif field == "verification_timeout":
                    group_config[field] = self.verification_timeout
                elif field == "max_wrong_answers":
                    group_config[field] = self.max_wrong_answers
                elif field == "enable_geetest_verify":
                    group_config[field] = self.enable_geetest_verify
                elif field == "enable_level_verify":
                    group_config[field] = self.enable_level_verify
                elif field == "min_qq_level":
                    group_config[field] = self.min_qq_level
                elif field == "verify_delay":
                    group_config[field] = self.verify_delay
        
        # 保存配置
        self._save_config()

    def _get_group_config(self, gid: int) -> dict:
        """获取特定群的配置，如果没有群级别配置则返回默认配置"""
        # 查找群级别配置
        for group_config in self.group_configs:
            if str(group_config.get("group_id")) == str(gid):
                # 返回群级别配置，缺失的配置项使用默认值
                return {
                    "enabled": group_config.get("enabled", False),
                    "verification_timeout": group_config.get("verification_timeout", self.verification_timeout),
                    "max_wrong_answers": group_config.get("max_wrong_answers", self.max_wrong_answers),
                    "enable_geetest_verify": group_config.get("enable_geetest_verify", self.enable_geetest_verify),
                    "enable_level_verify": group_config.get("enable_level_verify", self.enable_level_verify),
                    "min_qq_level": group_config.get("min_qq_level", self.min_qq_level),
                    "verify_delay": group_config.get("verify_delay", self.verify_delay),
                    "error_verification": group_config.get("error_verification", self.error_verification)
                }
        
        # 没有找到群级别配置，返回默认配置
        return {
            "enabled": False,
            "verification_timeout": self.verification_timeout,
            "max_wrong_answers": self.max_wrong_answers,
            "enable_geetest_verify": self.enable_geetest_verify,
            "enable_level_verify": self.enable_level_verify,
            "min_qq_level": self.min_qq_level,
            "verify_delay": self.verify_delay,
            "error_verification": self.error_verification
        }

    async def cleanup(self):
        """清理资源，关闭 aiohttp session"""
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()
            logger.info("[Geetest Verify] 已关闭 aiohttp ClientSession")

    async def _create_geetest_verify(self, gid: int, uid: str) -> str:
        """调用极验 API 生成验证链接，返回路径部分"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return None
        
        url = f"{self.api_base_url}/verify/create"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"AstrBot/v{VERSION}"
        }
        data = {
            "group_id": str(gid),
            "user_id": uid
        }
        
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        full_url = result.get("data", {}).get("url")
                        # 提取 URL 的路径部分（去掉域名和协议）
                        from urllib.parse import urlparse
                        parsed = urlparse(full_url)
                        verify_url_path = parsed.path
                        logger.info(f"[Geetest Verify] 成功生成验证链接路径: {verify_url_path}")
                        return verify_url_path
                    else:
                        logger.error(f"[Geetest Verify] API 返回错误: {result.get('msg')}")
                        return None
                else:
                    logger.error(f"[Geetest Verify] API 请求失败，状态码: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"[Geetest Verify] API 请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"[Geetest Verify] 生成验证链接异常: {e}")
            return None

    async def _check_geetest_verify(self, gid: int, uid: str, code: str) -> bool:
        """调用极验 API 验证验证码"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return False
        
        url = f"{self.api_base_url}/verify/check"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"AstrBot/v{VERSION}"
        }
        data = {
            "group_id": str(gid),
            "user_id": uid,
            "code": code
        }
        
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0 and result.get("passed"):
                        logger.info("[Geetest Verify] 验证码验证成功")
                        return True
                    else:
                        logger.info(f"[Geetest Verify] 验证码验证失败: {result.get('msg')}")
                        return False
                else:
                    logger.error(f"[Geetest Verify] API 请求失败，状态码: {response.status}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"[Geetest Verify] API 请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"[Geetest Verify] 验证验证码异常: {e}")
            return False

    def _get_platform(self, event: AstrMessageEvent) -> str:
        """获取事件所属的平台"""
        return event.get_platform_name()
    
    def _get_raw_value(self, raw, key: str, default=None):
        """安全地从 raw_message 中获取值，兼容字典和 Telegram Update 对象"""
        if isinstance(raw, dict):
            return raw.get(key, default)
        else:
            # Telegram Update 对象，使用属性访问
            return getattr(raw, key, default)
    
    def _get_raw_dict(self, raw) -> dict:
        """将 raw_message 转换为字典格式，方便访问"""
        if isinstance(raw, dict):
            return raw
        else:
            # Telegram Update 对象，转换为字典
            try:
                # 尝试使用 vars() 转换
                return vars(raw)
            except Exception:
                # 如果转换失败，返回空字典
                return {}
    
    def _get_group_id(self, platform: str, raw) -> int:
        """安全地获取群组 ID"""
        if platform == "telegram":
            # Telegram 的群组 ID 可能在不同的位置
            # 尝试从多个可能的路径获取
            raw_dict = self._get_raw_dict(raw) if raw else {}
            
            # 尝试直接从 chat 获取
            chat = self._get_raw_value(raw, "chat") or {}
            if chat:
                chat_id = self._get_raw_value(chat, "id")
                if chat_id:
                    logger.debug(f"[Geetest Verify] 从 chat 获取到群组 ID: {chat_id}")
                    return int(chat_id)
            
            # 尝试从 message.chat 获取
            message = self._get_raw_value(raw, "message") or {}
            if message:
                message_chat = self._get_raw_value(message, "chat") or {}
                if message_chat:
                    chat_id = self._get_raw_value(message_chat, "id")
                    if chat_id:
                        logger.debug(f"[Geetest Verify] 从 message.chat 获取到群组 ID: {chat_id}")
                        return int(chat_id)
            
            # 尝试从 callback_query.message.chat 获取
            callback_query = self._get_raw_value(raw, "callback_query") or {}
            if callback_query:
                cb_message = self._get_raw_value(callback_query, "message") or {}
                if cb_message:
                    cb_chat = self._get_raw_value(cb_message, "chat") or {}
                    if cb_chat:
                        chat_id = self._get_raw_value(cb_chat, "id")
                        if chat_id:
                            logger.debug(f"[Geetest Verify] 从 callback_query.message.chat 获取到群组 ID: {chat_id}")
                            return int(chat_id)
            
            logger.warning(f"[Geetest Verify] 无法从 Telegram 消息中获取群组 ID, raw 类型: {type(raw)}")
            logger.debug(f"[Geetest Verify] raw 内容: {raw}")
            return None
        else:
            # QQ (aiocqhttp) 直接从 group_id 获取
            group_id = self._get_raw_value(raw, "group_id")
            if group_id:
                logger.debug(f"[Geetest Verify] 获取到 QQ 群组 ID: {group_id}")
                return int(group_id)
            logger.warning(f"[Geetest Verify] 无法从 QQ 消息中获取群组 ID")
            return None
    
    def _format_user_mention(self, event: AstrMessageEvent, uid: str) -> str:
        """根据平台格式化用户提及"""
        platform = self._get_platform(event)
        if platform == "telegram":
            # Telegram 使用 @username 或 mention
            raw = event.message_obj.raw_message
            # 尝试从消息中获取用户信息
            new_member = self._get_raw_value(raw, "new_chat_member") or {}
            user_info = self._get_raw_value(new_member, "user") or {}
            username = self._get_raw_value(user_info, "username") or ""
            first_name = self._get_raw_value(user_info, "first_name") or ""
            
            if username:
                return f"@{username}"
            elif first_name:
                return f"[{first_name}](tg://user?id={uid})"
            else:
                return f"[用户](tg://user?id={uid})"
        else:
            # QQ 使用 CQ 码
            return f"[CQ:at,qq={uid}]"
    
    async def _send_group_message(self, event: AstrMessageEvent, gid: int, message: str):
        """根据平台发送群消息"""
        platform = self._get_platform(event)
        try:
            platform_client = self.context.get_platform(platform).get_client()
            
            if platform == "telegram":
                # Telegram API 调用 - 直接调用方法
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_message", chat_id=gid, text=message, parse_mode="Markdown")
                else:
                    # 尝试直接调用方法
                    await platform_client.send_message(chat_id=gid, text=message, parse_mode="Markdown")
            else:
                # QQ (aiocqhttp) API 调用
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("send_group_msg", group_id=gid, message=message)
                elif hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_group_msg", group_id=gid, message=message)
        except Exception as e:
            logger.error(f"[Geetest Verify] 发送消息失败: {e}")
    
    async def _kick_member(self, event: AstrMessageEvent, gid: int, uid: str):
        """根据平台踢出成员"""
        platform = self._get_platform(event)
        try:
            platform_client = self.context.get_platform(platform).get_client()
            
            if platform == "telegram":
                # Telegram API 调用 - 直接调用方法
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("kickChatMember", chat_id=gid, user_id=int(uid))
                else:
                    # 尝试直接调用方法
                    await platform_client.kick_chat_member(chat_id=gid, user_id=int(uid))
            else:
                # QQ (aiocqhttp) API 调用
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                elif hasattr(platform_client, "call_action"):
                    await platform_client.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
        except Exception as e:
            logger.error(f"[Geetest Verify] 踢出成员失败: {e}")
    
    async def _get_user_info(self, event: AstrMessageEvent, uid: str) -> dict:
        """根据平台获取用户信息"""
        platform = self._get_platform(event)
        if platform == "telegram":
            # Telegram 获取用户信息
            try:
                chat_member = await event.bot.api.call_action("getChatMember", chat_id=event.message_obj.raw_message.get("chat", {}).get("id"), user_id=int(uid))
                return chat_member.get("user", {})
            except Exception:
                return {}
        else:
            # QQ (aiocqhttp) 获取用户信息
            try:
                user_info = await self.context.get_platform("aiocqhttp").get_client().api.call_action("get_stranger_info", user_id=int(uid))
                return user_info
            except Exception:
                return {}

    def _generate_math_problem(self) -> Tuple[str, int]:
        """生成一个100以内的加减法问题"""
        op_type = random.choice(['add', 'sub'])
        if op_type == 'add':
            num1 = random.randint(0, 100)
            num2 = random.randint(0, 100 - num1)
            answer = num1 + num2
            question = f"{num1} + {num2} = ?"
            return question, answer
        else:
            num1 = random.randint(1, 100)
            num2 = random.randint(0, num1)
            answer = num1 - num2
            question = f"{num1} - {num2} = ?"
            return question, answer

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_event(self, event: AstrMessageEvent):
        """处理进群退群事件和监听验证码"""
        platform = event.get_platform_name()
        if platform not in ["aiocqhttp", "telegram"]:
            return

        raw = event.message_obj.raw_message
        
        # 调试：输出消息内容
        logger.info(f"[Geetest Verify] 收到消息 - message_str: {event.message_str}, 原始类型: {type(raw)}")
        if platform == "telegram":
            message_obj = self._get_raw_value(raw, "message") or {}
            logger.info(f"[Geetest Verify] Telegram 消息 - text: {self._get_raw_value(message_obj, 'text')}, caption: {self._get_raw_value(message_obj, 'caption')}")
        
        # 手动检测和处理命令（因为命令过滤器可能无法正确处理带 @ 的命令）
        message_str = event.message_str.strip()
        if message_str.startswith('/'):
            logger.info(f"[Geetest Verify] 检测到命令消息: {message_str}")
            # 解析命令
            parts = message_str.split(maxsplit=1)
            command = parts[0][1:]  # 去掉 /
            
            # 处理重新验证命令
            if command == "重新验证" or command == "reverify" or command == "rv":
                logger.info(f"[Geetest Verify] 手动触发重新验证命令")
                await self.reverify_command(event)
                return
            # 处理绕过验证命令
            elif command == "绕过验证" or command == "bypass":
                logger.info(f"[Geetest Verify] 手动触发绕过验证命令")
                await self.bypass_command(event)
                return
            # 其他命令由命令处理器处理
            else:
                logger.info(f"[Geetest Verify] 命令 {command} 由命令处理器处理，跳过事件处理")
                return
        
        # 获取群组 ID 并验证
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过事件处理")
            return
        
        # 处理 Telegram 平台的群事件
        if platform == "telegram":
            # 添加详细日志
            logger.info(f"[Geetest Verify] Telegram 群事件 - new_chat_member: {bool(self._get_raw_value(raw, 'new_chat_member'))}, left_chat_member: {bool(self._get_raw_value(raw, 'left_chat_member'))}, text: {self._get_raw_value(raw, 'text')}, message_id: {self._get_raw_value(raw, 'message_id')}")
            
            if self._get_raw_value(raw, "new_chat_member"):
                logger.info(f"[Geetest Verify] 检测到新成员入群事件 (new_chat_member)")
                await self._process_new_member(event)
            elif self._get_raw_value(raw, "new_chat_members"):
                logger.info(f"[Geetest Verify] 检测到新成员入群事件 (new_chat_members)")
                await self._process_new_member(event)
            elif self._get_raw_value(raw, "left_chat_member"):
                logger.info(f"[Geetest Verify] 检测到成员退群事件")
                await self._process_member_decrease(event)
            elif self._get_raw_value(raw, "text") or self._get_raw_value(raw, "message_id"):
                logger.info(f"[Geetest Verify] 检测到群消息事件")
                await self._process_verification_message(event)
            else:
                logger.info(f"[Geetest Verify] 未识别的 Telegram 事件类型")
        # 处理 OneBot (aiocqhttp) 平台的群事件
        elif platform == "aiocqhttp":
            post_type = self._get_raw_value(raw, "post_type")
            if post_type == "notice":
                if self._get_raw_value(raw, "notice_type") == "group_increase":
                    await self._process_new_member(event)
                elif self._get_raw_value(raw, "notice_type") == "group_decrease":
                    await self._process_member_decrease(event)
            elif post_type == "message" and self._get_raw_value(raw, "message_type") == "group":
                await self._process_verification_message(event)

    async def _process_new_member(self, event: AstrMessageEvent):
        """处理新成员入群"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过新成员处理")
            return
        
        # 根据平台获取用户 ID 列表
        users = []
        if platform == "telegram":
            # 优先检查 new_chat_members（复数），支持多个用户同时入群
            new_members = self._get_raw_value(raw, "new_chat_members") or []
            if new_members:
                users = list(new_members)
            else:
                # 回退到 new_chat_member（单数）
                new_member = self._get_raw_value(raw, "new_chat_member") or {}
                user = self._get_raw_value(new_member, "user") or {}
                if user:
                    users = [user]
        else:
            # QQ (aiocqhttp)
            user_id = self._get_raw_value(raw, "user_id")
            if user_id:
                users = [{"id": user_id}]
        
        if not users:
            logger.warning(f"[Geetest Verify] 无法获取新成员信息")
            return
        
        logger.info(f"[Geetest Verify] 检测到 {len(users)} 个新成员入群")
        
        # 处理每个新成员
        for user in users:
            if platform == "telegram":
                uid = str(self._get_raw_value(user, "id"))
            else:
                uid = str(user.get("id"))
            
            state_key = f"{gid}:{uid}"
            
            # 检查群是否开启了验证
            group_config = self._get_group_config(gid)
            if not group_config["enabled"]:
                return
            
            # 检查用户是否已被标记为绕过验证
            if state_key in self.verify_states and self.verify_states[state_key].get("status") == "bypassed":
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已标记为绕过验证，跳过验证流程")
                continue
            
            # 检查用户是否已验证过
            if state_key in self.verify_states and self.verify_states[state_key].get("status") == "verified":
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已验证过，跳过验证流程")
                continue

            # 获取群级别配置
            group_config = self._get_group_config(gid)
            
            # 延时2秒
            await asyncio.sleep(2)
            
            # 格式化用户提及
            at_user = self._format_user_mention(event, uid)
            skip_verify = False
            
            # 检查是否启用了等级验证（仅 QQ 平台支持，Telegram 没有等级系统）
            if platform == "aiocqhttp" and group_config["enable_level_verify"]:
                qq_level = await self._get_user_level(uid)
                if qq_level >= group_config["min_qq_level"]:
                    logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，达到最低等级要求 {group_config['min_qq_level']}，跳过验证流程")
                    await self._send_group_message(event, gid, f"{at_user} 您的QQ等级为 {qq_level}，大于等于最低等级要求 {group_config['min_qq_level']}级，已跳过验证流程。\n欢迎你的加入！")
                    # 标记用户为已验证
                    self.verify_states[state_key] = {
                        "status": "verified",
                        "verify_time": asyncio.get_event_loop().time()
                    }
                    skip_verify = True
                else:
                    logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，低于最低等级要求 {group_config['min_qq_level']}，将进入验证流程")
                    await self._send_group_message(event, gid, f"{at_user} 您的QQ等级为 {qq_level}，低于最低等级要求 {group_config['min_qq_level']}级，将进入验证流程。")
            
            # Telegram 平台直接进入验证流程（跳过等级验证）
            if platform == "telegram":
                logger.info(f"[Geetest Verify] 用户 {uid} 在 Telegram 群 {gid} 入群，直接进入验证流程")
            
            if skip_verify:
                continue
            
            # 存储用户的入群验证信息
            question, answer = self._generate_math_problem()
            
            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 入群，生成验证问题: {question} (答案: {answer})")
            
            # 延时发送验证消息
            if group_config["verify_delay"] > 0:
                logger.info(f"[Geetest Verify] 群 {gid} 新成员 {uid} 入群，将在 {group_config['verify_delay']} 秒后发送验证消息")
                await asyncio.sleep(group_config['verify_delay'])
            
            await self._start_verification_process(event, uid, gid, question, answer, is_new_member=True, group_config=group_config)

    async def _start_verification_process(self, event: AstrMessageEvent, uid: str, gid: int, question: str, answer: int, is_new_member: bool, group_config: dict = None):
        """为用户启动或重启验证流程"""
        state_key = f"{gid}:{uid}"
        
        # 如果没有提供群配置，则获取默认配置
        if group_config is None:
            group_config = self._get_group_config(gid)
        
        # 如果用户已有验证状态，取消之前的任务
        if state_key in self.verify_states:
            old_task = self.verify_states[state_key].get("task")
            if old_task and not old_task.done():
                old_task.cancel()

        task = asyncio.create_task(self._timeout_kick(uid, gid, group_config["verification_timeout"], event))
        
        # 如果是新成员，重置错误计数；否则保留现有错误计数
        if is_new_member:
            self.verify_states[state_key] = {
                "status": "pending",
                "question": question,
                "answer": answer,
                "task": task,
                "wrong_count": 0,
                "verify_method": "geetest",
                "max_wrong_answers": group_config["max_wrong_answers"]
            }
        else:
            wrong_count = self.verify_states.get(state_key, {}).get("wrong_count", 0)
            verify_method = self.verify_states.get(state_key, {}).get("verify_method", "geetest")
            self.verify_states[state_key] = {
                "status": "pending",
                "question": question,
                "answer": answer,
                "task": task,
                "wrong_count": wrong_count,
                "verify_method": verify_method,
                "max_wrong_answers": group_config["max_wrong_answers"]
            }

        at_user = self._format_user_mention(event, uid)
        timeout_minutes = group_config["verification_timeout"] // 60

        # 如果启用了极验验证，优先使用极验验证
        if group_config["enable_geetest_verify"] and self.api_key:
            try:
                verify_url_path = await self._create_geetest_verify(gid, uid)
                if verify_url_path:
                    self.verify_states[state_key]["verify_method"] = "geetest"
                    # 拼接完整 URL
                    full_verify_url = f"{self.api_base_url}{verify_url_path}"
                    if is_new_member:
                        prompt_message = f"{at_user} 欢迎加入本群！请在 {timeout_minutes} 分钟内复制下方链接前往浏览器完成人机验证：\n{full_verify_url}\n验证完成后，请在群内发送六位数验证码。"
                    else:
                        wrong_count = self.verify_states.get(state_key, {}).get("wrong_count", 0)
                        remaining_attempts = group_config["max_wrong_answers"] - wrong_count
                        prompt_message = f"{at_user} 验证码错误，请重新复制下方链接前往浏览器完成人机验证：\n{full_verify_url}\n验证完成后，请在群内发送六位数验证码。\n您的剩余尝试次数：{remaining_attempts}"
                    await self._send_group_message(event, gid, prompt_message)
                    return
            except Exception as e:
                logger.warning(f"[Geetest Verify] 调用极验 API 失败: {e}，回退到算术验证")
        
        # 回退到算术验证
        self.verify_states[state_key]["verify_method"] = "math"
        if is_new_member:
            prompt_message = f"{at_user} 欢迎加入本群！请在 {timeout_minutes} 分钟内回答下面的问题以完成验证：\n{question}\n注意：请直接发送计算结果，无需其他文字。"
        else:
            wrong_count = self.verify_states.get(state_key, {}).get("wrong_count", 0)
            remaining_attempts = group_config["max_wrong_answers"] - wrong_count
            prompt_message = f"{at_user} 答案错误，请重新回答验证。这是你的新问题：\n{question}\n剩余尝试次数：{remaining_attempts}"

        await self._send_group_message(event, gid, prompt_message)

    async def _process_verification_message(self, event: AstrMessageEvent):
        """处理群消息以进行验证"""
        platform = self._get_platform(event)
        uid = str(event.get_sender_id())
        raw = event.message_obj.raw_message
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过验证消息处理")
            return
        
        state_key = f"{gid}:{uid}"
        
        if state_key not in self.verify_states:
            return
        
        if self.verify_states[state_key].get("status") != "pending":
            return
        
        text = event.message_str.strip()
        
        # 获取群级别配置
        group_config = self._get_group_config(gid)
        
        # 根据用户的验证方法决定处理方式
        verify_method = self.verify_states[state_key].get("verify_method", "geetest")
        
        # 先检查消息是否匹配验证码，如果是验证码则不撤回
        is_verification_answer = False
        
        if verify_method == "geetest":
            # 检查是否是极验验证码（6位数字+字母）
            match = re.search(r'([A-Za-z0-9]{6})', text)
            if match:
                is_verification_answer = True
        else:
            # 检查是否是数学题答案
            try:
                match = re.search(r'(\d+)', text)
                if match:
                    user_answer = int(match.group(1))
                    correct_answer = self.verify_states[state_key].get("answer")
                    if user_answer == correct_answer:
                        is_verification_answer = True
            except (ValueError, TypeError):
                pass
        
        # 如果不是验证答案，才撤回并提示
        if not is_verification_answer:
            # 撤回未验证用户的消息
            try:
                message_id = raw.get("message_id")
                if message_id:
                    await event.bot.api.call_action("delete_msg", message_id=message_id)
                    logger.info(f"已撤回未验证用户 {uid} 在群 {gid} 的消息")
            except Exception as e:
                logger.warning(f"撤回消息失败: {e}")
            
            # 发送验证提示消息
            try:
                at_user = f"[CQ:at,qq={uid}]"
                timeout_minutes = group_config["verification_timeout"] // 60
                
                # 使用配置中的提示模板，替换变量
                error_msg = group_config["error_verification"].format(
                    at_user=at_user,
                    timeout=timeout_minutes
                )
                
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=error_msg)
                logger.info(f"[Geetest Verify] 已向未验证用户 {uid} 发送验证提示")
            except Exception as e:
                logger.warning(f"[Geetest Verify] 发送验证提示失败: {e}")
            
            # 不是验证答案，直接返回
            return
        
        # 获取群级别配置
        group_config = self._get_group_config(gid)
        
        # 根据用户的验证方法决定处理方式
        verify_method = self.verify_states[state_key].get("verify_method", "geetest")
        
        if verify_method == "geetest":
            # 提取验证码（6位数字+字母）
            match = re.search(r'([A-Za-z0-9]{6})', text)
            if not match:
                return
            user_code = match.group(1)
            
            # 调用 API 验证验证码
            is_valid = await self._check_geetest_verify(gid, uid, user_code)
            
            if is_valid:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                self.verify_states[state_key]["task"].cancel()
                self.verify_states[state_key]["status"] = "verified"
                self.verify_states[state_key]["verify_time"] = asyncio.get_event_loop().time()

                at_user = self._format_user_mention(event, uid)
                welcome_msg = f"{at_user} 验证成功，欢迎你的加入！"
                await self._send_group_message(event, gid, welcome_msg)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证码错误，重新生成验证链接")
                
                # 增加错误计数
                self.verify_states[state_key]["wrong_count"] += 1
                wrong_count = self.verify_states[state_key]["wrong_count"]
                
                # 检查是否超过最大错误次数
                max_wrong_answers = self.verify_states[state_key].get("max_wrong_answers", group_config["max_wrong_answers"])
                if wrong_count >= max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")
                    
                    # 取消超时任务
                    self.verify_states[state_key]["task"].cancel()
                    
                    # 发送踢出消息
                    at_user = self._format_user_mention(event, uid)
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await self._send_group_message(event, gid, kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await self._kick_member(event, gid, uid)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await self._send_group_message(event, gid, final_msg)
                    
                    # 删除验证状态
                    self.verify_states.pop(state_key, None)
                    
                    event.stop_event()
                    return
                
                # 重新生成验证链接
                await self._start_verification_process(event, uid, gid, "", 0, is_new_member=False, group_config=group_config)
                event.stop_event()
        else:
            # 使用本地数学题验证
            try:
                match = re.search(r'(\d+)', text)
                if not match:
                    return
                user_answer = int(match.group(1))
            except (ValueError, TypeError):
                return

            correct_answer = self.verify_states[state_key].get("answer")

            if user_answer == correct_answer:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                self.verify_states[state_key]["task"].cancel()
                self.verify_states[state_key]["status"] = "verified"
                self.verify_states[state_key]["verify_time"] = asyncio.get_event_loop().time()

                at_user = self._format_user_mention(event, uid)
                welcome_msg = f"{at_user} 验证成功，欢迎你的加入！"
                await self._send_group_message(event, gid, welcome_msg)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 回答错误，重新生成问题")
                
                # 增加错误计数
                self.verify_states[state_key]["wrong_count"] += 1
                wrong_count = self.verify_states[state_key]["wrong_count"]
                
                # 检查是否超过最大错误次数
                max_wrong_answers = self.verify_states[state_key].get("max_wrong_answers", group_config["max_wrong_answers"])
                if wrong_count >= max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")
                    
                    # 取消超时任务
                    self.verify_states[state_key]["task"].cancel()
                    
                    # 发送踢出消息
                    at_user = self._format_user_mention(event, uid)
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await self._send_group_message(event, gid, kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await self._kick_member(event, gid, uid)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await self._send_group_message(event, gid, final_msg)
                    
                    # 删除验证状态
                    self.verify_states.pop(state_key, None)
                    
                    event.stop_event()
                    return
                
                # 重新生成问题
                question, answer = self._generate_math_problem()
                await self._start_verification_process(event, uid, gid, question, answer, is_new_member=False, group_config=group_config)
                event.stop_event()

    async def _process_member_decrease(self, event: AstrMessageEvent):
        """处理成员退群"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过退群处理")
            return
        
        # 根据平台获取用户 ID
        if platform == "telegram":
            left_member = self._get_raw_value(raw, "left_chat_member") or {}
            user = self._get_raw_value(left_member, "user") or {}
            uid = str(self._get_raw_value(user, "id"))
        else:
            uid = str(self._get_raw_value(raw, "user_id"))
        
        state_key = f"{gid}:{uid}"
        
        if state_key not in self.verify_states:
            return
        
        # 取消验证任务
        task = self.verify_states[state_key].get("task")
        if task and not task.done():
            task.cancel()
        
        # 删除验证状态
        self.verify_states.pop(state_key, None)
        
        logger.info(f"[Geetest Verify] 用户 {uid} 已离开群 {gid}，清除验证状态")

    async def _timeout_kick(self, uid: str, gid: int, timeout: int = None, event: AstrMessageEvent = None):
        """处理超时踢出的协程"""
        # 获取群配置
        group_config = self._get_group_config(gid)
        
        # 如果未提供超时时间，使用配置中的值
        if timeout is None:
            timeout = group_config["verification_timeout"]
        
        # 如果没有提供 event，尝试从上下文获取（兼容旧版本）
        if event is None:
            try:
                platform_client = self.context.get_platform("aiocqhttp").get_client()
                platform = "aiocqhttp"
            except Exception:
                logger.error(f"[Geetest Verify] 无法获取平台客户端，踢出流程中断 (用户 {uid})")
                return
        else:
            platform = self._get_platform(event)
            try:
                platform_client = self.context.get_platform(platform).get_client()
            except Exception as e:
                logger.error(f"[Geetest Verify] 无法获取平台客户端 {platform}，踢出流程中断 (用户 {uid}): {e}")
                return
            
        try:
            if timeout > 120:
                await asyncio.sleep(timeout - 60)

                state_key = f"{gid}:{uid}"
                if state_key in self.verify_states:
                    at_user = f"[CQ:at,qq={uid}]" if platform == "aiocqhttp" else f"[用户](tg://user?id={uid})"
                    # 刷新验证链接
                    verify_url_path = await self._create_geetest_verify(gid, uid)
                    timeout_minutes = timeout // 60
                    
                    if verify_url_path:
                        # 拼接完整 URL
                        full_verify_url = f"{self.api_base_url}{verify_url_path}"
                        reminder_msg = f"{at_user} 验证剩余最后 1 分钟，请尽快完成验证！\n请在 {timeout_minutes} 分钟内复制下方链接前往浏览器完成人机验证，之前的链接可能已失效，请使用新链接完成验证：\n{full_verify_url}\n验证完成后，请在群内发送六位数验证码。"
                        if platform == "aiocqhttp":
                            if hasattr(platform_client, "api"):
                                await platform_client.api.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                            else:
                                await platform_client.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                        else:
                            if hasattr(platform_client, "call_action"):
                                await platform_client.call_action("send_message", chat_id=gid, text=reminder_msg, parse_mode="Markdown")
                            else:
                                await platform_client.send_message(chat_id=gid, text=reminder_msg, parse_mode="Markdown")
                        logger.info(f"[Geetest Verify] 用户 {uid} 验证剩余 1 分钟，已发送提醒")
                    else:
                        # 极验验证失败，回退到数学题验证
                        question, answer = self._generate_math_problem()
                        reminder_msg = f"{at_user} 验证剩余最后 1 分钟，请尽快完成验证！\n请在 {timeout_minutes} 分钟内回答数学题：{question}"
                        if platform == "aiocqhttp":
                            if hasattr(platform_client, "api"):
                                await platform_client.api.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                            else:
                                await platform_client.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                        else:
                            if hasattr(platform_client, "call_action"):
                                await platform_client.call_action("send_message", chat_id=gid, text=reminder_msg, parse_mode="Markdown")
                            else:
                                await platform_client.send_message(chat_id=gid, text=reminder_msg, parse_mode="Markdown")
                        # 更新用户的验证状态为数学题
                        if state_key in self.verify_states:
                            self.verify_states[state_key]["verify_method"] = "math"
                            self.verify_states[state_key]["question"] = question
                            self.verify_states[state_key]["answer"] = answer
                        logger.info(f"[Geetest Verify] 用户 {uid} 极验验证失败，已回退到数学题验证")

            await asyncio.sleep(60)

            state_key = f"{gid}:{uid}"
            if state_key not in self.verify_states:
                return

            at_user = f"[CQ:at,qq={uid}]" if platform == "aiocqhttp" else f"[用户](tg://user?id={uid})"
            
            failure_msg = f"{at_user} 验证超时，你将在 5 秒后被请出本群。"
            if platform == "aiocqhttp":
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("send_group_msg", group_id=gid, message=failure_msg)
                else:
                    await platform_client.call_action("send_group_msg", group_id=gid, message=failure_msg)
            else:
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_message", chat_id=gid, text=failure_msg, parse_mode="Markdown")
                else:
                    await platform_client.send_message(chat_id=gid, text=failure_msg, parse_mode="Markdown")
            
            await asyncio.sleep(5)

            if state_key not in self.verify_states:
                return
            
            if platform == "aiocqhttp":
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                else:
                    await platform_client.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
            else:
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("kickChatMember", chat_id=gid, user_id=int(uid))
                else:
                    await platform_client.kick_chat_member(chat_id=gid, user_id=int(uid))
            
            logger.info(f"[Geetest Verify] 用户 {uid} 验证超时，已从群 {gid} 踢出")
            
            kick_msg = f"{at_user} 因未在规定时间内完成验证，已被请出本群。"
            if platform == "aiocqhttp":
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                else:
                    await platform_client.call_action("send_group_msg", group_id=gid, message=kick_msg)
            else:
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_message", chat_id=gid, text=kick_msg, parse_mode="Markdown")
                else:
                    await platform_client.send_message(chat_id=gid, text=kick_msg, parse_mode="Markdown")

        except asyncio.CancelledError:
            logger.info(f"[Geetest Verify] 踢出任务已取消 (用户 {uid})")
        except Exception as e:
            logger.error(f"[Geetest Verify] 踢出流程发生错误 (用户 {uid}): {e}")

    @filter.command("重新验证")
    async def reverify_command(self, event: AstrMessageEvent):
        """强制指定用户重新验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        logger.info(f"[Geetest Verify] 收到重新验证命令，平台: {platform}, 用户: {uid}")
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过重新验证命令")
            return
        
        logger.info(f"[Geetest Verify] 群组 ID: {gid}")
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await self._send_group_message(event, gid, f"当前群未开启验证哦~")
            return
        
        # 检查是否有权限（这里简单判断是否@了其他用户）
        target_uid = None
        
        if platform == "telegram":
            # Telegram 使用 entities 或回复消息来判断
            # 注意：需要从 message 属性中获取
            message_obj = self._get_raw_value(raw, "message") or {}
            entities = self._get_raw_value(message_obj, "entities") or []
            reply_to_message = self._get_raw_value(message_obj, "reply_to_message") or {}
            text = self._get_raw_value(message_obj, "text") or ""
            
            logger.info(f"[Geetest Verify] Telegram entities: {entities}, reply_to_message: {bool(reply_to_message)}, text: {text}")
            
            # 如果是回复消息，使用回复消息的发送者
            if reply_to_message:
                target_user = self._get_raw_value(reply_to_message, "from") or {}
                target_uid = str(self._get_raw_value(target_user, "id"))
                logger.info(f"[Geetest Verify] 从回复消息获取到目标用户: {target_uid}")
            else:
                # 检查 entities 中的 mention
                for entity in entities:
                    entity_type = self._get_raw_value(entity, "type")
                    logger.info(f"[Geetest Verify] 处理 entity，类型: {entity_type}")
                    if entity_type == "text_mention":
                        # text_mention 带有 user 信息
                        target_user = self._get_raw_value(entity, "user") or {}
                        target_uid = str(self._get_raw_value(target_user, "id"))
                        logger.info(f"[Geetest Verify] 从 text_mention 获取到目标用户: {target_uid}")
                        break
                    elif entity_type == "mention":
                        # mention 是 @username 类型，需要解析 username
                        mention_text = text[self._get_raw_value(entity, "offset"):self._get_raw_value(entity, "offset") + self._get_raw_value(entity, "length")]
                        logger.info(f"[Geetest Verify] 找到 mention: {mention_text}")
                        # 尝试调用 Telegram API 获取用户信息
                        try:
                            username = mention_text.lstrip('@')
                            platform_client = self.context.get_platform("telegram").get_client()
                            if hasattr(platform_client, "call_action"):
                                # 尝试多种方法获取用户信息
                                logger.info(f"[Geetest Verify] 尝试获取用户 {username} 的信息")
                                
                                # 方法1: 尝试通过 getChatMember 遍历（不推荐，仅作测试）
                                # 注意：这需要知道 user_id，所以我们不能使用
                                
                                # 方法2: 尝试使用 AstrBot 的其他 API
                                # 让我们尝试调用 getChat
                                try:
                                    # 尝试通过 @username 获取用户信息
                                    # Telegram Bot API 可能有一些未公开的方法
                                    chat_info = await platform_client.call_action("getChat", chat_id=f"@{username}")
                                    if chat_info:
                                        target_uid = str(chat_info.get("id"))
                                        logger.info(f"[Geetest Verify] 通过 getChat 获取到用户 ID: {target_uid}")
                                except Exception as e1:
                                    logger.debug(f"[Geetest Verify] getChat 方法失败: {e1}")
                                
                                # 方法3: 尝试使用 resolvePeer（如果支持）
                                try:
                                    peer_info = await platform_client.call_action("resolvePeer", username=username)
                                    if peer_info:
                                        peer_id = peer_info.get("peer", {}).get("user_id")
                                        if peer_id:
                                            target_uid = str(peer_id)
                                            logger.info(f"[Geetest Verify] 通过 resolvePeer 获取到用户 ID: {target_uid}")
                                except Exception as e2:
                                    logger.debug(f"[Geetest Verify] resolvePeer 方法失败: {e2}")
                                
                        except Exception as e:
                            logger.warning(f"[Geetest Verify] 从 Telegram API 获取用户信息失败: {e}")
                        break
                
                # 如果还是没找到，尝试从 event.message_str 中解析 @username
                if not target_uid:
                    logger.info(f"[Geetest Verify] 尝试从 event.message_str 中解析 @username")
                    message_str = event.message_str
                    # 使用正则表达式匹配 @username
                    username_match = re.search(r'@([a-zA-Z0-9_]+)', message_str)
                    if username_match:
                        username = username_match.group(1)
                        logger.info(f"[Geetest Verify] 从 message_str 中提取到 username: {username}")
                        # 由于 Telegram Bot API 的限制，我们无法直接通过 username 获取 user_id
                        logger.warning(f"[Geetest Verify] Telegram Bot API 不支持通过 username 直接获取 user_id，请使用回复功能")
        else:
            # QQ (aiocqhttp) 使用消息段判断
            message = self._get_raw_value(raw, "message") or []
            for seg in message:
                if self._get_raw_value(seg, "type") == "at":
                    data = self._get_raw_value(seg, "data") or {}
                    target_uid = str(self._get_raw_value(data, "qq"))
                    break
        
        logger.info(f"[Geetest Verify] 目标用户 ID: {target_uid}")
        
        # 如果没有指定用户，提示用户
        if not target_uid:
            if platform == "telegram":
                await self._send_group_message(event, gid, f"❎ 无法从 @username 获取用户信息。请回复需要重新验证的用户的消息，然后使用此命令。")
            else:
                await self._send_group_message(event, gid, f"❎ 请@需要重新验证的用户。")
            return
        
        # 清除用户的验证状态
        target_state_key = f"{gid}:{target_uid}"
        
        # 如果用户正在验证中，取消之前的任务
        if target_state_key in self.verify_states:
            old_task = self.verify_states[target_state_key].get("task")
            if old_task and not old_task.done():
                old_task.cancel()
        
        # 生成新的验证问题
        question, answer = self._generate_math_problem()
        
        logger.info(f"[Geetest Verify] 用户 {target_uid} 被强制重新验证，生成问题: {question} (答案: {answer})")
        
        # 启动验证流程
        await self._start_verification_process(event, target_uid, gid, question, answer, is_new_member=True)
        
        at_target_user = self._format_user_mention(event, target_uid)
        await self._send_group_message(event, gid, f"✅ 已要求 {at_target_user} 重新验证")

    @filter.command("绕过验证")
    async def bypass_command(self, event: AstrMessageEvent):
        """让指定用户绕过验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过绕过验证命令")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await self._send_group_message(event, gid, f"❎ 当前群未开启验证哦~")
            return
        
        # 检查是否有权限（这里简单判断是否@了其他用户）
        target_uid = None
        
        if platform == "telegram":
            # Telegram 使用 entities 或回复消息来判断
            # 注意：需要从 message 属性中获取
            message_obj = self._get_raw_value(raw, "message") or {}
            entities = self._get_raw_value(message_obj, "entities") or []
            reply_to_message = self._get_raw_value(message_obj, "reply_to_message") or {}
            text = self._get_raw_value(message_obj, "text") or ""
            
            # 如果是回复消息，使用回复消息的发送者
            if reply_to_message:
                target_user = self._get_raw_value(reply_to_message, "from") or {}
                target_uid = str(self._get_raw_value(target_user, "id"))
            else:
                # 检查 entities 中的 mention
                for entity in entities:
                    entity_type = self._get_raw_value(entity, "type")
                    if entity_type == "text_mention":
                        # text_mention 带有 user 信息
                        target_user = self._get_raw_value(entity, "user") or {}
                        target_uid = str(self._get_raw_value(target_user, "id"))
                        break
                    elif entity_type == "mention":
                        # mention 是 @username 类型，需要解析 username
                        mention_text = text[self._get_raw_value(entity, "offset"):self._get_raw_value(entity, "offset") + self._get_raw_value(entity, "length")]
                        # 调用 Telegram API 获取用户信息
                        try:
                            username = mention_text.lstrip('@')
                            platform_client = self.context.get_platform("telegram").get_client()
                            if hasattr(platform_client, "call_action"):
                                chat_member = await platform_client.call_action("getChatMember", chat_id=gid, username=username)
                                if chat_member:
                                    user_info = chat_member.get("user", {})
                                    target_uid = str(user_info.get("id"))
                                    logger.info(f"[Geetest Verify] 从 Telegram API 获取到目标用户: {target_uid}")
                        except Exception as e:
                            logger.warning(f"[Geetest Verify] 从 Telegram API 获取用户信息失败: {e}")
                        break
                
                # 如果还是没找到，尝试从 event.message_str 中解析 @username
                if not target_uid:
                    logger.info(f"[Geetest Verify] 尝试从 event.message_str 中解析 @username")
                    message_str = event.message_str
                    # 使用正则表达式匹配 @username
                    username_match = re.search(r'@([a-zA-Z0-9_]+)', message_str)
                    if username_match:
                        username = username_match.group(1)
                        logger.info(f"[Geetest Verify] 从 message_str 中提取到 username: {username}")
                        # 调用 Telegram API 获取用户信息
                        try:
                            platform_client = self.context.get_platform("telegram").get_client()
                            if hasattr(platform_client, "call_action"):
                                chat_member = await platform_client.call_action("getChatMember", chat_id=gid, username=username)
                                if chat_member:
                                    user_info = chat_member.get("user", {})
                                    target_uid = str(user_info.get("id"))
                                    logger.info(f"[Geetest Verify] 从 Telegram API 获取到目标用户: {target_uid}")
                        except Exception as e:
                            logger.warning(f"[Geetest Verify] 从 Telegram API 获取用户信息失败: {e}")
        else:
            # QQ (aiocqhttp) 使用消息段判断
            message = self._get_raw_value(raw, "message") or []
            for seg in message:
                if self._get_raw_value(seg, "type") == "at":
                    data = self._get_raw_value(seg, "data") or {}
                    target_uid = str(self._get_raw_value(data, "qq"))
                    break
        
        if not target_uid:
            if platform == "telegram":
                await self._send_group_message(event, gid, f"❎ 请回复需要绕过验证的用户的消息，或点击用户头像后使用命令。")
            else:
                await self._send_group_message(event, gid, f"❎ 请@需要绕过验证的用户")
            return
        
        # 标记用户为绕过验证
        target_state_key = f"{gid}:{target_uid}"
        
        # 如果用户正在验证中，取消任务
        if target_state_key in self.verify_states:
            old_task = self.verify_states[target_state_key].get("task")
            if old_task and not old_task.done():
                old_task.cancel()
        
        # 设置绕过状态
        self.verify_states[target_state_key] = {
            "status": "bypassed"
        }
        
        logger.info(f"[Geetest Verify] 用户 {target_uid} 已标记为绕过验证")
        
        at_target_user = self._format_user_mention(event, target_uid)
        await self._send_group_message(event, gid, f"✅ 已允许 {at_target_user} 绕过验证\n欢迎你的加入！")

    @filter.command("开启验证")
    async def enable_verify_command(self, event: AstrMessageEvent):
        """开启群验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过开启验证命令")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已开启
        if group_config["enabled"]:
            await self._send_group_message(event, gid, f"✅ 本群验证已处于开启状态")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, enabled=True)
        
        # 同时更新内存状态（兼容旧版本）
        self.verify_states[f"group_{gid}_enabled"] = {"enabled": True}
        
        await self._send_group_message(event, gid, f"✅ 已开启本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启验证")

    @filter.command("关闭验证")
    async def disable_verify_command(self, event: AstrMessageEvent):
        """关闭群验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过关闭验证命令")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已关闭
        if not group_config["enabled"]:
            await self._send_group_message(event, gid, f"❎ 本群暂未开启验证")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, enabled=False)
        
        # 同时更新内存状态（兼容旧版本）
        self.verify_states[f"group_{gid}_enabled"] = {"enabled": False}
        
        await self._send_group_message(event, gid, f"✅ 已关闭本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭验证")

    @filter.command("设置验证超时时间")
    async def set_timeout_command(self, event: AstrMessageEvent):
        """设置验证超时时间"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过设置超时命令")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await self._send_group_message(event, gid, f"❎ 请输入正确的时间（秒）")
            return
        
        timeout = int(match.group(1))
        
        # 更新群级别配置
        self._update_group_config(gid, verification_timeout=timeout)
        
        await self._send_group_message(event, gid, f"✅ 已将本群验证超时时间设置为 {timeout} 秒")
        
        if timeout < 60:
            await self._send_group_message(event, gid, f"你给的时间太少了，建议至少一分钟(60秒)哦ε(*´･ω･)з")
        
        logger.info(f"[Geetest Verify] 群 {gid} 验证超时时间设置为 {timeout} 秒")

    @filter.command("开启等级验证")
    async def enable_level_verify_command(self, event: AstrMessageEvent):
        """开启等级验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过开启等级验证命令")
            return
        
        # Telegram 平台不支持等级验证
        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} ❎ Telegram 平台不支持等级验证功能。")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已开启
        if group_config["enable_level_verify"]:
            await self._send_group_message(event, gid, f"❎ 本群等级验证已处于开启状态")
            return
        
        # 开启等级验证
        self._update_group_config(gid, enable_level_verify=True)
        
        await self._send_group_message(event, gid, f"✅ 已开启本群等级验证，QQ等级大于等于 {group_config['min_qq_level']} 级的用户将自动跳过验证。")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启等级验证")

    @filter.command("关闭等级验证")
    async def disable_level_verify_command(self, event: AstrMessageEvent):
        """关闭等级验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过关闭等级验证命令")
            return
        
        # Telegram 平台不支持等级验证
        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} ❎ Telegram 平台不支持等级验证功能。")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已关闭
        if not group_config["enable_level_verify"]:
            await self._send_group_message(event, gid, f"❎ 本群等级验证暂未开启")
            return
        
        # 关闭等级验证
        self._update_group_config(gid, enable_level_verify=False)
        
        await self._send_group_message(event, gid, f"✅ 已关闭本群等级验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭等级验证")

    @filter.command("设置最低验证等级")
    async def set_min_level_command(self, event: AstrMessageEvent):
        """设置最低验证等级"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过设置最低等级命令")
            return
        
        # Telegram 平台不支持等级验证
        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} ❎ Telegram 平台不支持等级验证功能。")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await self._send_group_message(event, gid, f"❎ 请输入正确的等级（0-64）")
            return
        
        min_level = int(match.group(1))
        
        # 验证等级范围
        if min_level < 0 or min_level > 64:
            await self._send_group_message(event, gid, f"❎ 等级必须在 0-64 之间")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, min_qq_level=min_level)
        
        await self._send_group_message(event, gid, f"✅ 已将本群最低验证等级设置为 {min_level} 级")
        logger.info(f"[Geetest Verify] 群 {gid} 最低验证等级设置为 {min_level} 级")

    async def _get_user_level(self, uid: str) -> int:
        """获取用户QQ等级"""
        try:
            user_info = await self.context.get_platform("aiocqhttp").get_client().api.call_action("get_stranger_info", user_id=int(uid))
            logger.info(f"[Geetest Verify] 用户 {uid} 的API返回数据: {user_info}")
            
            # 尝试多种方式获取 qqLevel
            qq_level = 0
            for key in user_info.keys():
                if key.lower() == "qqlevel":
                    qq_level = user_info[key]
                    break
            
            # 如果顶层没找到，尝试从 data 中获取
            if qq_level == 0 and isinstance(user_info.get("data"), dict):
                for key in user_info["data"].keys():
                    if key.lower() == "qqlevel":
                        qq_level = user_info["data"][key]
                        break
            
            logger.info(f"[Geetest Verify] 用户 {uid} 的QQ等级为: {qq_level}")
            return qq_level
        except Exception as e:
            logger.error(f"[Geetest Verify] 获取用户 {uid} 的QQ等级失败: {e}")
            return 0

    async def _check_permission(self, event: AstrMessageEvent) -> bool:
        """检查用户权限（bot管理员、群主、管理员才可使用）"""
        platform = self._get_platform(event)
        raw_message = event.message_obj.raw_message
        
        # 检查是否是 Bot 管理员
        if event.is_admin():
            logger.debug(f"用户为Bot管理员，跳过权限检查")
            return True
        
        # 检查群权限（群主、管理员才可使用）
        if platform == "telegram":
            # Telegram 使用 chat_member 获取用户角色
            from_user = self._get_raw_value(raw_message, "from") or {}
            gid = self._get_group_id(platform, raw_message)
            if gid is None:
                logger.warning(f"[Geetest Verify] 无法获取群组 ID，权限检查失败")
                return False
            
            try:
                platform_client = self.context.get_platform(platform).get_client()
                chat_member = None
                if hasattr(platform_client, "call_action"):
                    chat_member = await platform_client.call_action("getChatMember", chat_id=gid, user_id=self._get_raw_value(from_user, "id"))
                else:
                    chat_member = await platform_client.get_chat_member(chat_id=gid, user_id=self._get_raw_value(from_user, "id"))
                
                status = self._get_raw_value(chat_member, "status", "member")
                if status in ["administrator", "creator"]:
                    logger.debug(f"用户为{status}，跳过权限检查")
                    return True
            except Exception as e:
                logger.warning(f"[Geetest Verify] 获取 Telegram 用户权限失败: {e}")
        else:
            # QQ (aiocqhttp) 使用 sender.role
            sender_dict = self._get_raw_dict(raw_message) if raw_message else {}
            sender = sender_dict.get("sender", {}) if sender_dict else {}
            sender_role = sender.get("role", "member")
            if sender_role in ["admin", "owner"]:
                logger.debug(f"用户为{sender_role}，跳过权限检查")
                return True
        
        return False

    @filter.command("查看验证配置")
    async def show_config_command(self, event: AstrMessageEvent):
        """查看当前群的验证配置"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        
        # 获取群组 ID
        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning(f"[Geetest Verify] 无法获取群组 ID，跳过查看配置命令")
            return
        
        # 检查用户权限
        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取群级别配置
        group_config = self._get_group_config(gid)
        
        # 检查群是否开启了验证
        if group_config["enabled"]:
            enabled_status = "✅ 已开启"
        else:
            enabled_status = "❌ 未开启"
        
        # 获取群名称
        if platform == "telegram":
            chat = self._get_raw_value(raw, "chat") or {}
            group_name = self._get_raw_value(chat, "title") or ""
        else:
            group_name = self._get_raw_value(raw, "group_name") or ""
        
        # 构建配置信息
        if platform == "telegram":
            # Telegram 平台没有等级验证
            config_info = f"""📋 群 {group_name}（{gid}）的验证配置信息：

🔹 验证状态：{enabled_status}
🔹 验证总超时时间：{group_config['verification_timeout']} 秒
🔹 最大错误回答次数：{group_config['max_wrong_answers']} 次
🔹 极验验证：{'✅ 已启用' if group_config['enable_geetest_verify'] else '❌ 未启用'}
🔹 入群验证延时：{group_config['verify_delay']} 秒

💡 Telegram 平台不支持等级验证，所有新成员均需完成验证"""
        else:
            # QQ 平台
            config_info = f"""📋 群 {group_name}（{gid}）的验证配置信息：

🔹 验证状态：{enabled_status}
🔹 验证总超时时间：{group_config['verification_timeout']} 秒
🔹 最大错误回答次数：{group_config['max_wrong_answers']} 次
🔹 极验验证：{'✅ 已启用' if group_config['enable_geetest_verify'] else '❌ 未启用'}
🔹 等级验证：{'✅ 已启用' if group_config['enable_level_verify'] else '❌ 未启用'}
🔹 最低QQ等级：{group_config['min_qq_level']} 级
🔹 入群验证延时：{group_config['verify_delay']} 秒

💡 配置来源：{'群级别配置' if any(str(cfg.get('group_id')) == str(gid) for cfg in self.group_configs) else '全局默认配置'}"""
        
        await self._send_group_message(event, gid, config_info)
        logger.info(f"[Geetest Verify] 群 {gid} 查看验证配置")
