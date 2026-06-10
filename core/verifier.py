import asyncio
import random
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class VerifyMixin:
    """验证流程相关方法：数学题生成、验证流程启动、超时踢出、等级查询、权限检查"""

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

    async def _start_verification_process(self, event, uid: str, gid: int, question: str, answer: int, is_new_member: bool, group_config: dict = None):
        """为用户启动或重启验证流程"""
        state_key = f"{gid}:{uid}"

        if group_config is None:
            group_config = self._get_group_config(gid)

        old_task = self._tasks.get(state_key)
        if old_task and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(self._timeout_kick(uid, gid, group_config["verification_timeout"], event))
        self._tasks[state_key] = task

        if is_new_member:
            await self.db.set(state_key, {
                "status": "pending",
                "question": question,
                "answer": answer,
                "wrong_count": 0,
                "verify_method": "geetest",
                "max_wrong_answers": group_config["max_wrong_answers"]
            })
        else:
            existing = self.db.get_cached(state_key) or {}
            wrong_count = existing.get("wrong_count", 0)
            verify_method = existing.get("verify_method", "geetest")
            await self.db.set(state_key, {
                "status": "pending",
                "question": question,
                "answer": answer,
                "wrong_count": wrong_count,
                "verify_method": verify_method,
                "max_wrong_answers": group_config["max_wrong_answers"]
            })

        at_user = self._format_user_mention(event, uid)
        timeout_minutes = group_config["verification_timeout"] // 60

        if group_config["enable_geetest_verify"] and self.api_key:
            try:
                verify_url_path = await self._create_geetest_verify(gid, uid)
                if verify_url_path:
                    await self.db.update_field(state_key, "verify_method", "geetest")
                    full_verify_url = f"{self.api_base_url}{verify_url_path}"
                    if is_new_member:
                        prompt_message = self.geetest_new_member_prompt.format(at_user=at_user, timeout=timeout_minutes, url=full_verify_url)
                    else:
                        current_state = self.db.get_cached(state_key) or {}
                        wrong_count = current_state.get("wrong_count", 0)
                        remaining_attempts = group_config["max_wrong_answers"] - wrong_count
                        prompt_message = self.geetest_wrong_code_prompt.format(at_user=at_user, url=full_verify_url, remaining=remaining_attempts)
                    await self._send_group_message(event, gid, prompt_message)
                    return
            except Exception as e:
                logger.warning(f"[Geetest Verify] 调用极验 API 失败: {e}，回退到算术验证")

        await self.db.update_field(state_key, "verify_method", "math")
        if is_new_member:
            prompt_message = self.new_member_prompt.format(at_user=at_user, timeout=timeout_minutes, question=question)
        else:
            current_state = self.db.get_cached(state_key) or {}
            wrong_count = current_state.get("wrong_count", 0)
            remaining_attempts = group_config["max_wrong_answers"] - wrong_count
            prompt_message = self.wrong_answer_prompt.format(at_user=at_user, question=question, remaining=remaining_attempts)

        await self._send_group_message(event, gid, prompt_message)

    async def _timeout_kick(self, uid: str, gid: int, timeout: int = None, event = None):
        """处理超时踢出的协程"""
        group_config = self._get_group_config(gid)

        if timeout is None:
            timeout = group_config["verification_timeout"]

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
                if self.db.contains(state_key):
                    at_user = f"[CQ:at,qq={uid}]" if platform == "aiocqhttp" else f"[用户](tg://user?id={uid})"

                    current_state = self.db.get_cached(state_key) or {}
                    verify_method = current_state.get("verify_method", "geetest")

                    if verify_method == "geetest":
                        verify_url_path = await self._create_geetest_verify(gid, uid)

                        if verify_url_path:
                            full_verify_url = f"{self.api_base_url}{verify_url_path}"
                            reminder_msg = self.timeout_reminder_geetest.format(at_user=at_user, url=full_verify_url)
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
                            question, answer = self._generate_math_problem()
                            reminder_msg = self.timeout_reminder_math.format(at_user=at_user, question=question)
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
                            if self.db.contains(state_key):
                                await self.db.update_field(state_key, "verify_method", "math")
                                await self.db.update_field(state_key, "question", question)
                                await self.db.update_field(state_key, "answer", answer)
                            logger.info(f"[Geetest Verify] 用户 {uid} 极验验证失败，已回退到数学题验证")
                    else:
                        question = current_state.get("question", "")
                        if not question:
                            question, answer = self._generate_math_problem()
                            if self.db.contains(state_key):
                                await self.db.update_field(state_key, "question", question)
                                await self.db.update_field(state_key, "answer", answer)

                        reminder_msg = self.timeout_reminder_math.format(at_user=at_user, question=question)
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
                        logger.info(f"[Geetest Verify] 用户 {uid} 验证剩余 1 分钟，已发送数学题提醒")

            await asyncio.sleep(60)

            state_key = f"{gid}:{uid}"
            if not self.db.contains(state_key):
                return

            at_user = f"[CQ:at,qq={uid}]" if platform == "aiocqhttp" else f"[用户](tg://user?id={uid})"

            kick_delay = group_config.get("kick_delay", self.kick_delay)

            failure_msg = self.failure_message.format(at_user=at_user, countdown=kick_delay)
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

            await asyncio.sleep(kick_delay)

            if not self.db.contains(state_key):
                return

            await self._kick_member(event, gid, uid)

            logger.info(f"[Geetest Verify] 用户 {uid} 验证超时，已从群 {gid} 踢出")

            await self.db.delete(state_key)
            self._tasks.pop(state_key, None)

            try:
                kick_msg = self.kick_message.format(at_user=at_user)
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
            except Exception as e:
                logger.warning(f"[Geetest Verify] 发送踢出通知消息失败 (用户 {uid}): {e}")

        except asyncio.CancelledError:
            logger.info(f"[Geetest Verify] 踢出任务已取消 (用户 {uid})")
        except Exception as e:
            logger.error(f"[Geetest Verify] 踢出流程发生错误 (用户 {uid}): {e}")

    async def _get_user_level(self, uid: str) -> int:
        """获取用户QQ等级"""
        try:
            user_info = await self.context.get_platform("aiocqhttp").get_client().api.call_action("get_stranger_info", user_id=int(uid))
            logger.info(f"[Geetest Verify] 用户 {uid} 的API返回数据: {user_info}")

            qq_level = 0
            for key in user_info.keys():
                if key.lower() == "qqlevel":
                    qq_level = user_info[key]
                    break

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

    async def _check_permission(self, event) -> bool:
        """检查用户权限（bot管理员、群主、管理员才可使用）"""
        platform = self._get_platform(event)
        raw_message = event.message_obj.raw_message

        if event.is_admin():
            logger.debug("用户为Bot管理员，跳过权限检查")
            return True

        if platform == "telegram":
            from_user = self._get_raw_value(raw_message, "from") or {}
            gid = self._get_group_id(platform, raw_message)
            if gid is None:
                logger.warning("[Geetest Verify] 无法获取群组 ID，权限检查失败")
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
            sender_dict = self._get_raw_dict(raw_message) if raw_message else {}
            sender = sender_dict.get("sender", {}) if sender_dict else {}
            sender_role = sender.get("role", "member")
            if sender_role in ["admin", "owner"]:
                logger.debug(f"用户为{sender_role}，跳过权限检查")
                return True

        return False
