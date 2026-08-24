<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-retirement-countdown

_✨ 一个计算退休日期与退休倒计时的 NoneBot2 插件 ✨_

<a href="./LICENSE">
	<img src="https://img.shields.io/github/license/coni233/nonebot-plugin-retirement-countdown.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-retirement-countdown">
	<img src="https://img.shields.io/pypi/v/nonebot-plugin-retirement-countdown.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>

## 安装

### 使用 NB-CLI 安装（推荐）

```bash
nb plugin install nonebot-plugin-retirement-countdown
```

### 使用 pip 安装

```bash
pip install nonebot-plugin-retirement-countdown
```

使用 pip 安装后，还需要在 NoneBot 项目根目录的 `pyproject.toml` 中手动注册插件，
在 `[tool.nonebot.plugins]` 中添加：

```toml
[tool.nonebot.plugins]
nonebot-plugin-retirement-countdown = ["nonebot_plugin_retirement_countdown"]
```

然后重启机器人（`nb run`）即可加载插件。

## 使用

### 命令

| 命令 | 说明 |
| --- | --- |
| `/退休` | 交互式输入出生日期与性别，返回退休测算结果 |
| `/退休 1995-01-01 男` | 直接传入出生日期与性别 |

命令别名：`/退休倒计时`

### 支持的输入格式

出生日期：

- `1995-01-01` / `1995/1/1` / `1995.1.1`
- `1995年1月1日` / `1995年1月`
- `6月1日`（默认当前年份）

性别（职工类型）：

- `男`
- `女`（默认按女干部、原 55 周岁计算）
- `女工人` / `女干部`

### 示例

```
/退休 1995-01-01 男

📅 退休倒计时测算

出生日期：1995-01-01
职工类型：男职工
原法定退休年龄：60岁
改革后退休年龄：63岁（延迟 36 个月）
预计退休日期：2058-01-01

⏳ 距离退休还有 11457 天
```

## 计算规则

依据《国务院关于渐进式延迟法定退休年龄的办法》（2025 年 1 月 1 日起施行）：

| 职工类型 | 原法定退休年龄 | 改革后法定退休年龄 | 延迟节奏 |
| --- | --- | --- | --- |
| 男职工 | 60 周岁 | 63 周岁 | 每 4 个月延迟 1 个月 |
| 女干部（原 55 周岁） | 55 周岁 | 58 周岁 | 每 4 个月延迟 1 个月 |
| 女工人（原 50 周岁） | 50 周岁 | 55 周岁 | 每 2 个月延迟 1 个月 |

> [!NOTE]
> 本插件仅按法定退休年龄测算退休日期，未考虑养老保险最低缴费年限、
> 特殊工种提前退休、病退等情形，测算结果仅供参考，请以官方经办结果为准。

## 开发

项目结构：

```text
nonebot_plugin_retirement_countdown/
├── __init__.py      # 插件元数据
├── data_source.py   # 退休测算核心逻辑（纯函数，可单测）
└── matcher.py       # /退休 命令处理
tests/
└── test_data_source.py
```

运行单元测试（使用标准库 unittest，无需额外依赖）：

```bash
python -m unittest discover -s tests -v
```

### 在本机 qqbot 工程中联调

如果通过 editable 方式安装到本地 NoneBot 工程中调试，请使用
`compat` 模式安装，否则 NoneBot 的插件加载器无法识别该插件
（报错：`Module ... is not loaded as a plugin!`）：

```bash
pip install -e . --config-settings editable_mode=compat
```

之后修改代码重启 bot 即可生效；如果再次执行不带参数的
`pip install -e .`，需要重新带上 `--config-settings editable_mode=compat`。

## License

MIT
