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
    "QQ群极验验证插件",
    "1.1.4"
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
            self.enabled_groups = self.config.get("enabled_groups", schema_defaults.get("enabled_groups", []))
            self.verification_timeout = self.config.get("verification_timeout", schema_defaults.get("verification_timeout", 300))
            self.max_wrong_answers = self.config.get("max_wrong_answers", schema_defaults.get("max_wrong_answers", 5))
            self.api_base_url = self.config.get("api_base_url", schema_defaults.get("api_base_url", ""))
            self.api_key = self.config.get("api_key", schema_defaults.get("api_key", ""))
            self.enable_geetest_verify = self.config.get("enable_geetest_verify", schema_defaults.get("enable_geetest_verify", False))
            self.enable_level_verify = self.config.get("enable_level_verify", schema_defaults.get("enable_level_verify", False))
            self.min_qq_level = self.config.get("min_qq_level", schema_defaults.get("min_qq_level", 20))
            self.verify_delay = self.config.get("verify_delay", schema_defaults.get("verify_delay", 0))
            self.group_configs = self.config.get("group_configs", [])
        except Exception:
            self.enabled_groups = schema_defaults.get("enabled_groups", [])
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
            self.config["enabled_groups"] = self.enabled_groups
            self.config["verification_timeout"] = self.verification_timeout
            self.config["max_wrong_answers"] = self.max_wrong_answers
            self.config["api_base_url"] = self.api_base_url
            self.config["api_key"] = self.api_key
            self.config["enable_geetest_verify"] = self.enable_geetest_verify
            self.config["enable_level_verify"] = self.enable_level_verify
            self.config["min_qq_level"] = self.min_qq_level
            self.config["verify_delay"] = self.verify_delay
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
                    "enabled": group_config.get("enabled", gid in self.enabled_groups),
                    "verification_timeout": group_config.get("verification_timeout", self.verification_timeout),
                    "max_wrong_answers": group_config.get("max_wrong_answers", self.max_wrong_answers),
                    "enable_geetest_verify": group_config.get("enable_geetest_verify", self.enable_geetest_verify),
                    "enable_level_verify": group_config.get("enable_level_verify", self.enable_level_verify),
                    "min_qq_level": group_config.get("min_qq_level", self.min_qq_level),
                    "verify_delay": group_config.get("verify_delay", self.verify_delay)
                }
        
        # 没有找到群级别配置，返回默认配置
        return {
            "enabled": gid in self.enabled_groups,
            "verification_timeout": self.verification_timeout,
            "max_wrong_answers": self.max_wrong_answers,
            "enable_geetest_verify": self.enable_geetest_verify,
            "enable_level_verify": self.enable_level_verify,
            "min_qq_level": self.min_qq_level,
            "verify_delay": self.verify_delay
        }

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
        state_key = f"{gid}:{uid}"
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            return
        
        # 检查用户是否已被标记为绕过验证
        if state_key in self.verify_states and self.verify_states[state_key].get("status") == "bypassed":
            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已标记为绕过验证，跳过验证流程")
            return
        
        # 检查用户是否已验证过
        if state_key in self.verify_states and self.verify_states[state_key].get("status") == "verified":
            logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 已验证过，跳过验证流程")
            return

        # 获取群级别配置
        group_config = self._get_group_config(gid)
        
        # 延时2秒
        await asyncio.sleep(2)
        # 检查是否启用了等级验证
        at_user = f"[CQ:at,qq={uid}]"
        skip_verify = False
        if group_config["enable_level_verify"]:
            qq_level = await self._get_user_level(uid)
            if qq_level >= group_config["min_qq_level"]:
                logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，达到最低等级要求 {group_config['min_qq_level']}，跳过验证流程")
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"{at_user} 您的QQ等级为 {qq_level}，大于等于最低等级要求 {group_config['min_qq_level']}级，已跳过验证流程。\n欢迎你的加入！")
                # 标记用户为已验证
                self.verify_states[state_key] = {
                    "status": "verified",
                    "verify_time": asyncio.get_event_loop().time()
                }
                skip_verify = True
            else:
                logger.info(f"[Geetest Verify] 用户 {uid} QQ等级为 {qq_level}，低于最低等级要求 {group_config['min_qq_level']}，将进入验证流程")
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"{at_user} 您的QQ等级为 {qq_level}，低于最低等级要求 {group_config['min_qq_level']}级，将进入验证流程。")
        
        if skip_verify:
            return
        
        # 存储用户的入群验证信息
        question, answer = self._generate_math_problem()
        
        logger.info(f"[Geetest Verify] 用户 {uid} 在群 {gid} 入群，生成验证问题: {question} (答案: {answer})")
        
        # 延时发送验证消息
        if group_config["verify_delay"] > 0:
            logger.info(f"[Geetest Verify] 群 {gid} 新成员 {uid} 入群，将在 {group_config['verify_delay']} 秒后发送验证消息")
            await asyncio.sleep(group_config["verify_delay"])
        
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

        task = asyncio.create_task(self._timeout_kick(uid, gid, group_config["verification_timeout"]))
        
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

        at_user = f"[CQ:at,qq={uid}]"
        timeout_minutes = group_config["verification_timeout"] // 60

        # 如果启用了极验验证，优先使用极验验证
        if group_config["enable_geetest_verify"] and self.api_key:
            try:
                verify_url = await self._create_geetest_verify(gid, uid)
                if verify_url:
                    self.verify_states[state_key]["verify_method"] = "geetest"
                    if is_new_member:
                        prompt_message = f"{at_user} 欢迎加入本群！请在 {timeout_minutes} 分钟内复制下方链接前往浏览器完成人机验证：\n{verify_url}\n验证完成后，请在群内发送六位数验证码。"
                    else:
                        wrong_count = self.verify_states.get(state_key, {}).get("wrong_count", 0)
                        remaining_attempts = group_config["max_wrong_answers"] - wrong_count
                        prompt_message = f"{at_user} 验证码错误，请重新复制下方链接前往浏览器完成人机验证：\n{verify_url}\n验证完成后，请在群内发送六位数验证码。\n您的剩余尝试次数：{remaining_attempts}"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=prompt_message)
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

        await event.bot.api.call_action("send_group_msg", group_id=gid, message=prompt_message)

    async def _process_verification_message(self, event: AstrMessageEvent):
        """处理群消息以进行验证"""
        uid = str(event.get_sender_id())
        raw = event.message_obj.raw_message
        gid = raw.get("group_id")
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

                welcome_msg = f"[CQ:at,qq={uid}] 验证成功，欢迎你的加入！"
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=welcome_msg)
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
                    at_user = f"[CQ:at,qq={uid}]"
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await event.bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=final_msg)
                    
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

                welcome_msg = f"[CQ:at,qq={uid}] 验证成功，欢迎你的加入！"
                await event.bot.api.call_action("send_group_msg", group_id=gid, message=welcome_msg)
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
                    at_user = f"[CQ:at,qq={uid}]"
                    kick_msg = f"{at_user} 你已连续回答错误 {wrong_count} 次，将被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                    
                    # 踢出用户
                    await asyncio.sleep(2)
                    await event.bot.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
                    
                    # 发送踢出完成消息
                    final_msg = f"{at_user} 因回答错误次数过多，已被请出本群。"
                    await event.bot.api.call_action("send_group_msg", group_id=gid, message=final_msg)
                    
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
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
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

    async def _timeout_kick(self, uid: str, gid: int, timeout: int = None):
        """处理超时踢出的协程"""
        if timeout is None:
            # 使用群级别配置
            group_config = self._get_group_config(gid)
            timeout = group_config["verification_timeout"]
            
        try:
            if timeout > 120:
                await asyncio.sleep(timeout - 60)

                state_key = f"{gid}:{uid}"
                if state_key in self.verify_states:
                    bot = self.context.get_platform("aiocqhttp").get_client()
                    at_user = f"[CQ:at,qq={uid}]"
                    # 刷新验证链接
                    verify_url = await self._create_geetest_verify(gid, uid)
                    timeout_minutes = group_config["verification_timeout"] // 60
                    reminder_msg = f"{at_user} 验证剩余最后 1 分钟，请尽快完成验证！\n 请在 {timeout_minutes} 分钟内复制下方链接前往浏览器完成人机验证，之前的链接已失效，请使用新链接完成验证：\n{verify_url}\n验证完成后，请在群内发送六位数验证码。"
                    await bot.api.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                    logger.info(f"[Geetest Verify] 用户 {uid} 验证剩余 1 分钟，已发送提醒")

            await asyncio.sleep(60)

            state_key = f"{gid}:{uid}"
            if state_key not in self.verify_states:
                return

            bot = self.context.get_platform("aiocqhttp").get_client()
            at_user = f"[CQ:at,qq={uid}]"
            
            failure_msg = f"{at_user} 验证超时，你将在 5 秒后被请出本群。"
            await bot.api.call_action("send_group_msg", group_id=gid, message=failure_msg)
            
            await asyncio.sleep(5)

            if state_key not in self.verify_states:
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
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"[CQ:at,qq={uid}] 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"当前群未开启验证哦~")
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
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 请@需要重新验证的用户。")
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
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已要求 [CQ:at,qq={target_uid}] 重新验证")

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
                member_state_key = f"{gid}:{member_uid}"
                if member_state_key in self.verify_states:
                    state = self.verify_states[member_state_key]
                    if state.get("status") == "verified" or state.get("status") == "bypassed":
                        continue
                
                # 为该用户启动验证
                question, answer = self._generate_math_problem()
                
                # 如果用户正在验证中，取消之前的任务
                if member_state_key in self.verify_states:
                    old_task = self.verify_states[member_state_key].get("task")
                    if old_task and not old_task.done():
                        old_task.cancel()
                
                # 启动验证流程
                await self._start_verification_process(event, member_uid, gid, question, answer, is_new_member=True)
                
                count += 1
                logger.info(f"[Geetest Verify] 为从未发言的用户 {member_uid} 启动验证")
                
                # 等待2秒再处理下一个
                await asyncio.sleep(2)
            
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已为 {count} 位从未发言的用户启动验证")
            
        except Exception as e:
            logger.error(f"[Geetest Verify] 获取群成员列表失败: {e}")
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 获取群成员列表失败！")

    @filter.command("绕过验证")
    async def bypass_command(self, event: AstrMessageEvent):
        """让指定用户绕过验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        if not group_config["enabled"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 当前群未开启验证哦~")
            return
        
        # 检查是否有权限（这里简单判断是否@了其他用户）
        message = raw.get("message", [])
        target_uid = None
        
        for seg in message:
            if seg.get("type") == "at":
                target_uid = str(seg.get("data", {}).get("qq"))
                break
        
        if not target_uid:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 请@需要绕过验证的用户")
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
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已允许 [CQ:at,qq={target_uid}] 绕过验证")

    @filter.command("开启验证")
    async def enable_verify_command(self, event: AstrMessageEvent):
        """开启群验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已开启
        if group_config["enabled"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 本群验证已处于开启状态")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, enabled=True)
        
        # 同时更新内存状态（兼容旧版本）
        self.verify_states[f"group_{gid}_enabled"] = {"enabled": True}
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已开启本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启验证")

    @filter.command("关闭验证")
    async def disable_verify_command(self, event: AstrMessageEvent):
        """关闭群验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已关闭
        if not group_config["enabled"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 本群暂未开启验证")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, enabled=False)
        
        # 同时更新内存状态（兼容旧版本）
        self.verify_states[f"group_{gid}_enabled"] = {"enabled": False}
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已关闭本群验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭验证")

    @filter.command("设置验证超时时间")
    async def set_timeout_command(self, event: AstrMessageEvent):
        """设置验证超时时间"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 请输入正确的时间（秒）")
            return
        
        timeout = int(match.group(1))
        
        # 更新群级别配置
        self._update_group_config(gid, verification_timeout=timeout)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已将本群验证超时时间设置为 {timeout} 秒")
        
        if timeout < 60:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"你给的时间太少了，建议至少一分钟(60秒)哦ε(*´･ω･)з")
        
        logger.info(f"[Geetest Verify] 群 {gid} 验证超时时间设置为 {timeout} 秒")

    @filter.command("开启等级验证")
    async def enable_level_verify_command(self, event: AstrMessageEvent):
        """开启等级验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已开启
        if group_config["enable_level_verify"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 本群等级验证已处于开启状态")
            return
        
        # 开启等级验证
        self._update_group_config(gid, enable_level_verify=True)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已开启本群等级验证，QQ等级大于等于 {group_config['min_qq_level']} 级的用户将自动跳过验证。")
        logger.info(f"[Geetest Verify] 群 {gid} 已开启等级验证")

    @filter.command("关闭等级验证")
    async def disable_level_verify_command(self, event: AstrMessageEvent):
        """关闭等级验证"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取当前群配置
        group_config = self._get_group_config(gid)
        
        # 检查是否已关闭
        if not group_config["enable_level_verify"]:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 本群等级验证暂未开启")
            return
        
        # 关闭等级验证
        self._update_group_config(gid, enable_level_verify=False)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已关闭本群等级验证")
        logger.info(f"[Geetest Verify] 群 {gid} 已关闭等级验证")

    @filter.command("设置最低验证等级")
    async def set_min_level_command(self, event: AstrMessageEvent):
        """设置最低验证等级"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 从消息中提取数字
        text = event.message_str
        match = re.search(r'(\d+)', text)
        if not match:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 请输入正确的等级（0-64）")
            return
        
        min_level = int(match.group(1))
        
        # 验证等级范围
        if min_level < 0 or min_level > 64:
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 等级必须在 0-64 之间")
            return
        
        # 更新群级别配置
        self._update_group_config(gid, min_qq_level=min_level)
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"✅ 已将本群最低验证等级设置为 {min_level} 级")
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
        raw_message = event.message_obj.raw_message
        
        # 检查是否是 Bot 管理员
        if event.is_admin():
            logger.debug(f"用户为Bot管理员，跳过权限检查")
            return True
        
        # 检查群权限（群主、管理员才可使用）
        sender_role = raw_message.get("sender", {}).get("role", "member") if raw_message else "member"
        if sender_role in ["admin", "owner"]:
            logger.debug(f"用户为{sender_role}，跳过权限检查")
            return True
        
        return False

    @filter.command("查看验证配置")
    async def show_config_command(self, event: AstrMessageEvent):
        """查看当前群的验证配置"""
        raw = event.message_obj.raw_message
        uid = str(event.get_sender_id())
        gid = raw.get("group_id")
        
        # 检查用户权限
        if not await self._check_permission(event):
            await event.bot.api.call_action("send_group_msg", group_id=gid, message=f"❎ 只有群主、管理员或 Bot 管理员才能使用此指令")
            return
        
        # 获取群级别配置
        group_config = self._get_group_config(gid)
        
        # 检查群是否开启了验证
        group_config = self._get_group_config(gid)
        
        if group_config["enabled"]:
            enabled_status = "✅ 已开启"
        else:
            enabled_status = "❌ 未开启"
        
        # 构建配置信息
        config_info = f"""📋 群 {gid} 验证配置信息：

🔹 验证状态：{enabled_status}
🔹 验证总超时时间：{group_config['verification_timeout']} 秒
🔹 最大错误回答次数：{group_config['max_wrong_answers']} 次
🔹 极验验证：{'✅ 已启用' if group_config['enable_geetest_verify'] else '❌ 未启用'}
🔹 等级验证：{'✅ 已启用' if group_config['enable_level_verify'] else '❌ 未启用'}
🔹 最低QQ等级：{group_config['min_qq_level']} 级
🔹 入群验证延时：{group_config['verify_delay']} 秒

💡 配置来源：{'群级别配置' if any(str(cfg.get('group_id')) == str(gid) for cfg in self.group_configs) else '全局默认配置'}
        """
        
        await event.bot.api.call_action("send_group_msg", group_id=gid, message=config_info)
        logger.info(f"[Geetest Verify] 群 {gid} 查看验证配置")
