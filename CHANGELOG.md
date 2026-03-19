# 更新日志 (CHANGELOG)

## [v1.2.4] fix: 修复WebUI配置无法保存的bug

* 修复WebUI配置无法保存的bug

<details>
<summary>📋 点击查看历史更新日志</summary>

# 历史更新

## v1.2.3

- 添加了之前忘记写的插件初始化和卸载钩子相关代码 

- 优化配置项，添加命令“设置踢出延迟”

- 在相关命令逻辑后加上 `event.stop_event()` 以便终止事件传播，避免请求 LLM 和执行其它插件的 Handler [#5](https://github.com/VanillaNahida/astrbot_plugin_group_geetest_verify/issues/5)

- 代码格式优化

- 移除未使用的类型注解和冗余代码

## v1.2.2

- 添加群级别配置项"是否撤回未验证用户的非验证码消息" `(recall_unverified_messages)`
  - 支持撤回未验证用户发送的非验证码消息
  - 可为每个群独立配置
  - 默认关闭

- 添加群级别配置项“是否提示用户完成验证” `(prompt_unverified_user)`
  - 开启时：用户发送非验证码消息会收到验证提示，不增加错误计数
  - 关闭时：用户发送非验证码消息会增加错误计数，达到最大次数后踢出用户
  - 默认开启

- 添加错误提示功能
  - 当关闭"提示用户完成验证"时，用户发送非验证码消息会收到简洁的错误提示
  - 提示内容包括剩余尝试次数

</details>