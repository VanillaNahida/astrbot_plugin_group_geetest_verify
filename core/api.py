import logging
from urllib.parse import urlparse
import aiohttp

from astrbot.core.config.default import VERSION

logger = logging.getLogger(__name__)

PLUGIN_VERSION = "1.3.4"


class GeetestAPIMixin:
    """极验验证 API 调用相关方法"""

    def _normalize_base_url(self) -> str:
        """去除 api_base_url 末尾的斜杠，避免拼接时出现双斜杠"""
        return (self.api_base_url or "").rstrip("/")

    async def _create_geetest_verify(self, gid: int, uid: str) -> str:
        """调用极验 API 生成验证链接，返回完整可用的验证 URL"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return None

        base_url = self._normalize_base_url()
        url = f"{base_url}/verify/create"
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
                    logger.info(f"[Geetest Verify] 创建验证响应: {result}")
                    if result.get("code") == 0:
                        full_url = result.get("data", {}).get("url")
                        if not full_url:
                            logger.error("[Geetest Verify] API 返回的验证链接为空")
                            return None

                        # 如果服务端返回的是相对路径，则拼接 base_url
                        parsed = urlparse(full_url)
                        if not parsed.scheme or not parsed.netloc:
                            # 相对路径，保留 path + query + fragment
                            suffix = parsed.path
                            if parsed.query:
                                suffix += "?" + parsed.query
                            if parsed.fragment:
                                suffix += "#" + parsed.fragment
                            full_url = f"{base_url}{suffix}"

                        logger.info(f"[Geetest Verify] 成功生成验证链接: {full_url}")
                        return full_url
                    else:
                        logger.error(f"[Geetest Verify] API 返回错误: {result.get('msg')}")
                        return None
                else:
                    body = await response.text()
                    logger.error(f"[Geetest Verify] API 请求失败，状态码: {response.status}, 响应: {body}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"[Geetest Verify] API 请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"[Geetest Verify] 生成验证链接异常: {e}", exc_info=True)
            return None

    async def _check_geetest_verify(self, gid: int, uid: str, code: str) -> bool:
        """调用极验 API 验证验证码"""
        if not self.api_key:
            logger.error("[Geetest Verify] API 密钥未配置")
            return False

        base_url = self._normalize_base_url()
        url = f"{base_url}/verify/check"
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
                    logger.info(f"[Geetest Verify] 校验验证码响应: {result}")
                    # 兼容两种响应格式：
                    # 1. {code: 0, passed: true/false, msg: "..."}
                    # 2. {code: 0, data: {passed: true/false, msg: "..."}}
                    passed = result.get("passed")
                    if passed is None and isinstance(result.get("data"), dict):
                        passed = result["data"].get("passed")
                    msg = result.get("msg") or (result.get("data") or {}).get("msg")

                    if result.get("code") == 0 and passed:
                        logger.info("[Geetest Verify] 验证码验证成功")
                        return True
                    else:
                        logger.info(f"[Geetest Verify] 验证码验证失败: code={result.get('code')}, passed={passed}, msg={msg}")
                        return False
                else:
                    body = await response.text()
                    logger.error(f"[Geetest Verify] API 请求失败，状态码: {response.status}, 响应: {body}")
                    return False
        except aiohttp.ClientError as e:
            logger.error(f"[Geetest Verify] API 请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"[Geetest Verify] 验证验证码异常: {e}", exc_info=True)
            return False
