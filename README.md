# Group-Geetest-Verify
一个AstrBot的入群验证码插件，使用极验Geetest V4验证，有效防止机器人入群。仅支持aiocqhttp

![Group-Geetest-Verify](https://socialify.git.ci/VanillaNahida/astrbot_plugin_group_geetest_verify/image?description=1&font=KoHo&forks=1&issues=1&language=1&name=1&owner=1&pattern=Circuit%20Board&pulls=1&stargazers=1&theme=Auto)

<div align="center">
  
  [![GitHub license](https://img.shields.io/github/license/VanillaNahida/astrbot_plugin_group_geetest_verify?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify/blob/main/LICENSE)
  [![GitHub stars](https://img.shields.io/github/stars/VanillaNahida/astrbot_plugin_group_geetest_verify?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/VanillaNahida/astrbot_plugin_group_geetest_verify?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify/network)
  [![GitHub issues](https://img.shields.io/github/issues/VanillaNahida/astrbot_plugin_group_geetest_verify?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify/issues)
  [![python3](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://www.python.org/)
  [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-brightgreen.svg?style=flat-square)]()
  
</div>

<p align="center">
  <img src="logo.png" alt="Group-Geetest-Verify Logo">
</p>

# 效果展示

<p align="center">
  <img src="img/1.jpg" width="300">
</p>

# 使用方法

  > [!WARNING]
  >
  > 请确保您的AstrBot版本号 ≥ `v4.10.6` ，插件已在该版本上测试通过，我们不对低版本AstrBot使用此插件由此导致的问题负责。

## 方案一：本地部署后端服务

### 前置条件
1. 一台有公网IP的服务器
2. 一个不要钱的域名，用来托管验证后端服务
3. 安装了PHP 8.4的服务器，可使用[宝塔面板](https://www.bt.cn/)按照文档安装

### 部署后端
请查看[安装步骤](https://github.com/VanillaNahida/group-verify-service#%E5%AE%89%E8%A3%85%E6%AD%A5%E9%AA%A4)

### 插件安装与配置
1. 在插件市场搜索插件 `astrbot_plugin_group_geetest_verify` 或 `入群网页验证插件`
2. 安装插件（可以在插件市场安装，或者复制仓库地址，在WebUI中粘贴地址安装）
3. 配置插件
    1. 登录极验Geetest官网，注册账号并创建一个新的Geetest V4项目
    2. 按照[文档](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify#%E5%AE%89%E8%A3%85%E6%AD%A5%E9%AA%A4)部署验证后端服务，按照文档配置好Geetest的ID和Key并启动。
    3. 在插件配置中填写验证后端服务的相关信息，包括`验证后端地址`、`API Key`等（API Key不会自动生成，请自行填写）
    4. 配置入群验证的相关参数，如验证超时时间、验证失败后的操作等。
4. 保存重载插件配置，使插件生效。

## 方案二：使用开发者部署好的服务

如果您没有自己的公网服务器和域名，也可以使用开发者部署好的服务。

### 获取后端地址和API Key
请加群 [195260107](https://qm.qq.com/q/1od5TMYrKE) 获取验证后端的 URL 和 API Key。  
**在群内发送“/申请密钥”命令，bot会自动发送密钥到你的QQ邮箱**  
若需要自定义接收密钥的邮箱，请使用这个命令：“/申请密钥 example@example.com”，将 `example@example.com` 替换为你自己的邮箱
如果签发失败，请直接私聊我，说明来意即可，看到了就会回复。

### 插件配置
1. 在插件市场搜索插件 `astrbot_plugin_group_geetest_verify` 或 `入群网页验证插件`
2. 安装插件
3. 配置插件
    1. 在WebUI中填写你获得的验证后端地址和API Key
    2. 配置入群验证的相关参数，如验证超时时间、验证失败后的操作等。
4. 保存重载插件配置，使插件生效。

  > [!TIP]
  >
  > 安装并配置好插件后建议**重启bot**，确保插件生效。  
  > 如果遇到了什么奇奇怪怪的bug，可以试试重新安装插件，或者删除配置重新初始化插件。

# 验证过程消息撤回

在插件设置页面的全局默认配置或对应群配置中，开启 **验证结束后撤回过程消息**（`recall_verification_messages`）。默认关闭，仅支持 QQ/OneBot；群配置可单独覆盖全局设置。

验证成功、超时踢出、错误次数达到上限、管理员绕过、强制重新验证或成员离群时，清理这一轮机器人发送的等级提示、链接或数学题、错误提醒、最后一分钟提醒及踢出预告。错误后刷新链接仍属于同一轮，直到验证结束才统一清理。

保留验证成功通知及欢迎图片、等级达标免验证通知、绕过通知、实际踢出后的最终通知，以及管理员命令回执。用户自己发送的验证码和聊天消息不受此开关影响；已有的 `recall_unverified_messages` 继续独立控制未验证用户的非验证码发言。

仅记录启用后本次插件运行期间发送的消息 ID，不扫描群历史，异常重启前的记录不恢复；已记录的轮次会继续完成清理。平台拒绝撤回或未返回消息 ID 时会记录日志，不影响验证和踢人操作。踢人失败时保留待验证状态，不发送“已被请出”通知。

QQ 实机验收可使用测试群：分别完成一次验证成功和一次超时踢出，确认过程提示消失、最终结果通知和用户验证码保留；再关闭开关重复验证，确认过程消息保留。

# 命令总览

| 命令 | 示例用法 | 权限要求 | 说明 |
|------|------|----------|------|
| `/重新验证` | `/重新验证 @用户` | 群主/管理员/Bot管理员 | 强制指定用户重新验证。需要@需要重新验证的用户 |
| `/绕过验证` | `/绕过验证 @用户` | 群主/管理员/Bot管理员 | 让指定用户绕过验证，该用户入群时将不再需要验证 |
| `/开启验证` | `/开启验证` | 群主/管理员/Bot管理员 | 开启当前群的入群验证功能 |
| `/关闭验证` | `/关闭验证` | 群主/管理员/Bot管理员 | 关闭当前群的入群验证功能 |
| `/查看验证配置` | `/查看验证配置` | 群主/管理员/Bot管理员 | 查看当前群的验证配置信息 |
| `/设置验证超时时间` | `/设置验证超时时间 秒数` | 群主/管理员/Bot管理员 | 设置当前群的验证超时时间（秒），超时未验证的用户将被踢出群 |
| `/开启等级验证` | `/开启等级验证` | 群主/管理员/Bot管理员 | 开启当前群的等级验证功能，QQ等级达到最低等级的用户将自动跳过验证 |
| `/关闭等级验证` | `/关闭等级验证` | 群主/管理员/Bot管理员 | 关闭当前群的等级验证功能 |
| `/设置最低验证等级` | `/设置最低验证等级 等级数` | 群主/管理员/Bot管理员 | 设置当前群的最低验证等级（0-64），QQ等级大于等于此等级的用户将自动跳过验证 |
| `/设置踢出延迟` | `/设置踢出延迟 3` | 群主/管理员/Bot管理员 | 设置当前群的踢出延迟时间（秒），用户验证失败后将在延迟时间后被踢出群 |

# 致谢
- [@yjwmidc](https://github.com/yjwmidc) 验证后端贡献者
- [@makotowu](https://github.com/makotowu) 负责验证后端的部署和前后端重构工作，为本项目提供公益验证服务
- [astrbot_plugin_Group-Verification_PRO](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO) 参考该代码实现的入群验证插件，感谢该项目作者。

# bug反馈
如果在使用过程中遇到任何问题，欢迎你通过以下方式反馈：
- [Issue](https://github.com/VanillaNahida/Group-Geetest-Verify/issues)
- QQ群：[195260107](https://qm.qq.com/q/1od5TMYrKE) （处理最快，预计一周内解决）

# QQ群：
 - 一群：621457510
 - 二群：1031065631
 - 三群：195260107 （推荐）
 - 四群：1074471035

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=VanillaNahida/Group-Geetest-Verify&type=Date)](https://star-history.com/#VanillaNahida/Group-Geetest-Verify&Date)
