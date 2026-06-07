import asyncio
import re
from typing import Dict

import aiohttp

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools, register

from .database.db import VerifyStateDB
from .config.config import ConfigMixin
from .platform.platform import PlatformMixin
from .core.verifier import VerifyMixin


@register(
    "group_geetest_verify",
    "香草味的纳西妲喵（VanillaNahida）& 不穿胖次の小奶猫（NyaNyagulugulu）",
    "入群网页验证插件",
    "v1.3.0"
)
class GroupGeetestVerifyPlugin(ConfigMixin, PlatformMixin, VerifyMixin, Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}

        self._data_dir = StarTools.get_data_dir("astrbot_plugin_group_geetest_verify")
        db_path = self._data_dir / "verify_states.db"
        self.db = VerifyStateDB(db_path)
        self._tasks: Dict[str, asyncio.Task] = {}

        self.session = aiohttp.ClientSession()

        self._load_config()

    async def initialize(self):
        """实现异步的插件初始化方法，当加载并实例化该插件类之后会自动调用该方法。"""
        logger.info("[Geetest Verify] 插件初始化中...")

        if not hasattr(self, 'session') or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.info("[Geetest Verify] 已创建 aiohttp ClientSession 用于请求验证服务器")

        await self.db.init()
        await self.db.cleanup_expired(max_age_seconds=86400)
        await self._sync_config_to_db()

        logger.info("[Geetest Verify] 插件初始化完成")
        logger.info("[Geetest Verify] 全局配置：")
        logger.info(f"[Geetest Verify] - API 基础 URL: {self.api_base_url if self.api_base_url else '未配置API地址'}")
        logger.info(f"[Geetest Verify] - 验证超时时间: {self.verification_timeout} 秒")
        logger.info(f"[Geetest Verify] - 最大错误回答次数: {self.max_wrong_answers} 次")
        logger.info(f"[Geetest Verify] - 极验验证: {'已启用' if self.enable_geetest_verify else '未启用'}")
        logger.info(f"[Geetest Verify] - 等级验证: {'已启用' if self.enable_level_verify else '未启用'}")
        logger.info(f"[Geetest Verify] - 已配置群数量: {len(self.group_configs)}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        logger.info("[Geetest Verify] 插件正在卸载...")

        cancelled_count = 0
        for task in self._tasks.values():
            if task and not task.done():
                task.cancel()
                cancelled_count += 1

        if cancelled_count > 0:
            logger.info(f"[Geetest Verify] 已取消 {cancelled_count} 个正在进行的验证任务")

        self._tasks.clear()

        await self.db.close()

        await self.cleanup()

        logger.info("[Geetest Verify] 插件已成功卸载")

    async def cleanup(self):
        """清理资源，关闭 aiohttp session"""
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()
            logger.info("[Geetest Verify] 已关闭 aiohttp ClientSession")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_event(self, event: AstrMessageEvent):
        """处理进群退群事件和监听验证码"""
        platform = event.get_platform_name()
        if platform not in ["aiocqhttp", "telegram"]:
            return

        raw = event.message_obj.raw_message

        logger.debug(f"[Geetest Verify] 收到消息 - message_str: {event.message_str}, 原始类型: {type(raw)}")

        if platform == "telegram":
            message_obj = self._get_raw_value(raw, "message") or {}
            logger.info(f"[Geetest Verify] Telegram 消息 - text: {self._get_raw_value(message_obj, 'text')}, caption: {self._get_raw_value(message_obj, 'caption')}")

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过事件处理")
            return

        if platform == "telegram":
            logger.info(f"[Geetest Verify] Telegram 群事件 - new_chat_member: {bool(self._get_raw_value(raw, 'new_chat_member'))}, left_chat_member: {bool(self._get_raw_value(raw, 'left_chat_member'))}, text: {self._get_raw_value(raw, 'text')}, message_id: {self._get_raw_value(raw, 'message_id')}")

            if self._get_raw_value(raw, "new_chat_member"):
                logger.info("[Geetest Verify] 检测到新成员入群事件 (new_chat_member)")
                await self._process_new_member(event)
            elif self._get_raw_value(raw, "new_chat_members"):
                logger.info("[Geetest Verify] 检测到新成员入群事件 (new_chat_members)")
                await self._process_new_member(event)
            elif self._get_raw_value(raw, "left_chat_member"):
                logger.info("[Geetest Verify] 检测到成员退群事件")
                await self._process_member_decrease(event)
            elif self._get_raw_value(raw, "text") or self._get_raw_value(raw, "message_id"):
                logger.info("[Geetest Verify] 检测到群消息事件")
                await self._process_verification_message(event)
            else:
                logger.info("[Geetest Verify] 未识别的 Telegram 事件类型")
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

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过新成员处理")
            return

        users = []
        if platform == "telegram":
            new_members = self._get_raw_value(raw, "new_chat_members") or []
            if new_members:
                users = list(new_members)
            else:
                new_member = self._get_raw_value(raw, "new_chat_member") or {}
                user = self._get_raw_value(new_member, "user") or {}
                if user:
                    users = [user]
        else:
            user_id = self._get_raw_value(raw, "user_id")
            if user_id:
                users = [{"id": user_id}]

        if not users:
            logger.warning("[Geetest Verify] 无法获取新成员信息")
            return

        logger.info(f"[Geetest Verify] 检测到 {len(users)} 个新成员入群")

        for user in users:
            if platform == "telegram":
                uid = str(self._get_raw_value(user, "id"))
            else:
                uid = str(user.get("id"))

            state_key = f"{gid}:{uid}"

            group_config = self._get_group_config(gid)
            if not group_config["enabled"]:
                return

            cached = self.db.get_cached(state_key)
            if cached and cached.get("status") == "bypassed":
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已标记为绕过验证，跳过验证流程")
                continue

            if cached and cached.get("status") == "verified":
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已验证过，跳过验证流程")
                continue

            group_config = self._get_group_config(gid)

            await asyncio.sleep(2)

            at_user = self._format_user_mention(event, uid)
            skip_verify = False

            if platform == "aiocqhttp" and group_config["enable_level_verify"]:
                qq_level = await self._get_user_level(uid)
                if qq_level == 0:
                    message = self.level_no_info_message.format(at_user=at_user)
                else:
                    message = self.level_too_low_message.format(at_user=at_user, qq_level=qq_level, min_level=group_config['min_qq_level'])
                if qq_level >= group_config["min_qq_level"]:
                    logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，达到最低等级要求 {group_config['min_qq_level']}，跳过验证流程")
                    pass_msg = self.level_pass_message.format(at_user=at_user, qq_level=qq_level, min_level=group_config['min_qq_level'])
                    await self._send_group_message(event, gid, pass_msg)
                    await self.db.set(state_key, {
                        "status": "verified",
                        "verify_time": asyncio.get_event_loop().time()
                    })
                    skip_verify = True
                else:
                    logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，低于最低等级要求 {group_config['min_qq_level']}，将进入验证流程")
                    await self._send_group_message(event, gid, message)

            if platform == "telegram":
                logger.info(f"[Geetest Verify] 用户 {uid} 在 Telegram 群 {gid} 入群，直接进入验证流程")

            if skip_verify:
                continue

            question, answer = self._generate_math_problem()

            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 入群，生成验证问题: {question} (答案: {answer})")

            if group_config["verify_delay"] > 0:
                logger.info(f"[Geetest Verify] 群 {gid} 新成员 {uid} 入群，将在 {group_config['verify_delay']} 秒后发送验证消息")
                await asyncio.sleep(group_config['verify_delay'])

            await self._start_verification_process(event, uid, gid, question, answer, is_new_member=True, group_config=group_config)

    async def _process_verification_message(self, event: AstrMessageEvent):
        """处理群消息以进行验证"""
        platform = self._get_platform(event)
        uid = str(event.get_sender_id())
        raw = event.message_obj.raw_message

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过验证消息处理")
            return

        state_key = f"{gid}:{uid}"

        state = self.db.get_cached(state_key)
        if not state:
            return

        if state.get("status") != "pending":
            return

        text = event.message_str.strip()

        group_config = self._get_group_config(gid)

        verify_method = state.get("verify_method", "geetest")

        is_verification_answer = False

        if verify_method == "geetest":
            match = re.search(r'([A-Za-z0-9]{6})', text)
            if match:
                is_verification_answer = True
        else:
            try:
                match = re.search(r'(\d+)', text)
                if match:
                    user_answer = int(match.group(1))
                    correct_answer = state.get("answer")
                    if user_answer == correct_answer:
                        is_verification_answer = True
            except (ValueError, TypeError):
                pass

        if not is_verification_answer:
            if group_config.get("recall_unverified_messages", False):
                try:
                    message_id = raw.get("message_id")
                    if message_id:
                        await event.bot.api.call_action("delete_msg", message_id=message_id)
                        logger.info(f"已撤回未验证用户 {uid} 在群 {gid} 的消息")
                except Exception as e:
                    logger.warning(f"撤回消息失败: {e}")

            if group_config.get("prompt_unverified_user", True):
                try:
                    at_user = self._format_user_mention(event, uid)
                    timeout_minutes = group_config["verification_timeout"] // 60
                    error_msg = self.error_verification.format(at_user=at_user, timeout=timeout_minutes)
                    await self._send_group_message(event, gid, error_msg)
                    logger.info(f"[Geetest Verify] 已向未验证用户 {uid} 发送验证提示")
                except Exception as e:
                    logger.warning(f"[Geetest Verify] 发送验证提示失败: {e}")
            else:
                state["wrong_count"] = state.get("wrong_count", 0) + 1
                wrong_count = state["wrong_count"]
                await self.db.update_field(state_key, "wrong_count", wrong_count)
                logger.info(f"[Geetest Verify] 用户 {uid} 发送非验证码消息，错误计数增加至 {wrong_count}")

                try:
                    at_user = self._format_user_mention(event, uid)
                    error_msg = self.wrong_code_message.format(at_user=at_user)
                    await self._send_group_message(event, gid, error_msg)
                except Exception as e:
                    logger.warning(f"[Geetest Verify] 发送错误提示失败: {e}")

                if wrong_count >= group_config["max_wrong_answers"]:
                    try:
                        at_user = self._format_user_mention(event, uid)
                        kick_msg = self.too_many_non_code_message.format(at_user=at_user, count=wrong_count)
                        await self._send_group_message(event, gid, kick_msg)
                        await asyncio.sleep(2)
                        await self._kick_member(event, gid, uid)
                        logger.info(f"[Geetest Verify] 用户 {uid} 因连续发送非验证码消息 {wrong_count} 次，已被踢出群 {gid}")
                        await self.db.delete(state_key)
                        self._tasks.pop(state_key, None)
                    except Exception as e:
                        logger.error(f"[Geetest Verify] 踢出用户 {uid} 失败: {e}")

            return

        group_config = self._get_group_config(gid)

        state = self.db.get_cached(state_key)
        verify_method = state.get("verify_method", "geetest")

        if verify_method == "geetest":
            match = re.search(r'([A-Za-z0-9]{6})', text)
            if not match:
                return
            user_code = match.group(1)

            is_valid = await self._check_geetest_verify(gid, uid, user_code)

            if is_valid:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                task = self._tasks.get(state_key)
                if task and not task.done():
                    task.cancel()
                await self.db.set(state_key, {
                    "status": "verified",
                    "verify_time": asyncio.get_event_loop().time()
                })
                self._tasks.pop(state_key, None)

                at_user = self._format_user_mention(event, uid)
                welcome_msg = self.welcome_message.format(at_user=at_user)
                welcome_image = group_config.get("welcome_image", self.welcome_image)
                await self._send_group_message_with_image(event, gid, welcome_msg, welcome_image)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证码错误，重新生成验证链接")

                state["wrong_count"] = state.get("wrong_count", 0) + 1
                wrong_count = state["wrong_count"]
                await self.db.update_field(state_key, "wrong_count", wrong_count)

                max_wrong_answers = state.get("max_wrong_answers", group_config["max_wrong_answers"])
                if wrong_count >= max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")

                    task = self._tasks.get(state_key)
                    if task and not task.done():
                        task.cancel()

                    at_user = self._format_user_mention(event, uid)
                    kick_msg = self.too_many_wrong_message.format(at_user=at_user, count=wrong_count)
                    await self._send_group_message(event, gid, kick_msg)

                    await asyncio.sleep(2)
                    await self._kick_member(event, gid, uid)

                    final_msg = self.too_many_wrong_kick_message.format(at_user=at_user)
                    await self._send_group_message(event, gid, final_msg)

                    await self.db.delete(state_key)
                    self._tasks.pop(state_key, None)

                    event.stop_event()
                    return

                await self._start_verification_process(event, uid, gid, "", 0, is_new_member=False, group_config=group_config)
                event.stop_event()
        else:
            try:
                match = re.search(r'(\d+)', text)
                if not match:
                    return
                user_answer = int(match.group(1))
            except (ValueError, TypeError):
                return

            correct_answer = state.get("answer")

            if user_answer == correct_answer:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                task = self._tasks.get(state_key)
                if task and not task.done():
                    task.cancel()
                await self.db.set(state_key, {
                    "status": "verified",
                    "verify_time": asyncio.get_event_loop().time()
                })
                self._tasks.pop(state_key, None)

                at_user = self._format_user_mention(event, uid)
                welcome_msg = self.welcome_message.format(at_user=at_user)
                welcome_image = group_config.get("welcome_image", self.welcome_image)
                await self._send_group_message_with_image(event, gid, welcome_msg, welcome_image)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 回答错误，重新生成问题")

                state["wrong_count"] = state.get("wrong_count", 0) + 1
                wrong_count = state["wrong_count"]
                await self.db.update_field(state_key, "wrong_count", wrong_count)

                max_wrong_answers = state.get("max_wrong_answers", group_config["max_wrong_answers"])
                if wrong_count >= max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")

                    task = self._tasks.get(state_key)
                    if task and not task.done():
                        task.cancel()

                    at_user = self._format_user_mention(event, uid)
                    kick_msg = self.too_many_wrong_message.format(at_user=at_user, count=wrong_count)
                    await self._send_group_message(event, gid, kick_msg)

                    await asyncio.sleep(2)
                    await self._kick_member(event, gid, uid)

                    final_msg = self.too_many_wrong_kick_message.format(at_user=at_user)
                    await self._send_group_message(event, gid, final_msg)

                    await self.db.delete(state_key)
                    self._tasks.pop(state_key, None)

                    event.stop_event()
                    return

                question, answer = self._generate_math_problem()
                await self._start_verification_process(event, uid, gid, question, answer, is_new_member=False, group_config=group_config)
                event.stop_event()

    async def _process_member_decrease(self, event: AstrMessageEvent):
        """处理成员退群"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过退群处理")
            return

        if platform == "telegram":
            left_member = self._get_raw_value(raw, "left_chat_member") or {}
            user = self._get_raw_value(left_member, "user") or {}
            uid = str(self._get_raw_value(user, "id"))
        else:
            uid = str(self._get_raw_value(raw, "user_id"))

        state_key = f"{gid}:{uid}"

        if not self.db.contains(state_key):
            return

        task = self._tasks.get(state_key)
        if task and not task.done():
            task.cancel()

        await self.db.delete(state_key)
        self._tasks.pop(state_key, None)

        logger.info(f"[Geetest Verify] 用户 {uid} 已离开群 {gid}，清除验证状态")

    @filter.command("重新验证")
    async def reverify_command(self, event: AstrMessageEvent):
        """强制指定用户重新验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        logger.info(f"[Geetest Verify] 收到重新验证命令，平台: {platform}, 用户: {uid}")

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过重新验证命令")
            return

        logger.info(f"[Geetest Verify] 群组 ID: {gid}")

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await self._send_group_message(event, gid, "当前群未开启验证哦~")
            return

        target_uid = None

        if platform == "telegram":
            message_obj = self._get_raw_value(raw, "message") or {}
            entities = self._get_raw_value(message_obj, "entities") or []
            reply_to_message = self._get_raw_value(message_obj, "reply_to_message") or {}
            text = self._get_raw_value(message_obj, "text") or ""

            logger.info(f"[Geetest Verify] Telegram entities: {entities}, reply_to_message: {bool(reply_to_message)}, text: {text}")

            if reply_to_message:
                target_user = self._get_raw_value(reply_to_message, "from") or {}
                target_uid = str(self._get_raw_value(target_user, "id"))
                logger.info(f"[Geetest Verify] 从回复消息获取到目标用户: {target_uid}")
            else:
                for entity in entities:
                    entity_type = self._get_raw_value(entity, "type")
                    logger.info(f"[Geetest Verify] 处理 entity，类型: {entity_type}")
                    if entity_type == "text_mention":
                        target_user = self._get_raw_value(entity, "user") or {}
                        target_uid = str(self._get_raw_value(target_user, "id"))
                        logger.info(f"[Geetest Verify] 从 text_mention 获取到目标用户: {target_uid}")
                        break
                    elif entity_type == "mention":
                        mention_text = text[self._get_raw_value(entity, "offset"):self._get_raw_value(entity, "offset") + self._get_raw_value(entity, "length")]
                        logger.info(f"[Geetest Verify] 找到 mention: {mention_text}")
                        try:
                            username = mention_text.lstrip('@')
                            platform_client = self.context.get_platform("telegram").get_client()
                            if hasattr(platform_client, "call_action"):
                                logger.info(f"[Geetest Verify] 尝试获取用户 {username} 的信息")

                                try:
                                    chat_info = await platform_client.call_action("getChat", chat_id=f"@{username}")
                                    if chat_info:
                                        target_uid = str(chat_info.get("id"))
                                        logger.info(f"[Geetest Verify] 通过 getChat 获取到用户 ID: {target_uid}")
                                except Exception as e1:
                                    logger.debug(f"[Geetest Verify] getChat 方法失败: {e1}")

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

                if not target_uid:
                    logger.info("[Geetest Verify] 尝试从 event.message_str 中解析 @username")
                    message_str = event.message_str
                    username_match = re.search(r'@([a-zA-Z0-9_]+)', message_str)
                    if username_match:
                        username = username_match.group(1)
                        logger.info(f"[Geetest Verify] 从 message_str 中提取到 username: {username}")
                        logger.warning("[Geetest Verify] Telegram Bot API 不支持通过 username 直接获取 user_id，请使用回复功能")
        else:
            message = self._get_raw_value(raw, "message") or []
            for seg in message:
                if self._get_raw_value(seg, "type") == "at":
                    data = self._get_raw_value(seg, "data") or {}
                    target_uid = str(self._get_raw_value(data, "qq"))
                    break

        logger.info(f"[Geetest Verify] 目标用户 ID: {target_uid}")

        if not target_uid:
            if platform == "telegram":
                await self._send_group_message(event, gid, "无法从 @username 获取用户信息。请回复需要重新验证的用户的消息，然后使用此命令。")
            else:
                await self._send_group_message(event, gid, "请@需要重新验证的用户。")
            return

        target_state_key = f"{gid}:{target_uid}"

        old_task = self._tasks.get(target_state_key)
        if old_task and not old_task.done():
            old_task.cancel()

        question, answer = self._generate_math_problem()

        logger.info(f"[Geetest Verify] 用户 {target_uid} 被强制重新验证，生成问题: {question} (答案: {answer})")

        await self._start_verification_process(event, target_uid, gid, question, answer, is_new_member=True)

        at_target_user = self._format_user_mention(event, target_uid)
        await self._send_group_message(event, gid, f"已要求 {at_target_user} 重新验证")

        event.stop_event()

    @filter.command("绕过验证")
    async def bypass_command(self, event: AstrMessageEvent):
        """让指定用户绕过验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过绕过验证命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await self._send_group_message(event, gid, "当前群未开启验证哦~")
            return

        target_uid = None

        if platform == "telegram":
            message_obj = self._get_raw_value(raw, "message") or {}
            entities = self._get_raw_value(message_obj, "entities") or []
            reply_to_message = self._get_raw_value(message_obj, "reply_to_message") or {}
            text = self._get_raw_value(message_obj, "text") or ""

            if reply_to_message:
                target_user = self._get_raw_value(reply_to_message, "from") or {}
                target_uid = str(self._get_raw_value(target_user, "id"))
            else:
                for entity in entities:
                    entity_type = self._get_raw_value(entity, "type")
                    if entity_type == "text_mention":
                        target_user = self._get_raw_value(entity, "user") or {}
                        target_uid = str(self._get_raw_value(target_user, "id"))
                        break
                    elif entity_type == "mention":
                        mention_text = text[self._get_raw_value(entity, "offset"):self._get_raw_value(entity, "offset") + self._get_raw_value(entity, "length")]
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

                if not target_uid:
                    logger.info("[Geetest Verify] 尝试从 event.message_str 中解析 @username")
                    message_str = event.message_str
                    username_match = re.search(r'@([a-zA-Z0-9_]+)', message_str)
                    if username_match:
                        username = username_match.group(1)
                        logger.info(f"[Geetest Verify] 从 message_str 中提取到 username: {username}")
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
            message = self._get_raw_value(raw, "message") or []
            for seg in message:
                if self._get_raw_value(seg, "type") == "at":
                    data = self._get_raw_value(seg, "data") or {}
                    target_uid = str(self._get_raw_value(data, "qq"))
                    break

        if not target_uid:
            if platform == "telegram":
                await self._send_group_message(event, gid, "请回复需要绕过验证的用户的消息，或点击用户头像后使用命令。")
            else:
                await self._send_group_message(event, gid, "请@需要绕过验证的用户")
            return

        target_state_key = f"{gid}:{target_uid}"

        old_task = self._tasks.get(target_state_key)
        if old_task and not old_task.done():
            old_task.cancel()

        await self.db.set(target_state_key, {
            "status": "bypassed"
        })
        self._tasks.pop(target_state_key, None)

        logger.info(f"[Geetest Verify] 用户 {target_uid} 已标记为绕过验证")

        at_target_user = self._format_user_mention(event, target_uid)
        await self._send_group_message(event, gid, f"已允许 {at_target_user} 绕过验证\n欢迎你的加入！")

        event.stop_event()

    @filter.command("开启验证")
    async def enable_verify_command(self, event: AstrMessageEvent):
        """开启群验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过开启验证命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)

        if group_config["enabled"]:
            await self._send_group_message(event, gid, "本群验证已处于开启状态")
            return

        self._update_group_config(gid, enabled=True)

        await self._send_group_message(event, gid, "已开启本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启验证")

        event.stop_event()

    @filter.command("关闭验证")
    async def disable_verify_command(self, event: AstrMessageEvent):
        """关闭群验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过关闭验证命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)

        if not group_config["enabled"]:
            await self._send_group_message(event, gid, "本群暂未开启验证")
            return

        self._update_group_config(gid, enabled=False)

        await self._send_group_message(event, gid, "已关闭本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭验证")

        event.stop_event()

    @filter.command("设置验证超时时间")
    async def set_timeout_command(self, event: AstrMessageEvent):
        """设置验证超时时间"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过设置超时命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await self._send_group_message(event, gid, "请输入正确的时间（秒）")
            return

        timeout = int(match.group(1))

        self._update_group_config(gid, verification_timeout=timeout)

        await self._send_group_message(event, gid, f"已将本群验证超时时间设置为 {timeout} 秒")

        if timeout < 60:
            await self._send_group_message(event, gid, "你给的时间太少了，建议至少一分钟(60秒)哦")

        logger.info(f"[Geetest Verify] 群 {gid} 验证超时时间设置为 {timeout} 秒")

        event.stop_event()

    @filter.command("设置踢出延迟")
    async def set_kick_delay_command(self, event: AstrMessageEvent):
        """设置验证超时后踢出延迟时间"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过设置踢出延迟命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await self._send_group_message(event, gid, "请输入正确的时间（秒）")
            return

        kick_delay = int(match.group(1))

        self._update_group_config(gid, kick_delay=kick_delay)

        await self._send_group_message(event, gid, f"已将本群验证超时后踢出延迟设置为 {kick_delay} 秒")

        logger.info(f"[Geetest Verify] 群 {gid} 验证超时后踢出延迟设置为 {kick_delay} 秒")

        event.stop_event()

    @filter.command("开启等级验证")
    async def enable_level_verify_command(self, event: AstrMessageEvent):
        """开启等级验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过开启等级验证命令")
            return

        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} Telegram 平台不支持等级验证功能。")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)

        if group_config["enable_level_verify"]:
            await self._send_group_message(event, gid, "本群等级验证已处于开启状态")
            return

        self._update_group_config(gid, enable_level_verify=True)

        await self._send_group_message(event, gid, f"已开启本群等级验证，QQ等级大于等于 {group_config['min_qq_level']} 级的用户将自动跳过验证。")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启等级验证")

        event.stop_event()

    @filter.command("关闭等级验证")
    async def disable_level_verify_command(self, event: AstrMessageEvent):
        """关闭等级验证"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过关闭等级验证命令")
            return

        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} Telegram 平台不支持等级验证功能。")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)

        if not group_config["enable_level_verify"]:
            await self._send_group_message(event, gid, "本群等级验证暂未开启")
            return

        self._update_group_config(gid, enable_level_verify=False)

        await self._send_group_message(event, gid, "已关闭本群等级验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭等级验证")

        event.stop_event()

    @filter.command("设置最低验证等级")
    async def set_min_level_command(self, event: AstrMessageEvent):
        """设置最低验证等级"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过设置最低等级命令")
            return

        if platform == "telegram":
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} Telegram 平台不支持等级验证功能。")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await self._send_group_message(event, gid, "请输入正确的等级（0-64）")
            return

        min_level = int(match.group(1))

        if min_level < 0 or min_level > 64:
            await self._send_group_message(event, gid, "等级必须在 0-64 之间")
            return

        self._update_group_config(gid, min_qq_level=min_level)

        await self._send_group_message(event, gid, f"已将本群最低验证等级设置为 {min_level} 级")
        logger.info(f"[Geetest Verify] 群 {gid} 最低验证等级设置为 {min_level} 级")

        event.stop_event()

    @filter.command("查看验证配置")
    async def show_config_command(self, event: AstrMessageEvent):
        """查看当前群的验证配置"""
        platform = self._get_platform(event)
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())

        gid = self._get_group_id(platform, raw)
        if gid is None:
            logger.warning("[Geetest Verify] 无法获取群组 ID，跳过查看配置命令")
            return

        if not await self._check_permission(event):
            at_user = self._format_user_mention(event, uid)
            await self._send_group_message(event, gid, f"{at_user} 只有群主、管理员或 Bot 管理员才能使用此指令")
            return

        group_config = self._get_group_config(gid)

        if group_config["enabled"]:
            enabled_status = "已开启"
        else:
            enabled_status = "未开启"

        if platform == "telegram":
            chat = self._get_raw_value(raw, "chat") or {}
            group_name = self._get_raw_value(chat, "title") or ""
        else:
            group_name = self._get_raw_value(raw, "group_name") or ""

        if platform == "telegram":
            config_info = f"""群 {group_name}（{gid}）的验证配置信息：

验证状态：{enabled_status}
验证总超时时间：{group_config['verification_timeout']} 秒
验证超时后踢出延迟：{group_config.get('kick_delay', 5)} 秒
最大错误回答次数：{group_config['max_wrong_answers']} 次
极验验证：{'已启用' if group_config['enable_geetest_verify'] else '未启用'}
入群验证延时：{group_config['verify_delay']} 秒

Telegram 平台不支持等级验证，所有新成员均需完成验证"""
        else:
            config_info = f"""群 {group_name}（{gid}）的验证配置信息：

验证状态：{enabled_status}
验证总超时时间：{group_config['verification_timeout']} 秒
验证超时后踢出延迟：{group_config.get('kick_delay', 5)} 秒
最大错误回答次数：{group_config['max_wrong_answers']} 次
极验验证：{'已启用' if group_config['enable_geetest_verify'] else '未启用'}
等级验证：{'已启用' if group_config['enable_level_verify'] else '未启用'}
最低QQ等级：{group_config['min_qq_level']} 级
入群验证延时：{group_config['verify_delay']} 秒

配置来源：{'群级别配置' if any(str(cfg.get('group_id')) == str(gid) for cfg in self.group_configs) else '全局默认配置'}"""

        await self._send_group_message(event, gid, config_info)
        logger.info(f"[Geetest Verify] 群 {gid} 查看验证配置")

        event.stop_event()
