# 我的 QQ 机器人

## 功能与使用

所有命令都以 `/` 开头，发送 `/help` 可以随时查看完整功能列表。

### ❓ /help —— 功能总览

任何时候发送 `/help`（或 `/帮助`）都能看到最新功能列表。

### 📅 /退休 —— 退休倒计时

根据出生日期和性别计算预计退休日期与剩余天数，支持交互式输入：

```
/退休 [出生日期] [性别]
```

例如：

```
/退休 1995-01-01 男
/退休 1995-01-01 女
```

不带参数时会一步一步引导你输入；回复「取消」可退出。女性默认按女干部（原 55 岁）计算，也可以指定 `女工人`。

### 🧐 /查成分 —— B 站 VTuber 成分

输入 B 站用户名或 UID，查询 TA 关注了哪些 VTuber：

```
/查成分 <B站用户名或UID>
```

例如：

```
/查成分 9200471
```

### 🎲 /rd —— 掷骰子

支持 `[x]d[y]` 格式掷出多个骰子：

```
/rd [x]d[y]
```

例如：

```
/rd 2d6
/roll 1d20
/掷骰 3d8
```

### 💰 /营收 —— 虚拟主播营收榜

查询 VirtuaReal / PSPlive 等 B 站虚拟主播的月度/年度营收：

```
/营收 [年份|月份] [公会] [数量]
```

- 年份：`YYYY`（如 `2026`），汇总该年数据；当年只到当前月份（如 8 月查询即 1-8 月）
- 月份：`YYYYMM` 或 `YYYY-MM`，不写为当月
- 公会：`all` / `vr` / `psp`，不写默认为 `vr`（VirtuaReal）
- 数量：只看前 N 名，不写为全部
- 结果以图片形式发送，渲染不可用时自动回退为文本

例如：

```
/营收
/营收 2026
/营收 202607
/营收 202607 psp 10
```

