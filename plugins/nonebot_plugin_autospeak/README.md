<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>


# nonebot-plugin-autospeak

NoneBot2 定时自动发言插件。可以设置任务，让机器人按指定时间自动发送消息，支持群聊和私聊。

## 安装

使用 NB-CLI 安装：

```bash
nb plugin install nonebot-plugin-autospeak
```

或使用 pip：

```bash
pip install nonebot-plugin-autospeak
```

## 功能

- 定时循环发送：按每天或指定星期几发送
- 一次性任务：指定年月日时分，触发一次后自动删除
- 多条消息随机发送：同一任务可配置多条消息，每次随机取一条
- 图文混排：配置任务时直接发送图片，自动保存并在发送时带上
- 预设占位符：消息内容可包含日期、时间、倒计时、图片等占位符，发送时自动替换
- 任务管理指令：添加、删除、修改、查看任务
- 只允许 SUPERUSER 使用

## 依赖

- nonebot2
- nonebot-adapter-onebot（OneBot v11）
- nonebot-plugin-apscheduler
- nonebot-plugin-localstore

## 配置项

插件零配置即可使用，以下配置项均可选：

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `autospeak_command_priority` | int | `10` | `autospk` 指令的响应优先级，数值越小越优先 |

通过 `.env` 文件或环境变量设置，如：

```dotenv
AUTOSPEAK_COMMAND_PRIORITY=10
```

## 存储路径

配置与图片由 `nonebot-plugin-localstore` 管理：

- 配置文件：`<localstore 配置目录>/nonebot_plugin_autospeak/config.json`
- 图片目录：`<localstore 数据目录>/nonebot_plugin_autospeak/images/`

可通过 `nb localstore` 命令查看实际路径。旧版本使用的 `data/autospeak/` 目录会在插件加载时自动迁移。

## 指令

所有指令仅 SUPERUSER 可用。

### 总开关

```
autospk on       开启自动发言
autospk off      关闭自动发言
autospk reload   重新加载配置
```

### 添加循环任务

```
autospk add <group|private> <目标> <HH:MM> <消息1>|<消息2>|... [days=...]
```

- 目标：群聊用群号或 `here`（当前群），私聊用 QQ 号或 `me`（自己）
- 时间：24 小时制，如 `09:00`、`21:30`
- 多条消息用 `|` 分隔，发送时随机取一条
- `days=` 指定星期几，不写则每天发送
- 消息内容可直接附带图片，插件自动保存到图片目录并在发送时带上

示例：

```
autospk add group here 09:00 早上好|大家早上好|起床啦
autospk add group here 09:00 早上好，上班啦 days=workday
autospk add group here 09:00 早上好 days=1,3,5
autospk add group 123456 21:00 晚安 days=mon,tue,wed,thu,fri
```

`days=` 支持的值：

| 写法 | 含义 |
|---|---|
| 不写 / `*` / `all` / `everyday` | 每天 |
| `workday` / `wd` | 工作日，周一至周五 |
| `1,3,5` | 数字 1-7，1 是周一，7 是周日 |
| `mon,tue,wed` | 英文缩写或全称 |

### 添加一次性任务

```
autospk addonce <group|private> <目标> <YYYY-MM-DD> <HH:MM> <消息>
```

示例：

```
autospk addonce group here 2026-12-31 23:59 新年快乐
```

到点触发一次，触发后任务自动删除。

### 查看与删除

```
autospk list         列出所有任务
autospk del <任务ID>  删除任务
```

任务 ID 在 `autospk list` 中查看。

### 修改任务

```
autospk edit time     <任务ID> <HH:MM>             修改循环任务时间
autospk edit datetime <任务ID> <YYYY-MM-DD> <HH:MM> 修改一次性任务时间
autospk edit msg      <任务ID> <消息1>|<消息2>      替换任务消息
```

### 占位符

消息内容支持以下占位符，发送时自动替换为实际内容：

| 占位符 | 说明 |
|---|---|
| `{date}` / `{date:格式}` | 当前日期，默认 YYYY-MM-DD |
| `{time}` / `{time:格式}` | 当前时间，默认 HH:MM:SS |
| `{datetime}` / `{datetime:格式}` | 当前日期时间 |
| `{weekday}` | 今天星期几 |
| `{days_until:日期}` | 距目标日期还有几天，未来为正数、过去为负数、当天为 0 |
| `{days_until_cn:日期}` | 中文描述，如"还有 7 天"、"就是今天" |
| `{image:路径\|URL\|文件名}` | 发送图片 |

日期和时间格式使用 strftime 语法，例如 `{date:%Y年%m月%d日}`。日期支持 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM[:SS]`。

图片占位符的用法：

- 配置任务时直接在消息里附上图片，插件自动保存，无需手写占位符
- 网络图片：`{image:https://example.com/a.png}`
- 本地文件：`{image:E:\Pictures\a.png}`
- 插件图片目录：把图片放到 `<localstore 数据目录>/nonebot_plugin_autospeak/images/` 下，用文件名引用，如 `{image:greeting.png}`
- CQ 码也可以直接写在消息里，原样发送

示例：

```
autospk add group here 09:00 距离高考还有 {days_until_cn:2026-06-07}
autospk add group here 09:00 今天是 {date:%Y年%m月%d日} {weekday}
autospk add group here 09:00 早安 {image:greeting.png}
```

### 预览

```
autospk preview <文本>    预览占位符渲染结果
autospk placeholders      查看占位符说明
```

## 测试

安装测试依赖后运行：

```bash
pip install -e .[test]
python -m pytest
```

## 配置示例

`config.json` 由插件自动生成和维护，一般无需手动修改。手动编辑后执行 `autospk reload` 生效。

```json
{
  "enabled": true,
  "next_id": 3,
  "tasks": [
    {
      "id": 1,
      "type": "group",
      "target_id": 123456,
      "time": "09:00",
      "messages": ["早上好", "大家早上好"],
      "weekdays": [0, 1, 2, 3, 4]
    },
    {
      "id": 2,
      "kind": "once",
      "type": "private",
      "target_id": 10001,
      "datetime": "2026-12-31 23:59",
      "messages": ["新年快乐"]
    }
  ]
}
```
