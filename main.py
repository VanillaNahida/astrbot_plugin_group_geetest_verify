import asyncio
import json
import os
import random
import re
from typing import Dict, Any, Tuple
import aiohttp

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register


@register(
    "group_geetest_verify",
    "香草味的纳西妲喵（VanillaNahida）",
    "QQ群极验验证插件",
    "1.0.0"
)
class GroupGeetestVerifyPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        
        # 待处理的验证: { "user_id": {"gid": group_id, "answer": correct_answer, "task": asyncio.Task, "wrong_count": 0} }
        self.pending: Dict[str, Dict[str, Any]] = {}
        
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
            self.enabled_groups = self.config.get("enabled_groups", schema_defaults.get("enabled_groups", []))
            self.verification_timeout = self.config.get("verification_timeout", schema_defaults.get("verification_timeout", 300))
            self.max_wrong_answers = self.config.get("max_wrong_answers", schema_defaults.get("max_wrong_answers", 5))
            self.api_base_url = self.config.get("api_base_url", schema_defaults.get("api_base_url", "http://localhost:8000"))
            self.api_key = self.config.get("api_key", schema_defaults.get("api_key", ""))
            self.enable_geetest_verify = self.config.get("enable_geetest_verify", schema_defaults.get("enable_geetest_verify", False))
            self.enable_level_verify = self.config.get("enable_level_verify", schema_defaults.get("enable_level_verify", False))
            self.min_qq_level = self.config.get("min_qq_level", schema_defaults.get("min_qq_level", 20))
            self.verify_delay = self.config.get("verify_delay", schema_defaults.get("verify_delay", 0))
        except Exception:
            self.enabled_groups = schema_defaults.get("enabled_groups", [])
            self.verification_timeout = schema_defaults.get("verification_timeout", 300)
            self.max_wrong_answers = schema_defaults.get("max_wrong_answers", 5)
            self.api_base_url = schema_defaults.get("api_base_url", "http://localhost:8000")
            self.api_key = schema_defaults.get("api_key", "")
            self.enable_geetest_verify = schema_defaults.get("enable_geetest_verify", False)
            self.enable_level_verify = schema_defaults.get("enable_level_verify", False)
            self.min_qq_level = schema_defaults.get("min_qq_level", 20)
            self.verify_delay = schema_defaults.get("verify_delay", 3)

    def _save_config(self):
        """保存配置到磁盘"""
        try:
            # 更新配置字典
            self.config["enabled_groups"] = self.enabled_groups
            self.config["verification_timeout"] = self.verification_timeout
            self.config["max_wrong_answers"] = self.max_wrong_answers
            self.config["api_base_url"] = self.api_base_url
            self.config["api_key"] = self.api_key
            self.config["enable_geetest_verify"] = self.enable_geetest_verify
            self.config["enable_level_verify"] = self.enable_level_verify
            self.config["min_qq_level"] = self.min_qq_level
            self.config["verify_delay"] = self.verify_delay
            
            logger.info("[Geetest Verify] 配置已更新到内存")
        except Exception as e:
            logger.error(f"[Geetest Verify] 更新配置失败: {e}")

    async def cleanup(self):
        """清理资源，关闭 aiohttp session"""
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()
            logger.info("[Geetest Verify] 已关闭 aiohttp ClientSession")

    async def _create_geetest_verify(self, gid: int, uid: str) -> str:
        """调用极验 API 生成验证链接"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return None
        
        url = f"{self.api_base_url}/verify/create"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AstrBot/v4.7.0"
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
                        verify_url = result.get("data", {}).get("url")
                        logger.info(f"[Geetest Verify] 成功生成验证链接: {verify_url}")
                        return verify_url
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
            "Content-Type": "application/json"
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
        if event.get_platform_name() != "aiocqhttp":
            return

        raw = event.message_obj.raw_message
        post_type = raw.get("post_type")
        
        if post_type == "notice":
            if raw.get("notice_type") == "group_increase":
                await self._process_new_member(event)
            elif raw.get("notice_type") == "group_decrease":
                await self._process_member_decrease(event)
        elif post_type == "message" and raw.get("message_type") == "group":
            await self._process_verification_message(event)

    async def _process_new_member(self, event: AstrMessageEvent):
        """处理新成员入群"""
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        
        # 检查群是否开启了验证
        # 如果 enabled_groups 为空，则对所有群生效（检查 KV 数据库）
        # 如果 enabled_groups 不为空，则只对列表中的群生效
        if self.enabled_groups:
            if gid not in self.enabled_groups:
                return
        else:
            enabled = await self.get_kv_data(f"group_{gid}_enabled", False)
            if not enabled:
                return
        
        # 检查用户是否已被标记为绕过验证
        bypassed = await self.get_kv_data(f"{gid}:{uid}_bypassed", False)
        if bypassed:
            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已标记为绕过验证，跳过验证流程")
            return
        
        # 检查用户是否已验证过
        verified = await self.get_kv_data(f"{gid}:{uid}_verified", False)
        if verified:
            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已验证过，跳过验证流程")
            return
        
        # 检查是否启用了等级验证
        if self.enable_level_verify:
            qq_level = await self._get_user_level(uid)
            if qq_level >= self.min_qq_level:
                logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，达到最低等级要求 {self.min_qq_level}，跳过验证流程")
                # 标记用户为已验证
                await self.put_kv_data(f"{gid}:{uid}_verify_status", "verified")
                await self.put_kv_data(f"{gid}:{uid}_verified", True)
                await self.put_kv_data(f"{gid}:{uid}_verify_time", asyncio.get_event_loop().time())
                return
        
        # 存储用户的入群验证信息
        question, answer = self._generate_math_problem()
        verify_info = {
            "gid": gid,
            "join_time": asyncio.get_event_loop().time(),
            "question": question,
            "answer": answer
        }
        await self.put_kv_data(f"{gid}:{uid}_verify_info", verify_info)
        await self.put_kv_data(f"{gid}:{uid}_verify_status", "pending")
        
        logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 入群，生成验证问题: {question} (答案: {answer})")
        
        # 延时发送验证消息
        if self.verify_delay > 0:
            logger.info(f"[Geetest Verify] 群 {gid} 新成员 {uid} 入群，将在 {self.verify_delay} 秒后发送验证消息")
            await asyncio.sleep(self.verify_delay)
        
        await self._start_verification_process(event, uid, gid, question, answer, is_new_member=True)

    async def _start_verification_process(self, event: AstrMessageEvent, uid: str, gid: int, question: str, answer: int, is_new_member: bool):
        """为用户启动或重启验证流程"""
        if uid in self.pending:
            old_task = self.pending[uid].get("task")
            if old_task and not old_task.done():
                old_task.cancel()

        task = asyncio.create_task(self._timeout_kick(uid, gid))
        
        # 如果是新成员，重置错误计数；否则保留现有错误计数
        if is_new_member:
            self.pending[uid] = {"gid": gid, "answer": answer, "task": task, "wrong_count": 0, "verify_method": "geetest"}
        else:
            wrong_count = self.pending.get(uid, {}).get("wrong_count", 0)
            verify_method = self.pending.get(uid, {}).get("verify_method", "geetest")
            self.pending[uid] = {"gid": gid, "answer": answer, "task": task, "wrong_count": wrong_count, "verify_method": verify_method}

        at_user = f"[CQ:at,qq={uid}]"
        timeout_minutes = self.verification_timeout // 60
        
        # 如果启用了极验验证，优先使用极验验证
        if self.enable_geetest_verify and self.api_key:
            try:
                verify_url = await self._create_geetest_verify(gid, uid)
                if verify_url:
                    self.pending[uid]["verify_method"] = "geetest"
                    if is_new_member:
                        prompt_message = f"{at_user} 欢迎加入本群！请在 {timeout_minutes} 分钟内复制下方链接前往浏览器完成人机验证：\n{verify_url}\n验证完成后，请在群内发送六位数验证码。"
                    else:
                        prompt_message = f"{at_user} 验证码错误，请重新复制下方链接前往浏览器完成人机验证：\n{verify_url}\n验证完成后，请在群内发送六位数验证码。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=prompt_message)
                    return
            except Exception as e:
                logger.warning(f"[Geetest Verify] 调用极验 API 失败: {e}，回退到算术验证")
        
        # 回退到算术验证
        self.pending[uid]["verify_method"] = "math"
        if is_new_member:
            prompt_message = f"{at_user} 欢迎加入本群！请在 {timeout_minutes} 分钟内 @我 并回答下面的问题以完成验证：\n{question}"
        else:
            prompt_message = f"{at_user} 答案错误，请重新回答验证。这是你的新问题：\n{question}"

        await event.bot.api.call_action("send_group_msg", group_id=gid, message=prompt_message)

    async def _process_verification_message(self, event: AstrMessageEvent):
        """处理群消息以进行验证"""
        uid = str(event.get_sender_id())
        if uid not in self.pending:
            return
        
        text = event.message_str.strip()
        raw = event.message_obj.raw_message
        gid = self.pending[uid]["gid"]
        
        current_gid = raw.get("group_id")
        if current_gid and str(current_gid) != str(gid):
            return
        
        # 如果启用了极验验证，使用 API 验证验证码
        if self.enable_geetest_verify:
            # 提取验证码（6位数字+字母）
            match = re.search(r'([A-Za-z0-9]{6})', text)
            if not match:
                return
            user_code = match.group(1)
            
            # 调用 API 验证验证码
            is_valid = await self._check_geetest_verify(gid, uid, user_code)
            
            if is_valid:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                self.pending[uid]["task"].cancel()
                self.pending.pop(uid, None)

                # 更新验证状态
                await self.put_kv_data(f"{gid}:{uid}_verify_status", "verified")
                await self.put_kv_data(f"{gid}:{uid}_verified", True)
                await self.put_kv_data(f"{gid}:{uid}_verify_time", asyncio.get_event_loop().time())

                welcome_msg = f"[CQ:at,qq={uid}] 验证成功，欢迎你的加入！"
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=welcome_msg)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证码错误，重新生成验证链接")
                
                # 增加错误计数
                self.pending[uid]["wrong_count"] += 1
                wrong_count = self.pending[uid]["wrong_count"]
                
                # 检查是否超过最大错误次数
                if wrong_count >= self.max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")
                    
                    # 取消超时任务
                    self.pending[uid]["task"].cancel()
                    self.pending.pop(uid, None)
                    
                    # 发送踢出消息
                    at_user = f"[CQ:at,qq={uid}]"
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await event.bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=final_msg)
                    
                    event.stop_event()
                    return
                
                # 重新生成验证链接
                await self._start_verification_process(event, uid, gid, "", 0, is_new_member=False)
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

            correct_answer = self.pending[uid].get("answer")

            if user_answer == correct_answer:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 验证成功")
                self.pending[uid]["task"].cancel()
                self.pending.pop(uid, None)

                # 更新验证状态
                await self.put_kv_data(f"{gid}:{uid}_verify_status", "verified")
                await self.put_kv_data(f"{gid}:{uid}_verified", True)
                await self.put_kv_data(f"{gid}:{uid}_verify_time", asyncio.get_event_loop().time())
                # nickname = raw.get("sender", {}).get("card", "") or raw.get("sender", {}).get("nickname", uid)
                welcome_msg = f"[CQ:at,qq={uid}] 验证成功，欢迎你的加入！"
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=welcome_msg)
                event.stop_event()
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 回答错误，重新生成问题")
                
                # 增加错误计数
                self.pending[uid]["wrong_count"] += 1
                wrong_count = self.pending[uid]["wrong_count"]
                
                # 检查是否超过最大错误次数
                if wrong_count >= self.max_wrong_answers:
                    logger.info(f"[Geetest Verify] 用户 {uid} 回答错误次数达到 {wrong_count} 次，将踢出")
                    
                    # 取消超时任务
                    self.pending[uid]["task"].cancel()
                    self.pending.pop(uid, None)
                    
                    # 发送踢出消息
                    at_user = f"[CQ:at,qq={uid}]"
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await event.bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=final_msg)
                    
                    event.stop_event()
                    return
                
                # 更新验证信息
                question, answer = self._generate_math_problem()
                verify_info = await self.get_kv_data(f"{gid}:{uid}_verify_info", {})
                verify_info["question"] = question
                verify_info["answer"] = answer
                await self.put_kv_data(f"{gid}:{uid}_verify_info", verify_info)
                
                await self._start_verification_process(event, uid, gid, question, answer, is_new_member=False)
                event.stop_event()

    async def _process_member_decrease(self, event: AstrMessageEvent):
        """处理成员离开"""
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        
        if uid in self.pending:
            self.pending[uid]["task"].cancel()
            self.pending.pop(uid, None)
            logger.info(f"[Geetest Verify] 待验证用户 {uid} 已离开，清理其验证状态")
        
        await self.put_kv_data(f"{gid}:{uid}_verified", False)
        await self.put_kv_data(f"{gid}:{uid}_verify_status", "pending")
        logger.info(f"[Geetest Verify] 用户 {uid} 已离开群 {gid}，清除验证状态")

    async def _check_user_permission(self, event: AstrMessageEvent, uid: str, gid: int) -> bool:
        """检查用户是否是群主或管理员"""
        try:
            member_info = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            role = member_info.get("role", "")
            return role in ["owner", "admin"]
        except Exception as e:
            logger.error(f"[Geetest Verify] 检查用户权限失败: {e}")
            return False

    async def _get_user_level(self, uid: str) -> int:
        """获取用户QQ等级"""
        try:
            user_info = await self.context.get_platform("aiocqhttp").get_client().api.call_action("get_user_info", user_id=int(uid))
            qq_level = user_info.get("qqLevel", 0)
            logger.info(f"[Geetest Verify] 用户 {uid} 的QQ等级为: {qq_level}")
            return qq_level
        except Exception as e:
            logger.error(f"[Geetest Verify] 获取用户 {uid} 的QQ等级失败: {e}")
            return 0

    async def _timeout_kick(self, uid: str, gid: int):
        """处理超时踢出的协程"""
        try:
            if self.verification_timeout > 120:
                await asyncio.sleep(self.verification_timeout - 60)

                if uid in self.pending:
                    bot = self.context.get_platform("aiocqhttp").get_client()
                    at_user = f"[CQ:at,qq={uid}]"
                    reminder_msg = f"{at_user} 验证剩余最后 1 分钟，请尽快完成验证！"
                    await bot.api.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                    logger.info(f"[Geetest Verify] 用户 {uid} 验证剩余 1 分钟，已发送提醒")

            await asyncio.sleep(60)

            if uid not in self.pending:
                return

            bot = self.context.get_platform("aiocqhttp").get_client()
            at_user = f"[CQ:at,qq={uid}]"
            
            failure_msg = f"{at_user} 验证超时，你将在 5 秒后被请出本群。"
            await bot.api.call_action("send_group_msg", group_id=gid, message=failure_msg)
            
            await asyncio.sleep(5)

            if uid not in self.pending:
                return
            
            await bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
            logger.info(f"[Geetest Verify] 用户 {uid} 验证超时，已从群 {gid} 踢出")
            
            kick_msg = f"{at_user} 因未在规定时间内完成验证，已被请出本群。"
            await bot.api.call_action("send_group_msg", group_id=gid, message=kick_msg)

        except asyncio.CancelledError:
            logger.info(f"[Geetest Verify] 踢出任务已取消 (用户 {uid})")
        except Exception as e:
            logger.error(f"[Geetest Verify] 踢出流程发生错误 (用户 {uid}): {e}")

    @filter.command("重新验证")
    async def reverify_command(self, event: AstrMessageEvent):
        """强制指定用户重新验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        enabled = await self.get_kv_data(f"group_{gid}_enabled", False)
        if not enabled:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 当前群未开启验证哦~")
            return
        
        # 检查是否有权限（这里简单判断是否@了其他用户）
        message = raw.get("message", [])
        target_uid = None
        
        for seg in message:
            if seg.get("type") == "at":
                target_uid = str(seg.get("data", {}).get("qq"))
                break
        
        # 如果没有@用户，检查是否是"从未发言的人"
        text = event.message_str.replace("/重新验证", "").strip()
        if not target_uid and text == "从未发言的人":
            await self._reverify_never_speak(event, gid, uid)
            return
        
        if not target_uid:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 请@需要重新验证的用户")
            return
        
        # 清除用户的验证状态
        await self.put_kv_data(f"{gid}:{target_uid}_verify_status", "pending")
        await self.put_kv_data(f"{gid}:{target_uid}_verified", False)
        await self.put_kv_data(f"{gid}:{target_uid}_bypassed", False)
        
        # 如果用户正在验证中，取消之前的任务
        if target_uid in self.pending:
            old_task = self.pending[target_uid].get("task")
            if old_task and not old_task.done():
                old_task.cancel()
            self.pending.pop(target_uid, None)
        
        # 生成新的验证问题
        question, answer = self._generate_math_problem()
        verify_info = {
            "gid": gid,
            "join_time": asyncio.get_event_loop().time(),
            "question": question,
            "answer": answer
        }
        await self.put_kv_data(f"{gid}:{target_uid}_verify_info", verify_info)
        
        logger.info(f"[Geetest Verify] 用户 {target_uid} 被强制重新验证，生成问题: {question} (答案: {answer})")
        
        # 启动验证流程
        await self._start_verification_process(event, target_uid, gid, question, answer, is_new_member=True)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已要求 [CQ:at,qq={target_uid}] 重新验证")

    async def _reverify_never_speak(self, event: AstrMessageEvent, gid: int, operator_uid: str):
        """为从未发言的人重新验证"""
        try:
            # 获取群成员列表
            member_list = await event.bot.api.call_action("get_group_member_list", group_id=gid)
            
            count = 0
            for member in member_list:
                member_uid = str(member.get("user_id"))
                
                # 跳过机器人自己
                if member_uid == str(event.get_self_id()):
                    continue
                
                # 跳过管理员和群主
                if member.get("role") in ["admin", "owner"]:
                    continue
                
                # 检查用户是否已验证过
                verified = await self.get_kv_data(f"{gid}:{member_uid}_verified", False)
                if verified:
                    continue
                
                # 检查用户是否已被标记为绕过验证
                bypassed = await self.get_kv_data(f"{gid}:{member_uid}_bypassed", False)
                if bypassed:
                    continue
                
                # 为该用户启动验证
                question, answer = self._generate_math_problem()
                verify_info = {
                    "gid": gid,
                    "join_time": asyncio.get_event_loop().time(),
                    "question": question,
                    "answer": answer
                }
                await self.put_kv_data(f"{gid}:{member_uid}_verify_info", verify_info)
                await self.put_kv_data(f"{gid}:{member_uid}_verify_status", "pending")
                
                # 如果用户正在验证中，取消之前的任务
                if member_uid in self.pending:
                    old_task = self.pending[member_uid].get("task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                
                # 启动验证流程
                await self._start_verification_process(event, member_uid, gid, question, answer, is_new_member=True)
                
                count += 1
                logger.info(f"[Geetest Verify] 为从未发言的用户 {member_uid} 启动验证")
                
                # 等待2秒再处理下一个
                await asyncio.sleep(2)
            
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={operator_uid}] 已为 {count} 位从未发言的用户启动验证")
            
        except Exception as e:
            logger.error(f"[Geetest Verify] 获取群成员列表失败: {e}")
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={operator_uid}] 获取群成员列表失败")

    @filter.command("绕过验证")
    async def bypass_command(self, event: AstrMessageEvent):
        """让指定用户绕过验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        enabled = await self.get_kv_data(f"group_{gid}_enabled", False)
        if not enabled:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 当前群未开启验证哦~")
            return
        
        # 检查是否有权限（这里简单判断是否@了其他用户）
        message = raw.get("message", [])
        target_uid = None
        
        for seg in message:
            if seg.get("type") == "at":
                target_uid = str(seg.get("data", {}).get("qq"))
                break
        
        if not target_uid:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 请@需要绕过验证的用户")
            return
        
        # 标记用户为绕过验证
        await self.put_kv_data(f"{gid}:{target_uid}_bypassed", True)
        await self.put_kv_data(f"{gid}:{target_uid}_verify_status", "bypassed")
        
        # 如果用户正在验证中，取消任务
        if target_uid in self.pending:
            old_task = self.pending[target_uid].get("task")
            if old_task and not old_task.done():
                old_task.cancel()
            self.pending.pop(target_uid, None)
        
        logger.info(f"[Geetest Verify] 用户 {target_uid} 已标记为绕过验证")
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已允许 [CQ:at,qq={target_uid}] 绕过验证")

    @filter.command("开启验证")
    async def enable_verify_command(self, event: AstrMessageEvent):
        """开启群验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查是否已在配置列表中
        if gid in self.enabled_groups:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 本群验证已处于开启状态")
            return
        
        # 添加到启用列表
        self.enabled_groups.append(gid)
        
        # 保存配置
        self._save_config()
        
        # 同时更新 KV 数据库（兼容旧版本）
        await self.put_kv_data(f"group_{gid}_enabled", True)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已开启本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启验证")

    @filter.command("关闭验证")
    async def disable_verify_command(self, event: AstrMessageEvent):
        """关闭群验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查是否在配置列表中
        if self.enabled_groups and gid not in self.enabled_groups:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 本群暂未开启验证")
            return
        
        # 从启用列表中移除
        if gid in self.enabled_groups:
            self.enabled_groups.remove(gid)
            
            # 保存配置
            self._save_config()
        
        # 同时更新 KV 数据库（兼容旧版本）
        await self.put_kv_data(f"group_{gid}_enabled", False)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已关闭本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭验证")

    @filter.command("设置验证超时时间")
    async def set_timeout_command(self, event: AstrMessageEvent):
        """设置验证超时时间"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 请输入正确的时间（秒）")
            return
        
        timeout = int(match.group(1))
        self.verification_timeout = timeout
        
        # 保存配置
        self._save_config()
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已将验证超时时间设置为 {timeout} 秒")
        
        if timeout < 60:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 建议至少一分钟(60秒)哦ε(*´･ω･)з")
        
        logger.info(f"[Geetest Verify] 群 {gid} 验证超时时间设置为 {timeout} 秒")

    @filter.command("开启等级验证")
    async def enable_level_verify_command(self, event: AstrMessageEvent):
        """开启等级验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查是否已开启
        if self.enable_level_verify:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 等级验证已处于开启状态")
            return
        
        # 开启等级验证
        self.enable_level_verify = True
        
        # 保存配置
        self._save_config()
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已开启等级验证，QQ等级大于等于 {self.min_qq_level} 级的用户将自动跳过验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启等级验证")

    @filter.command("关闭等级验证")
    async def disable_level_verify_command(self, event: AstrMessageEvent):
        """关闭等级验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 检查是否已关闭
        if not self.enable_level_verify:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 等级验证暂未开启")
            return
        
        # 关闭等级验证
        self.enable_level_verify = False
        
        # 保存配置
        self._save_config()
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已关闭等级验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭等级验证")

    @filter.command("设置最低验证等级")
    async def set_min_level_command(self, event: AstrMessageEvent):
        """设置最低验证等级"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_user_permission(event, uid, gid):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主和管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 请输入正确的等级（0-64）")
            return
        
        min_level = int(match.group(1))
        
        # 验证等级范围
        if min_level < 0 or min_level > 64:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 等级必须在 0-64 之间")
            return
        
        self.min_qq_level = min_level
        
        # 保存配置
        self._save_config()
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 已将最低验证等级设置为 {min_level} 级")
        logger.info(f"[Geetest Verify] 群 {gid} 最低验证等级设置为 {min_level} 级")