数据来源：[dc.hihivr.top](https://dc.hihivr.top/)（第三方非官方接口，数据仅供参考）。

### 🎮 /游戏 —— 游戏日程

对接我自建的[游戏日程表](https://www.coni.top/game-schedule/)，可以查今天、本周或指定日期的游戏安排：

```
/游戏              查看今天
/游戏 本周         查看本周
/游戏 下周         查看下周
/游戏 明天         查看明天
/游戏 2026-08-22   查看指定日期（也支持 8月22日、8.22）
```

快捷指令：`/今日游戏` `/本周游戏` `/下周游戏`。

### 📺 /bili —— B 站直播与动态订阅

订阅指定 UP 主后，开播时推送图片卡片，下播推送文字通知，新动态也会定时检测推送：

```
/bili <add|del|list|login|push>
```

B 站订阅推送：

```
/bili add <UID>            订阅 UP 主（群主/管理员/超管）
/bili del <UID>            取消订阅
/bili list                 查看本群订阅
/bili atall live on <UID>  开播时 @全体（群主/管理员/超管）
/bili filter add <正则>    动态过滤
/bili push live <直播间号>  手动推送开播卡片
/bili login                扫码登录 B 站（超管）
```

还支持 @全体、关键词过滤、手动推送动态/视频/直播等，完整命令见 `/bili help`。

### 🤖 /autospk —— 定时自动发言（仅超管）

可设置定时任务，让机器人按指定时间自动发送消息，支持群聊和私聊：

#### 总开关

```
autospk on       开启自动发言
autospk off      关闭自动发言
autospk reload   重新加载配置
```

- 默认关闭：添加任务后需要先执行 `/autospk on`，否则任务不会定时发送。

#### 添加循环任务

```
autospk add <group|private> <目标> <HH:MM> <消息1>|<消息2>|... [days=...]
```

- 目标：群聊用群号或 `here`（当前群），私聊用 QQ 号或 `me`（自己）
- 时间：24 小时制，如 `09:00`、`21:30`
- 多条消息用 `|` 分隔，发送时随机取一条
- `days=` 指定星期几，不写则每天发送
- 消息内容可直接附带图片，插件自动保存到图片目录并在发送时带上

#### 添加一次性任务

```
autospk addonce <group|private> <目标> <YYYY-MM-DD> <HH:MM> <消息>
```


例如：

```
/autospk add group here 09:00 早上好|大家早上好|起床啦
/autospk add group here 09:00 早上好，上班啦 days=workday
/autospk addonce group here 2026-12-31 23:59 新年快乐
/autospk list / del / edit / preview ...
```

- 循环任务：每天或指定星期几定时发送，多条消息随机取一条
- 一次性任务：指定日期时间触发一次后自动删除
- 消息支持占位符：`{date}`、`{time}`、`{weekday}`、`{days_until_cn:日期}`、`{image:...}` 等
- 仅超级用户可用，发送 `/autospk` 可查看完整帮助

### ✅ 自动批准（好友申请 / 群邀请）

自动同意加好友申请和群邀请，开启后无需手动处理。相关配置（`.env`，默认关闭）：

```
AUTO_APPROVE_FRIEND=true
AUTO_APPROVE_GROUP_INVITE=true
AUTO_APPROVE_NOTIFY_SUPERUSER=true
```

- 三个开关默认均为关闭，设为 `true` 后生效
- 开启通知后，每次自动同意会私聊超级用户告知详情
- 申请加群（`add`）不会自动处理

## 联系我

- QQ：690379256
- 博客：[https://www.coni.top](https://www.coni.top)
- GitHub：[https://github.com/coni233](https://github.com/coni233)

有功能需求、Bug 反馈或其他想法，欢迎直接找我。

## 技术路线

### 总体架构

机器人采用 **LLBot + NoneBot2** 的双层架构：

```
QQ ──► LLBot（QQ 协议端，OneBot V11 实现）
          │  事件上报 / 指令下发（WebSocket）
          ▼
     NoneBot2（Python 机器人框架）
          │  加载插件 / 业务逻辑
          ▼
     plugins/（本地插件：退休、查成分、骰子、游戏日程、B站订阅……）
```

- **LLBot**（LuckyLilliaBot）负责 QQ 侧的协议接入：登录、收发消息、群事件等，对外提供标准的 OneBot V11 接口。
- **NoneBot2** 负责机器人业务：命令解析、插件调度、定时任务、消息渲染，通过 OneBot V11 适配器与 LLBot 通信。
- 两者解耦，符合 OneBot 标准，理论上任何 OneBot 实现端都能替换 LLBot。

### 项目结构

```
qqbot-nonebot-llbot/
├── LLBot-CLI-win-x64/      # QQ 协议端（llbot.exe，命令行版）
├── LLBot-Desktop-win-x64/  # QQ 协议端（桌面版，备用）
├── qqbot/                  # NoneBot2 项目
│   ├── plugins/            # 本地插件（可自由修改）
│   ├── .env.prod           # 运行配置
│   └── pyproject.toml      # 依赖与插件加载配置
└── data/                   # 插件运行数据（订阅、Cookie 等）
```

### 启动方式

1. 启动 QQ 协议端：运行 `llbot.exe`，登录 QQ。
   web 端口：http://127.0.0.1:3080/
2. 启动机器人：在 `qqbot` 目录下激活 Python 环境，执行：

```
nb run
```

LLBot 与 NoneBot 连接成功后，机器人即开始工作。

### 技术选型

| 组件 | 选型 | 版本 |
| --- | --- | --- |
| 运行语言 | Python（Miniconda 环境） | 3.12 |
| 机器人框架 | NoneBot2 | 2.5.0 |
| 适配器 | nonebot-adapter-onebot（OneBot V11） | 2.4.6 |
| 驱动 | FastAPI（HTTP + WebSocket） | 0.141 |
| 定时任务 | nonebot-plugin-apscheduler | 0.5.0 |
| 数据目录 | nonebot-plugin-localstore | 0.7.4 |
| 图片渲染 | nonebot-plugin-htmlrender + Playwright | 0.5.1 / 1.62 |
| HTTP 客户端 | httpx | — |
| 数据存储 | SQLite（aiosqlite） | — |

游戏日程表是独立的 PHP + MySQL 项目（[game-schedule-web](https://github.com/coni233/game-schedule-web)），机器人通过其只读 JSON API 查询数据，不直接访问数据库。

### 插件本地化思路

为了让插件能按个人需求随意修改、减少对环境的依赖，大部分插件直接以源码形式放在 `plugins/` 目录下，由 `plugin_dirs` 加载：

- 自己开发的插件：退休倒计时、游戏日程查询、help 等
- 从 GitHub 下载并本地维护的第三方插件：B 站订阅（bilibili）、查成分（ddcheck）、定时自动发言（autospeak）等

其中退休倒计时插件已发布到 PyPI（`nonebot-plugin-retirement-countdown`），商店审核通过后可通过 `nb plugin install` 一键安装。

### 一些问题

- **B 站接口风控**：B 站对匿名请求有 412 风控，动态轮询必须登录。解决方案是接入扫码登录，Cookie 持久化到本地数据库。
- **`plugin_dirs` 加载下的资源定位**：目录方式加载插件时模块名带目录前缀，插件内部按包名取内置模板会报错（Web 后台 500）。已修复为基于 `__file__` 定位资源，并向上游提交了 PR。
- **退出时的无害告警**：Playwright 在进程退出阶段关闭浏览器时会因连接已断开打印一条 WARNING，属于良性竞态，不影响正常退出。

## 致谢

本项目建立在以下开源项目之上，感谢这些项目和作者们的付出：

- [NoneBot2](https://github.com/nonebot/nonebot2) —— 机器人框架
- [LuckyLilliaBot（LLBot）](https://github.com/LLOneBot/LuckyLilliaBot) —— QQ 协议端，提供 OneBot V11 接口
- [nonebot-plugin-retirement-countdown](https://github.com/coni233/nonebot-plugin-retirement-countdown) —— 退休倒计时
- [nonebot-adapter-onebot](https://github.com/nonebot/adapter-onebot) —— OneBot V11 适配器
- [nonebot-plugin-apscheduler](https://github.com/nonebot/plugin-apscheduler) —— 定时任务
- [nonebot-plugin-localstore](https://github.com/nonebot/plugin-localstore) —— 本地数据存储
- [nonebot-plugin-htmlrender](https://github.com/nonebotjs/nonebot-plugin-htmlrender) —— 图片渲染
- [nonebot-plugin-bilibili](https://github.com/coni233/nonebot-plugin-bilibili) —— B 站直播/动态订阅（fork 自上游开源项目，本地维护并已向上游提交 PR）
- [nonebot-plugin-ddcheck](https://github.com/noneplugin/nonebot-plugin-ddcheck) —— B 站 VTuber 成分查询
- [nonebot-plugin-autospeak](https://github.com/TangTangChu/nonebot-plugin-autospeak) —— 定时自动发言
- [nonebot-plugin-roll](https://github.com/MinatoAquaCrews/nonebot_plugin_roll) —— 掷骰子（原作者 KafCoppelia）

## License

MIT