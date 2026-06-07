import json
import os
import logging

logger = logging.getLogger(__name__)

# 配置项名称列表，用于 _load_config 和 _save_config
_CONFIG_KEYS = [
    "verification_timeout", "kick_delay", "max_wrong_answers",
    "api_base_url", "api_key",
    "enable_geetest_verify", "enable_level_verify", "min_qq_level",
    "verify_delay", "error_verification",
    "recall_unverified_messages", "prompt_unverified_user",
    "new_member_prompt", "welcome_message", "welcome_image",
    "wrong_answer_prompt", "failure_message", "kick_message",
    "too_many_wrong_message", "too_many_wrong_kick_message",
    "wrong_code_message", "too_many_non_code_message",
    "geetest_new_member_prompt", "geetest_wrong_code_prompt",
    "level_no_info_message", "level_too_low_message", "level_pass_message",
    "timeout_reminder_geetest", "timeout_reminder_math",
]


class ConfigMixin:
    """配置管理相关方法"""

    def _load_config(self):
        """从配置文件 schema 和用户配置中加载所有配置项"""
        # 读取配置文件 schema 默认值
        package_root = os.path.dirname(os.path.dirname(__file__))
        schema_path = os.path.join(package_root, "_conf_schema.json")
        schema_defaults = {}
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
                for key, value in schema.items():
                    schema_defaults[key] = value.get("default")
        except Exception as e:
            logger.warning(f"[Geetest Verify] 读取配置 schema 失败: {e}")

        # 为每个配置项设置值，优先使用用户配置，否则使用 schema 默认值
        # 数值和布尔类型
        self.verification_timeout = self.config.get("verification_timeout", schema_defaults.get("verification_timeout", 300))
        self.kick_delay = self.config.get("kick_delay", schema_defaults.get("kick_delay", 5))
        self.max_wrong_answers = self.config.get("max_wrong_answers", schema_defaults.get("max_wrong_answers", 5))
        self.enable_geetest_verify = self.config.get("enable_geetest_verify", schema_defaults.get("enable_geetest_verify", False))
        self.enable_level_verify = self.config.get("enable_level_verify", schema_defaults.get("enable_level_verify", False))
        self.min_qq_level = self.config.get("min_qq_level", schema_defaults.get("min_qq_level", 20))
        self.verify_delay = self.config.get("verify_delay", schema_defaults.get("verify_delay", 0))
        self.recall_unverified_messages = self.config.get("recall_unverified_messages", schema_defaults.get("recall_unverified_messages", False))
        self.prompt_unverified_user = self.config.get("prompt_unverified_user", schema_defaults.get("prompt_unverified_user", True))

        # 字符串类型
        self.api_base_url = self.config.get("api_base_url", schema_defaults.get("api_base_url", ""))
        self.api_key = self.config.get("api_key", schema_defaults.get("api_key", ""))
        self.error_verification = self.config.get("error_verification", schema_defaults.get("error_verification",
            "{at_user} 你还未完成验证。请在 {timeout} 分钟内输入验证码以完成验证"))
        self.new_member_prompt = self.config.get("new_member_prompt", schema_defaults.get("new_member_prompt",
            "{at_user} 欢迎加入本群！请在 {timeout} 分钟内回答下面的问题以完成验证：\n{question}\n注意：请直接发送计算结果，无需其他文字。"))
        self.welcome_message = self.config.get("welcome_message", schema_defaults.get("welcome_message",
            "{at_user} 验证成功，欢迎你的加入！"))
        self.welcome_image = self.config.get("welcome_image", schema_defaults.get("welcome_image", ""))
        self.wrong_answer_prompt = self.config.get("wrong_answer_prompt", schema_defaults.get("wrong_answer_prompt",
            "{at_user} 答案错误，请重新回答验证。这是你的新问题：\n{question}\n剩余尝试次数：{remaining}"))
        self.failure_message = self.config.get("failure_message", schema_defaults.get("failure_message",
            "{at_user} 验证超时，你将在 {countdown} 秒后被请出本群。"))
        self.kick_message = self.config.get("kick_message", schema_defaults.get("kick_message",
            "{at_user} 因未在规定时间内完成验证，已被请出本群。"))
        self.too_many_wrong_message = self.config.get("too_many_wrong_message", schema_defaults.get("too_many_wrong_message",
            "{at_user} 很抱歉，你已连续回答错误 {count} 次，将被请出本群。"))
        self.too_many_wrong_kick_message = self.config.get("too_many_wrong_kick_message", schema_defaults.get("too_many_wrong_kick_message",
            "{at_user} 因回答错误次数过多，已被请出本群。"))
        self.wrong_code_message = self.config.get("wrong_code_message", schema_defaults.get("wrong_code_message",
            "{at_user} 验证码错误！"))
        self.too_many_non_code_message = self.config.get("too_many_non_code_message", schema_defaults.get("too_many_non_code_message",
            "{at_user} 很抱歉，你已连续发送非验证码消息达到 {count} 次，将被请出本群。"))
        self.geetest_new_member_prompt = self.config.get("geetest_new_member_prompt", schema_defaults.get("geetest_new_member_prompt",
            "{at_user} 欢迎加入本群！请在 {timeout} 分钟内复制下方链接前往浏览器完成人机验证：\n{url}\n验证完成后，请在群内发送六位数验证码。"))
        self.geetest_wrong_code_prompt = self.config.get("geetest_wrong_code_prompt", schema_defaults.get("geetest_wrong_code_prompt",
            "{at_user} 验证码错误，请重新复制下方链接前往浏览器完成人机验证：\n{url}\n验证完成后，请在群内发送六位数验证码。\n您的剩余尝试次数：{remaining}"))
        self.level_no_info_message = self.config.get("level_no_info_message", schema_defaults.get("level_no_info_message",
            "{at_user} 未查询到您的QQ等级信息，请检查是否在隐私设置内开启等级显示，为了安全起见，将自动进入验证流程。"))
        self.level_too_low_message = self.config.get("level_too_low_message", schema_defaults.get("level_too_low_message",
            "{at_user} 您的QQ等级为 {qq_level}，低于最低等级要求 {min_level}级，将进入验证流程。"))
        self.level_pass_message = self.config.get("level_pass_message", schema_defaults.get("level_pass_message",
            "{at_user} 您的QQ等级为 {qq_level}，大于等于最低等级要求 {min_level}级，已跳过验证流程。\n欢迎你的加入！"))
        self.timeout_reminder_geetest = self.config.get("timeout_reminder_geetest", schema_defaults.get("timeout_reminder_geetest",
            "{at_user} 验证剩余最后 1 分钟，请尽快完成验证！\n请复制下方链接前往浏览器完成人机验证，之前的链接可能已失效，请使用新链接完成验证：\n{url}\n验证完成后，请在群内发送六位数验证码。"))
        self.timeout_reminder_math = self.config.get("timeout_reminder_math", schema_defaults.get("timeout_reminder_math",
            "{at_user} 验证剩余最后 1 分钟，请尽快完成验证！\n请回答数学题：{question}"))

        # 群级别配置列表
        self.group_configs = self.config.get("group_configs", [])

    def _save_config(self):
        """保存配置到磁盘"""
        try:
            # 更新配置字典
            self.config["verification_timeout"] = self.verification_timeout
            self.config["kick_delay"] = self.kick_delay
            self.config["max_wrong_answers"] = self.max_wrong_answers
            self.config["api_base_url"] = self.api_base_url
            self.config["api_key"] = self.api_key
            self.config["enable_geetest_verify"] = self.enable_geetest_verify
            self.config["enable_level_verify"] = self.enable_level_verify
            self.config["min_qq_level"] = self.min_qq_level
            self.config["verify_delay"] = self.verify_delay
            self.config["error_verification"] = self.error_verification
            self.config["recall_unverified_messages"] = self.recall_unverified_messages
            self.config["prompt_unverified_user"] = self.prompt_unverified_user
            self.config["new_member_prompt"] = self.new_member_prompt
            self.config["welcome_message"] = self.welcome_message
            self.config["welcome_image"] = self.welcome_image
            self.config["wrong_answer_prompt"] = self.wrong_answer_prompt
            self.config["failure_message"] = self.failure_message
            self.config["kick_message"] = self.kick_message
            self.config["too_many_wrong_message"] = self.too_many_wrong_message
            self.config["too_many_wrong_kick_message"] = self.too_many_wrong_kick_message
            self.config["wrong_code_message"] = self.wrong_code_message
            self.config["too_many_non_code_message"] = self.too_many_non_code_message
            self.config["geetest_new_member_prompt"] = self.geetest_new_member_prompt
            self.config["geetest_wrong_code_prompt"] = self.geetest_wrong_code_prompt
            self.config["level_no_info_message"] = self.level_no_info_message
            self.config["level_too_low_message"] = self.level_too_low_message
            self.config["level_pass_message"] = self.level_pass_message
            self.config["timeout_reminder_geetest"] = self.timeout_reminder_geetest
            self.config["timeout_reminder_math"] = self.timeout_reminder_math
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
            group_config = {
                "__template_key": "default_config",
                "group_id": gid,
                "enabled": False,
                "verification_timeout": self.verification_timeout,
                "kick_delay": self.kick_delay,
                "max_wrong_answers": self.max_wrong_answers,
                "enable_geetest_verify": self.enable_geetest_verify,
                "enable_level_verify": self.enable_level_verify,
                "min_qq_level": self.min_qq_level,
                "verify_delay": self.verify_delay,
                "recall_unverified_messages": self.recall_unverified_messages,
                "prompt_unverified_user": self.prompt_unverified_user,
                "welcome_image": self.welcome_image
            }
            self.group_configs.append(group_config)

        # 更新配置项
        for key, value in kwargs.items():
            group_config[key] = value

        # 确保配置项完整
        required_fields = ["__template_key", "group_id", "enabled", "verification_timeout",
                          "kick_delay", "max_wrong_answers", "enable_geetest_verify", "enable_level_verify",
                          "min_qq_level", "verify_delay", "recall_unverified_messages", "prompt_unverified_user",
                          "welcome_image"]

        for field in required_fields:
            if field not in group_config:
                if field == "__template_key":
                    group_config[field] = "default_config"
                elif field == "enabled":
                    group_config[field] = False
                elif field == "verification_timeout":
                    group_config[field] = self.verification_timeout
                elif field == "kick_delay":
                    group_config[field] = self.kick_delay
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
                elif field == "recall_unverified_messages":
                    group_config[field] = self.recall_unverified_messages
                elif field == "prompt_unverified_user":
                    group_config[field] = self.prompt_unverified_user
                elif field == "welcome_image":
                    group_config[field] = self.welcome_image

        # 保存配置
        self._save_config()

    def _get_group_config(self, gid: int) -> dict:
        """获取特定群的配置，如果没有群级别配置则返回默认配置"""
        for group_config in self.group_configs:
            if str(group_config.get("group_id")) == str(gid):
                return {
                    "enabled": group_config.get("enabled", False),
                    "verification_timeout": group_config.get("verification_timeout", self.verification_timeout),
                    "kick_delay": group_config.get("kick_delay", self.kick_delay),
                    "max_wrong_answers": group_config.get("max_wrong_answers", self.max_wrong_answers),
                    "enable_geetest_verify": group_config.get("enable_geetest_verify", self.enable_geetest_verify),
                    "enable_level_verify": group_config.get("enable_level_verify", self.enable_level_verify),
                    "min_qq_level": group_config.get("min_qq_level", self.min_qq_level),
                    "verify_delay": group_config.get("verify_delay", self.verify_delay),
                    "error_verification": group_config.get("error_verification", self.error_verification),
                    "recall_unverified_messages": group_config.get("recall_unverified_messages", self.recall_unverified_messages),
                    "prompt_unverified_user": group_config.get("prompt_unverified_user", self.prompt_unverified_user),
                    "welcome_image": group_config.get("welcome_image", self.welcome_image)
                }

        return {
            "enabled": False,
            "verification_timeout": self.verification_timeout,
            "kick_delay": self.kick_delay,
            "max_wrong_answers": self.max_wrong_answers,
            "enable_geetest_verify": self.enable_geetest_verify,
            "enable_level_verify": self.enable_level_verify,
            "min_qq_level": self.min_qq_level,
            "verify_delay": self.verify_delay,
            "error_verification": self.error_verification,
            "recall_unverified_messages": self.recall_unverified_messages,
            "prompt_unverified_user": self.prompt_unverified_user,
            "welcome_image": self.welcome_image
        }

    async def _sync_config_to_db(self):
        """同步配置到数据库中待验证的记录"""
        updated = 0
        for key in self.db.all_keys():
            state = self.db.get_cached(key)
            if not state or state.get("status") != "pending":
                continue
            parts = key.split(":")
            if len(parts) == 2:
                try:
                    gid = int(parts[0])
                except (ValueError, TypeError):
                    continue
                group_config = self._get_group_config(gid)
                await self.db.update_field(key, "max_wrong_answers", group_config["max_wrong_answers"])
                updated += 1
        if updated > 0:
            logger.info(f"[Geetest Verify] 已同步配置到 {updated} 条待验证记录")
