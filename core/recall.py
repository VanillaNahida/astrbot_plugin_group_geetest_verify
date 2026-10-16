import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class VerificationMessageRound:
    key: tuple
    call_action: Callable
    message_ids: set = field(default_factory=set)
    closed: bool = False
    kicking: bool = False


class RecallMixin:
    """Track only bot-generated process messages for one verification round."""

    @staticmethod
    def _verification_client(event):
        bot = getattr(event, "bot", None)
        if callable(getattr(bot, "call_action", None)):
            return bot
        api = getattr(bot, "api", None)
        if callable(getattr(api, "call_action", None)):
            return api
        raise RuntimeError("event-bound OneBot API client is unavailable")

    def _verification_message_key(self, event, gid, uid):
        return id(self._verification_client(event)), int(gid), str(uid)

    def _find_verification_messages(self, event, gid, uid, *, any_bot=False):
        rounds = getattr(self, "_verification_messages", {})
        if not rounds or self._get_platform(event) != "aiocqhttp":
            return None
        existing = rounds.get(self._verification_message_key(event, gid, uid))
        if existing is not None or not any_bot:
            return existing
        # Pending state is shared by group/member; another bot may receive the
        # reply or admin command first. Keep the round's original sender.
        return next((item for item in rounds.values()
                     if item.key[-2:] == (int(gid), str(uid))), None)

    def _verification_message_round(self, event, gid, uid, group_config, *, any_bot=False):
        existing = self._find_verification_messages(event, gid, uid, any_bot=any_bot)
        if existing is not None:
            return existing
        if (self._get_platform(event) != "aiocqhttp"
                or not group_config.get("recall_verification_messages", False)):
            return None
        try:
            key = self._verification_message_key(event, gid, uid)
            call_action = self._verification_client(event).call_action
        except Exception as exc:
            logger.warning("Cannot track verification messages: %s", exc)
            return None
        if not hasattr(self, "_verification_messages"):
            self._verification_messages = {}
        message_round = VerificationMessageRound(key, call_action)
        self._verification_messages[key] = message_round
        return message_round

    async def _recall_verification_message(self, message_round, message_id):
        try:
            response = await message_round.call_action("delete_msg", message_id=message_id)
            if isinstance(response, dict) and (
                response.get("status") == "failed" or response.get("retcode", 0) != 0
            ):
                raise RuntimeError("delete_msg returned a failure response")
        except Exception as exc:
            logger.warning("Cannot recall verification message %s (%s): %s",
                           message_id, message_round.key, exc)

    async def _send_tracked_message(self, message_round, gid, message):
        if not message:
            return None
        try:
            return await message_round.call_action("send_group_msg", group_id=gid, message=message)
        except Exception as exc:
            logger.warning("Cannot send verification message (%s): %s", message_round.key, exc)
            return None

    async def _send_verification_message(self, event, gid, message, message_round):
        if message_round is None:
            return await self._send_group_message(event, gid, message)
        if message_round.closed:
            return None

        # A timer can be cancelled by success/retry while its send is in flight.
        # Keep the response so its message ID is still registered or recalled.
        sending = asyncio.create_task(self._send_tracked_message(message_round, gid, message))
        cancelled = False
        try:
            response = await asyncio.shield(sending)
        except asyncio.CancelledError:
            cancelled = True
            response = await sending

        message_id = None
        if isinstance(response, dict):
            message_id = response.get("message_id")
            if message_id is None and isinstance(response.get("data"), dict):
                message_id = response["data"].get("message_id")
        if isinstance(message_id, (int, str)) and not isinstance(message_id, bool) and message_id != "":
            if message_round.closed:
                await self._recall_verification_message(message_round, message_id)
            else:
                message_round.message_ids.add(message_id)
        elif message:
            logger.warning("Verification message has no message ID (%s)", message_round.key)
        if cancelled:
            raise asyncio.CancelledError
        return response

    async def _finish_verification_messages(self, message_round):
        if message_round is None:
            return
        message_round.closed = True
        rounds = self._verification_messages
        if rounds.get(message_round.key) is message_round:
            rounds.pop(message_round.key)
        message_ids = message_round.message_ids.copy()
        message_round.message_ids.clear()
        for message_id in message_ids:
            await self._recall_verification_message(message_round, message_id)

    async def _kick_verifying_member(self, event, gid, uid, message_round):
        # A synchronous kick notice must not cancel the task that still owes the
        # group its final result. That task owns state cleanup after a good kick.
        if message_round is not None:
            message_round.kicking = True
        try:
            if message_round is None:
                return await self._kick_member(event, gid, uid)
            response = await message_round.call_action(
                "set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
            if isinstance(response, dict) and (
                response.get("status") == "failed" or response.get("retcode", 0) != 0
            ):
                raise RuntimeError("set_group_kick returned a failure response")
            return response
        except BaseException:
            if message_round is not None:
                message_round.kicking = False
            raise
