# Group-Geetest-Verify
一个AstrBot的入群验证码插件，使用极验Geetest V4验证，有效防止机器人入群。

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
请加群 [195260107](https://qm.qq.com/q/1od5TMYrKE) 联系开发者，获取验证后端的 URL 和 API Key。

### 插件配置
1. 在插件市场搜索插件 `astrbot_plugin_group_geetest_verify` 或 `入群网页验证插件`
2. 安装插件
3. 配置插件
    1. 在WebUI中填写你获得的验证后端地址和API Key
    2. 配置入群验证的相关参数，如验证超时时间、验证失败后的操作等。
4. 保存重载插件配置，使插件生效。

# 命令

| 命令 | 用法 | 权限要求 | 说明 |
|------|------|----------|------|
| `/重新验证` | `/重新验证 @用户` 或 `/重新验证 从未发言的人` | 群主/管理员/Bot管理员 | 强制指定用户重新验证。可以@单个用户，或使用"从未发言的人"为所有未验证且未发言的用户启动验证 |
| `/绕过验证` | `/绕过验证 @用户` | 群主/管理员/Bot管理员 | 让指定用户绕过验证，该用户入群时将不再需要验证 |
| `/开启验证` | `/开启验证` | 群主/管理员/Bot管理员 | 开启当前群的入群验证功能 |
| `/关闭验证` | `/关闭验证` | 群主/管理员/Bot管理员 | 关闭当前群的入群验证功能 |
| `/查看验证配置` | `/查看验证配置` | 群主/管理员/Bot管理员 | 查看当前群的验证配置信息 |
| `/设置验证超时时间` | `/设置验证超时时间 秒数` | 群主/管理员/Bot管理员 | 设置当前群的验证超时时间（秒），超时未验证的用户将被踢出群 |
| `/开启等级验证` | `/开启等级验证` | 群主/管理员/Bot管理员 | 开启当前群的等级验证功能，QQ等级达到最低等级的用户将自动跳过验证 |
| `/关闭等级验证` | `/关闭等级验证` | 群主/管理员/Bot管理员 | 关闭当前群的等级验证功能 |
| `/设置最低验证等级` | `/设置最低验证等级 等级数` | 群主/管理员/Bot管理员 | 设置当前群的最低验证等级（0-64），QQ等级大于等于此等级的用户将自动跳过验证 |

# 致谢
- [@yjwmidc](https://github.com/yjwmidc/) 验证后端贡献者
- [astrbot_plugin_Group-Verification_PRO](https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO) 参考该代码实现的入群验证插件，感谢该项目作者。

# bug反馈
如果在使用过程中遇到任何问题，请通过以下方式反馈：
- [Issue](https://github.com/VanillaNahida/Group-Geetest-Verify/issues)
- QQ群：[195260107](https://qm.qq.com/q/1od5TMYrKE)

# QQ群：
 - 一群：621457510
 - 二群：1031065631
 - 三群：195260107 （推荐）
 - 四群：1074471035

**Star History**

[![Star History Chart](https://api.star-history.com/svg?repos=VanillaNahida/Group-Geetest-Verify&type=Date)](https://star-history.com/#VanillaNahida/Group-Geetest-Verify&Date)
