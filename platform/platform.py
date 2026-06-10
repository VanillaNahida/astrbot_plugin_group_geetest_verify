import os
import logging
from ..core.api import GeetestAPIMixin

logger = logging.getLogger(__name__)


class PlatformMixin(GeetestAPIMixin):
    """平台抽象层：平台检测、原始消息解析、消息发送、踢人、图片路径解析"""

    def _get_platform(self, event) -> str:
        """获取事件所属的平台"""
        return event.get_platform_name()

    def _get_raw_value(self, raw, key: str, default=None):
        """安全地从 raw_message 中获取值，兼容字典和 Telegram Update 对象"""
        if isinstance(raw, dict):
            return raw.get(key, default)
        else:
            return getattr(raw, key, default)

    def _get_raw_dict(self, raw) -> dict:
        """将 raw_message 转换为字典格式"""
        if isinstance(raw, dict):
            return raw
        else:
            try:
                return vars(raw)
            except Exception:
                return {}

    def _get_group_id(self, platform: str, raw) -> int:
        """安全地获取群组 ID"""
        if platform == "telegram":
            chat = self._get_raw_value(raw, "chat") or {}
            if chat:
                chat_id = self._get_raw_value(chat, "id")
                if chat_id:
                    logger.debug(f"[Geetest Verify] 从 chat 获取到群组 ID: {chat_id}")
                    return int(chat_id)

            message = self._get_raw_value(raw, "message") or {}
            if message:
                message_chat = self._get_raw_value(message, "chat") or {}
                if message_chat:
                    chat_id = self._get_raw_value(message_chat, "id")
                    if chat_id:
                        logger.debug(f"[Geetest Verify] 从 message.chat 获取到群组 ID: {chat_id}")
                        return int(chat_id)

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
            group_id = self._get_raw_value(raw, "group_id")
            if group_id:
                logger.debug(f"[Geetest Verify] 获取到 QQ 群组 ID: {group_id}")
                return int(group_id)
            logger.warning("[Geetest Verify] 无法从 QQ 消息中获取群组 ID")
            return None

    def _format_user_mention(self, event, uid: str) -> str:
        """根据平台格式化用户提及"""
        platform = self._get_platform(event)
        if platform == "telegram":
            raw = event.message_obj.raw_message
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
            return f"[CQ:at,qq={uid}]"

    async def _send_group_message(self, event, gid: int, message: str):
        """根据平台发送群消息。如果 message 为空则不发送。"""
        if not message:
            return
        platform = self._get_platform(event)
        try:
            platform_client = self.context.get_platform(platform).get_client()

            if platform == "telegram":
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_message", chat_id=gid, text=message, parse_mode="Markdown")
                else:
                    await platform_client.send_message(chat_id=gid, text=message, parse_mode="Markdown")
            else:
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("send_group_msg", group_id=gid, message=message)
                elif hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_group_msg", group_id=gid, message=message)
        except Exception as e:
            logger.error(f"[Geetest Verify] 发送消息失败: {e}")

    def _resolve_image_path(self, image_path: str) -> str:
        """解析图片路径，支持 URL、绝对路径和相对路径"""
        if not image_path:
            return ""
        if image_path.lower().startswith(("http://", "https://")):
            return image_path
        if os.path.isabs(image_path):
            return image_path
        resolved = str(self._data_dir / image_path)
        logger.info(f"[Geetest Verify] 解析相对路径图片: {image_path} -> {resolved}")
        return resolved

    async def _send_group_message_with_image(self, event, gid: int, text: str, image_path: str = None):
        """发送群消息，附带图片。如果 text 和 image_path 都为空则不发送。"""
        if not text and not image_path:
            return
        if not image_path:
            return await self._send_group_message(event, gid, text)

        resolved_path = self._resolve_image_path(image_path)
        if not resolved_path:
            return await self._send_group_message(event, gid, text)

        platform = self._get_platform(event)
        try:
            platform_client = self.context.get_platform(platform).get_client()

            if platform == "telegram":
                if hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_photo", chat_id=gid, photo=resolved_path, caption=text)
                else:
                    await platform_client.send_photo(chat_id=gid, photo=resolved_path, caption=text)
            else:
                message_with_image = f"{text}\n[CQ:image,file={resolved_path}]"
                if hasattr(platform_client, "api"):
                    await platform_client.api.call_action("send_group_msg", group_id=gid, message=message_with_image)
                elif hasattr(platform_client, "call_action"):
                    await platform_client.call_action("send_group_msg", group_id=gid, message=message_with_image)
        except Exception as e:
            logger.error(f"[Geetest Verify] 发送带图片消息失败: {e}")
            await self._send_group_message(event, gid, text)

    async def _kick_member(self, event, gid: int, uid: str):
        """根据平台踢出成员"""
        platform = self._get_platform(event)
        platform_client = self.context.get_platform(platform).get_client()

        if platform == "telegram":
            if hasattr(platform_client, "call_action"):
                await platform_client.call_action("kickChatMember", chat_id=gid, user_id=int(uid))
            else:
                await platform_client.kick_chat_member(chat_id=gid, user_id=int(uid))
        else:
            if hasattr(platform_client, "api"):
                await platform_client.api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
            elif hasattr(platform_client, "call_action"):
                await platform_client.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)

    async def _get_user_info(self, event, uid: str) -> dict:
        """根据平台获取用户信息"""
        platform = self._get_platform(event)
        if platform == "telegram":
            try:
                chat_member = await event.bot.api.call_action("getChatMember", chat_id=event.message_obj.raw_message.get("chat", {}).get("id"), user_id=int(uid))
                return chat_member.get("user", {})
            except Exception:
                return {}
        else:
            try:
                user_info = await self.context.get_platform("aiocqhttp").get_client().api.call_action("get_stranger_info", user_id=int(uid))
                return user_info
            except Exception:
                return {}
