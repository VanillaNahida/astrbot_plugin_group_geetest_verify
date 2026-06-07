import logging
from urllib.parse import urlparse
import aiohttp

from astrbot.core.config.default import VERSION

logger = logging.getLogger(__name__)

PLUGIN_VERSION = "1.3.0"


class GeetestAPIMixin:
    """极验验证 API 调用相关方法"""

    async def _create_geetest_verify(self, gid: int, uid: str) -> str:
        """调用极验 API 生成验证链接，返回路径部分"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return None

        url = f"{self.api_base_url}/verify/create"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"AstrBot/v{VERSION} group_geetest_verify/v{PLUGIN_VERSION}"
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
            "User-Agent": f"AstrBot/v{VERSION} group_geetest_verify/v{PLUGIN_VERSION}"
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
