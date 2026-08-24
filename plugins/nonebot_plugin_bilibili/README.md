# nonebot-plugin-bilibili

基于 NoneBot2 与 OneBot V11 的 Bilibili 动态、视频、专栏、音乐和直播订阅推送插件。

插件采用“接口获取 -> 字体选择 -> 模板选择 -> Playwright 渲染 -> OneBot 图片推送”的统一流程。仅当图片渲染失败时才降级为文字消息。订阅数据、Cookie、过滤词、模板、字体和轮询状态全部保存在 `nonebot-plugin-localstore` 提供的插件数据目录中。

## 功能

- 定时轮询 UP 主动态；首次检查只建立最新动态基线，后续仅推送新发布内容
- 检测直播开播和下播状态；开播使用图片卡片，下播使用简洁文字通知
- 按动态号、AV/BV 号、直播间号手动推送
- 群维度正则过滤
- `all / dynamic / video / music / article / live` 六类 @全体配置
- 每个群分别配置动态、视频、直播三套模板、字体和渐变配色
- 聊天命令或 Web 页面扫码登录 Bilibili
- 带令牌鉴权的 Web 管理后台
- Web 上传字体和 HTML 模板
- QQ 群头像和 Bilibili UP 主头像管理界面

## 安装

运行环境要求 Python `>=3.10,<4.0`。请在 **NoneBot 项目根目录**执行安装命令，并确保
命令使用的是运行 NoneBot 的同一个 Python 虚拟环境。

### 使用 nb-cli（推荐）

已经使用 `nb-cli` 管理 NoneBot 项目时，可以直接安装：

```bash
nb plugin install nonebot-plugin-bilibili
```

`nb-cli` 会将依赖安装到当前 NoneBot 项目环境，并更新项目的插件配置。

### 使用 pip

激活 NoneBot 虚拟环境后执行：

```bash
python -m pip install --upgrade nonebot-plugin-bilibili
```

使用 `python -m pip` 可以减少把插件误装到其他 Python 环境的情况。

### 使用 uv

使用 `uv` 管理项目依赖：

```bash
uv add nonebot-plugin-bilibili
```

只向现有虚拟环境安装、不修改项目依赖文件时，可以使用：

```bash
uv pip install --upgrade nonebot-plugin-bilibili
```

### 使用 PDM

```bash
pdm add nonebot-plugin-bilibili
```

### 使用 Poetry

```bash
poetry add nonebot-plugin-bilibili
```

### 从源码安装

需要测试 GitHub 上尚未发布的代码时，可以安装开发分支：

```bash
python -m pip install --upgrade \
  "nonebot-plugin-bilibili @ git+https://github.com/mengbingnaixi/nonebot-plugin-bilibili.git"
```

源码版本可能包含尚未发布或未完成验证的改动，正常部署应优先安装 PyPI 正式版本。

### 升级与卸载

升级到最新正式版本：

```bash
python -m pip install --upgrade nonebot-plugin-bilibili
```

卸载插件：

```bash
python -m pip uninstall nonebot-plugin-bilibili
```

卸载 Python 包不会删除 `BILI_DATA` 或 localstore 数据目录中的订阅、Cookie、模板和字体。
如需重新安装，保留数据目录即可继续使用原数据。不要在没有备份的情况下手动删除该目录。

### 加载插件

插件首次启动时会检查 Playwright Chromium。浏览器资源缺失时，默认使用当前
Python 环境自动执行 `python -m playwright install chromium`。自动下载失败不会阻止
NoneBot 启动，但图片推送会暂时降级为文字；此时请根据启动日志手动安装浏览器资源。

在 NoneBot 项目的 `pyproject.toml` 中加载 OneBot V11 适配器和插件：

```toml
[tool.nonebot]
adapters = [
    { name = "OneBot V11", module_name = "nonebot.adapters.onebot.v11" },
]
plugins = ["nonebot_plugin_bilibili"]
```

最小 `.env` 示例：

```dotenv
DRIVER=~fastapi
HOST=127.0.0.1
PORT=8080
SUPERUSERS=["123456789"]

BILI_DATA=./data/nonebot_plugin_bilibili
BILI_SUBSCRIPTION_WEB_ENABLED=true
```

`SUPERUSERS` 中填写机器人管理员 QQ 号。Web 后台依赖 NoneBot 的 FastAPI 驱动；若
不启用 Web 后台，可以继续使用项目原有的驱动。OneBot 实现端还需要按其文档连接到
NoneBot，看到 OneBot V11 Bot 连接成功后，群列表扫描和群消息推送才可用。

启动 NoneBot 后可以依次完成：

1. 打开 `http://127.0.0.1:8080/bili-subscription/`，输入启动日志中的管理令牌。
2. 在登录页使用哔哩哔哩客户端扫码，确认后台显示 Cookie 已配置。
3. 扫描机器人已加入的 QQ 群，选择群和 UP 主 UID 添加订阅。
4. 使用 `/bili list` 检查当前群订阅，或在 Web 预览页验证图片模板。

当前 Bilibili 空间动态接口会对匿名请求返回 `412` 风控响应。安装后请先由超级用户执行 `/bili login`，或在 Web 后台完成扫码登录；未配置 Cookie 时插件会暂停动态轮询，但直播检测、视频查询和订阅配置仍可使用。

## 依赖

运行环境要求 Python `>=3.10,<4.0`。以下直接依赖会在安装插件时由 `pip` 自动解析和安装：

| 依赖 | 最低版本 | 用途 |
| --- | --- | --- |
| `nonebot2` | `2.5.0` | NoneBot2 核心框架 |
| `fastapi` | `0.100.0` | Web 后台 ASGI 应用框架 |
| `uvicorn[standard]` | `0.20.0` | FastAPI 驱动的 ASGI 服务器与 WebSocket 支持 |
| `nonebot-adapter-onebot` | `2.4.6` | OneBot V11 事件、消息与群聊接口 |
| `nonebot-plugin-apscheduler` | `0.5.0` | 动态和直播定时轮询任务 |
| `nonebot-plugin-htmlrender` | `0.6.7` | NoneBot HTML 渲染运行环境兼容 |
| `nonebot-plugin-localstore` | `0.7.0` | 默认插件数据目录管理 |
| `aiosqlite` | `0.20.0` | 异步 SQLite 数据持久化 |
| `httpx` | `0.28.0` | Bilibili API 异步 HTTP 请求 |
| `jinja2` | `3.0` | HTML 推送模板渲染 |
| `qrcode` | `7.4` | Bilibili 扫码登录二维码编码 |
| `pillow` | `9.1.0` | 将登录二维码输出为 PNG 图片 |
| `pydantic` | `2.0` | 插件配置与 Web 请求数据校验 |
| `playwright` | `1.40` | Chromium 图片卡片截图 |
| `python-multipart` | `0.0.9` | Web 后台字体和模板文件上传 |
| `regex` | `2024.5.15` | 带超时保护的关键词正则过滤 |

Playwright Python 包和插件 Wheel 不包含 Chromium 浏览器文件。插件默认在首次
启动时自动下载；如已关闭自动安装，或服务器需要预先准备离线环境，可手动执行：

```bash
playwright install chromium
```

Linux 缺少 Chromium 系统库时可使用：

```bash
playwright install --with-deps chromium
```

请使用运行 NoneBot 的同一个 Python/虚拟环境执行安装，否则 Playwright 可能仍然找不到浏览器。

构建源码包或 Wheel 使用：

| 依赖 | 用途 |
| --- | --- |
| `pdm-backend` | PEP 517 构建后端 |

使用 PDM 安装开发依赖：

```bash
pdm install -G dev
```

| 开发依赖 | 最低版本 | 用途 |
| --- | --- | --- |
| `black` | `24.4.2` | Python 代码格式化 |
| `isort` | `5.13.2` | Python 导入排序 |
| `pytest` | `8.0` | 单元和集成测试 |
| `pytest-asyncio` | `0.23` | 异步测试支持 |
| `ruff` | `0.6` | 代码规范和静态检查 |

插件还需要一个兼容 OneBot V11 的实现端（例如 NapCatQQ 或 Lagrange.Core），该实现端不是 Python 包，不会由 `pip` 自动安装。

## 配置

配置通过 NoneBot scoped config 获取。插件仅调用一次 `get_plugin_config`；数据目录覆盖项使用短名称 `BILI_DATA`，其他插件配置均使用 `BILI_SUBSCRIPTION_` 前缀。插件不会在运行时修改环境变量。

```dotenv
BILI_DATA=./data/nonebot_plugin_bilibili
BILI_SUBSCRIPTION_DYNAMIC_INTERVAL=120
BILI_SUBSCRIPTION_LIVE_INTERVAL=30
BILI_SUBSCRIPTION_REQUEST_TIMEOUT=15
BILI_SUBSCRIPTION_REQUEST_CONCURRENCY=4
BILI_SUBSCRIPTION_WEB_ENABLED=false
BILI_SUBSCRIPTION_WEB_PATH=/bili-subscription
BILI_SUBSCRIPTION_WEB_TOKEN=
BILI_SUBSCRIPTION_WEB_PUBLIC_URL=
BILI_SUBSCRIPTION_RENDER_WIDTH=720
BILI_SUBSCRIPTION_RENDER_TIMEOUT=15000
BILI_SUBSCRIPTION_AUTO_INSTALL_BROWSER=true
BILI_SUBSCRIPTION_INITIAL_DYNAMIC_LIMIT=3
BILI_SUBSCRIPTION_ENABLE_DYNAMIC=true
BILI_SUBSCRIPTION_ENABLE_LIVE=true
```

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `BILI_DATA` | 未设置 | 自定义数据目录；相对路径从 NoneBot 工作目录解析，目录不存在时自动创建 |
| `BILI_SUBSCRIPTION_DYNAMIC_INTERVAL` | `120` | 动态检测间隔，单位秒，最小 `30` |
| `BILI_SUBSCRIPTION_LIVE_INTERVAL` | `30` | 直播检测间隔，单位秒，最小 `10` |
| `BILI_SUBSCRIPTION_REQUEST_TIMEOUT` | `15` | Bilibili HTTP 请求超时，单位秒 |
| `BILI_SUBSCRIPTION_REQUEST_CONCURRENCY` | `4` | 同时检测的 UP 主数量，范围 `1-20` |
| `BILI_SUBSCRIPTION_WEB_ENABLED` | `false` | 是否启用 Web 管理后台 |
| `BILI_SUBSCRIPTION_WEB_PATH` | `/bili-subscription` | Web 后台路由前缀 |
| `BILI_SUBSCRIPTION_WEB_TOKEN` | 空 | 管理令牌；为空时首次启动生成并持久化 |
| `BILI_SUBSCRIPTION_WEB_PUBLIC_URL` | 空 | `/bili login` 失败时提示的后台访问地址 |
| `BILI_SUBSCRIPTION_RENDER_WIDTH` | `720` | Playwright 视口宽度，范围 `480-1600` |
| `BILI_SUBSCRIPTION_RENDER_TIMEOUT` | `15000` | 页面、图片和字体加载超时，单位毫秒 |
| `BILI_SUBSCRIPTION_AUTO_INSTALL_BROWSER` | `true` | Chromium 缺失时是否自动下载 |
| `BILI_SUBSCRIPTION_INITIAL_DYNAMIC_LIMIT` | `3` | 单轮最多处理最近几条新增动态，范围 `1-20` |
| `BILI_SUBSCRIPTION_ENABLE_DYNAMIC` | `true` | 是否启用动态检测任务 |
| `BILI_SUBSCRIPTION_ENABLE_LIVE` | `true` | 是否启用直播检测任务 |

每次启动时，动态任务会先静默同步当前最新动态号，再注册定时任务。重启前已经存在的动态不会补发；启动完成后发布的新动态仍会正常推送。如果旧游标已不在当前接口列表中，也只会重建基线，不会把历史列表当作新内容连续发送。

Web 后台的“运行配置”可以在不重启 NoneBot 的情况下修改动态/直播开关和轮询间隔。
这些值会写入数据库，并在后续启动时覆盖 `.env` 中对应的四项配置。若要恢复 `.env`
值，需要在 Web 后台重新保存目标值，或在停止 NoneBot 后删除数据库中的对应运行设置；
不要在进程运行时直接编辑 SQLite 文件。

首次直播检查的处理与动态不同：如果 UP 主当前正在直播，会推送开播通知；如果数据库
残留“正在直播”但重启后的首次检查已经下播，只同步为下播状态，不补发过期的下播通知。

`BILI_SUBSCRIPTION_AUTO_INSTALL_BROWSER` 默认为 `true`。设置为 `false` 后，插件只会
检查浏览器是否可用，不会联网下载；渲染不可用时推送流程会自动降级为文字消息。

`BILI_DATA` 可选。未配置时继续使用 `nonebot-plugin-localstore` 返回的数据目录；配置相对路径时以 NoneBot 当前工作目录为基准，配置绝对路径时直接使用该路径。插件不会自动覆盖或删除旧目录中的数据。

### 数据目录与备份

插件启动时会自动创建不存在的 `BILI_DATA` 及其子目录。Web 后台状态页也会显示当前
实际使用的数据目录：

```text
<BILI_DATA>/
├─ subscription.sqlite3  # 订阅、Cookie、过滤词、运行配置、检测游标和发送回执
├─ fonts/                # Web 上传字体
├─ templates/            # Web 上传 HTML 模板
└─ renders/              # 渲染相关数据
```

备份时应先停止 NoneBot，再复制整个目录，以避免 SQLite 文件和上传资源处于不同时间点。
恢复时同样在停止状态下覆盖完整目录。`subscription.sqlite3` 包含 Bilibili Cookie 和 Web
管理信息，不应上传到公开仓库或发送给他人。

## 命令

| 命令 | 说明 | 权限 |
| --- | --- | --- |
| `/bili add <uid>` | 订阅 UP 主 | 群主、群管理员、超管 |
| `/bili del <uid>` | 取消订阅 | 群主、群管理员、超管 |
| `/bili list` | 查看本群订阅 | 所有人 |
| `/bili listall` | 查看全部群订阅 | 超管 |
| `/bili delall` | 清除本群订阅 | 群主、群管理员、超管 |
| `/bili delallall` | 清除所有群订阅 | 超管 |
| `/bili atall <类型> on\|off <uid>` | 设置 @全体 | 群主、群管理员、超管 |
| `/bili atall list` | 查看本群 @全体配置 | 所有人 |
| `/bili filter add <正则>` | 添加过滤规则 | 群主、群管理员、超管 |
| `/bili filter del <规则或序号>` | 删除过滤规则 | 群主、群管理员、超管 |
| `/bili filter list` | 查看过滤规则 | 所有人 |
| `/bili push dynamic <动态号>` | 手动推送动态 | 群主、群管理员、超管 |
| `/bili push video <AV/BV号>` | 手动推送视频 | 群主、群管理员、超管 |
| `/bili push live <直播间号>` | 手动推送直播卡片 | 群主、群管理员、超管 |
| `/bili login` | 扫码登录 Bilibili | 超管 |
| `/bili help image` | 图片版帮助 | 所有人 |

超级用户可在私聊命令末尾添加 `-群号`：

```text
/bili add 12345 -123456789
/bili del 12345 -123456789
/bili list -123456789
/bili push video BV1xx411c7mD -123456789
```

群管理员即使手动添加后缀，也不能操作其他群。

## @全体组合规则

- 开启 `all`：清除其他五类，只保留 `all`
- 开启其他类型：自动关闭 `all`
- `dynamic / video / music / article / live` 可以同时开启
- `dynamic` 仅匹配普通动态，视频、音乐和专栏由各自开关控制
- 下播通知不会触发 @全体

## 自定义模板和字体

### 作用范围

渲染方案按“群 + 内容类别”保存。每个群可以分别设置三套方案：

| 后台类别 | 使用该模板的内容 |
| --- | --- |
| `dynamic` | 普通动态、音乐、专栏和转发动态 |
| `video` | 视频投稿 |
| `live` | 开播通知 |

当前版本不提供每位 UP 独立模板。同一个群中，相同类别的所有订阅共用该群选择的模板、字体、主色和渐变色。下播通知固定使用文字，不进入直播模板渲染。

未选择上传模板时使用 Wheel 内置模板。模板、字体和配色互相独立，例如可以使用内置动态模板搭配上传字体，也可以只更换模板并保留默认字体。

制作新模板时可以直接复制内置模板再修改：

- `nonebot_plugin_bilibili/resources/dynamic.html`
- `nonebot_plugin_bilibili/resources/video.html`
- `nonebot_plugin_bilibili/resources/live.html`

### 文件位置和上传要求

上传文件保存在插件数据目录：

```text
<BILI_DATA>/
├─ subscription.sqlite3
├─ fonts/
├─ templates/
└─ renders/
```

模板要求：

- 扩展名为 `.html` 或 `.htm`
- UTF-8 编码
- 不超过 10 MiB
- 必须包含 `id="bili-card"` 或 `id='bili-card'`
- 相同文件名再次上传会覆盖原文件

Playwright 最终只截取 `#bili-card`，不会截取整个页面。需要出现在图片中的背景、边框和内容都必须放在该元素内部。

最小模板：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    {{ font_css | safe }}
    * { box-sizing: border-box; }
    html, body { margin: 0; background: transparent; }
    #bili-card {
      width: 560px;
      padding: 24px;
      border-radius: 12px;
      background: #fff;
      color: #18191c;
    }
  </style>
</head>
<body>
  <article id="bili-card">
    <strong>{{ content.author_name }}</strong>
    <h1>{{ content.title }}</h1>
    {% if content.text %}<div>{{ content.text }}</div>{% endif %}
  </article>
</body>
</html>
```

### 模板执行环境

模板由 Jinja2 `SandboxedEnvironment` 渲染，并启用 `StrictUndefined`：

- 使用不存在或拼错的变量会导致渲染失败
- 群推送渲染失败时会自动降级为文字消息
- Web 预览会显示具体错误，适合调试模板
- Playwright 禁用 JavaScript，不要依赖 `<script>`
- 不允许加载远程 JavaScript、CSS、字体或任意网络资源
- 外部图片只允许 Bilibili 图片域名和 QQ 群头像域名
- 内联 HTML、CSS 和上传字体生成的 `data:` 字体可以使用

可选字段必须先判断：

```jinja2
{% if content.cover %}
  <img src="{{ content.cover }}" alt="封面">
{% endif %}

{% if content.forward %}
  <div>转发自 @{{ content.forward.author_name }}</div>
{% endif %}
```

### `content` 完整字段

| 表达式 | 类型 | 说明 |
| --- | --- | --- |
| `content.id` | `str` | 动态号、BV 号或直播间号 |
| `content.uid` | `int` | UP 主 UID |
| `content.kind.value` | `str` | `dynamic / video / music / article / live` |
| `content.title` | `str` | 标题；普通动态可能是默认占位标题 |
| `content.text` | `str` | 纯文本正文，保留换行 |
| `content.url` | `str` | Bilibili 内容地址 |
| `content.author_name` | `str` | UP 主名称 |
| `content.author_avatar` | `str` | UP 主头像 URL，可能为空 |
| `content.cover` | `str` | 视频、直播封面或第一张动态图片 |
| `content.images` | `list[str]` | 动态图片 URL |
| `content.image_dimensions` | `list[tuple[int, int]]` | 与 `images` 同顺序的 `(宽, 高)` |
| `content.rich_text` | `list[RichTextSegment]` | 带 Bilibili 表情信息的正文分段 |
| `content.published_at` | `int` | Unix 发布时间戳，没有时间时为 `0` |
| `content.published_text` | `str` | 北京时间 `YYYY-MM-DD HH:MM` |
| `content.live_action` | `LiveAction \| None` | 直播状态；存在时 `.value` 为 `start` 或 `stop` |
| `content.forward` | `PushContent \| None` | 转发动态的原动态，字段结构相同 |
| `content.raw` | `dict` | 原始 API 数据，不保证跨接口版本稳定 |

发布模板应优先使用标准化字段，不建议依赖 `content.raw`。

访问直播状态时必须先判空：

```jinja2
{% if content.live_action %}
  {{ content.live_action.value }}
{% endif %}
```

`RichTextSegment` 提供 `segment.text` 和 `segment.emoji_url` 两个字段。

### 富文本和 Bilibili 表情

`content.text` 只包含文字。需要显示表情图片时，应遍历 `content.rich_text`：

```html
{% if content.rich_text %}
  <div class="text">
    {% for segment in content.rich_text %}
      {% if segment.emoji_url %}
        <img class="emoji" src="{{ segment.emoji_url }}" alt="{{ segment.text }}">
      {% else %}
        {{ segment.text }}
      {% endif %}
    {% endfor %}
  </div>
{% elif content.text %}
  <div class="text">{{ content.text }}</div>
{% endif %}
```

```css
.text { line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.emoji {
  display: inline-block;
  width: 24px;
  height: 24px;
  margin: 0 2px;
  vertical-align: -6px;
  object-fit: contain;
}
```

### 九宫格和长图

动态模板可使用图片尺寸识别长图。下面的宏最多显示 9 张图片，高度达到宽度 3 倍时从顶部裁切，并显示“长图”标记，与 Bilibili 网页九宫格一致：

```html
{% macro image_grid(item) -%}
  {% set pictures = item.images[:9] %}
  {% set dimensions = item.image_dimensions[:9] %}
  {% if pictures %}
    <div class="image-grid">
      {% for picture in pictures %}
        {% set size = dimensions[loop.index0]
          if loop.index0 < dimensions|length else none %}
        {% set is_long = size and size[0] > 0 and size[1] >= size[0] * 3 %}
        <div class="image-cell">
          <img class="picture{% if is_long %} long{% endif %}"
               src="{{ picture }}" alt="动态图片 {{ loop.index }}">
          {% if is_long %}<span class="long-badge">长图</span>{% endif %}
        </div>
      {% endfor %}
    </div>
  {% endif %}
{%- endmacro %}
```

```css
.image-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}
.image-cell {
  position: relative;
  overflow: hidden;
  aspect-ratio: 1;
  border-radius: 8px;
  background: #f1f2f3;
}
.picture { display: block; width: 100%; height: 100%; object-fit: cover; }
.picture.long { object-position: center top; }
.long-badge {
  position: absolute;
  right: 5px;
  bottom: 5px;
  padding: 2px 5px;
  border-radius: 3px;
  background: rgba(35, 39, 46, .72);
  color: #fff;
  font-size: 10px;
}
```

单张长图通常不应强制裁成正方形，可以在图片数量为 1 时单独使用 `height: auto` 和 `object-fit: contain`。

### 转发动态

`content.forward` 存在时，应单独渲染原动态。图片宏和富文本宏都可以复用：

```html
{{ render_text(content) }}
{{ image_grid(content) }}

{% if content.forward %}
  <section class="forward-card">
    <strong>@{{ content.forward.author_name }}</strong>
    {% if content.forward.title and content.forward.title != "发布了新动态" %}
      <h2>{{ content.forward.title }}</h2>
    {% endif %}
    {{ render_text(content.forward) }}
    {{ image_grid(content.forward) }}
  </section>
{% endif %}
```

### 字体、颜色和渐变

渲染器还会传入：

| 变量 | 说明 |
| --- | --- |
| `font_css` | 当前字体 CSS 与主题 CSS 变量，必须使用 `safe` 输出 |
| `accent_color` | 主色，例如 `#fb7299` |
| `gradient_color` | 渐变第二色，未开启渐变时为 `None` |
| `theme_background` | 已组合的纯色或 `linear-gradient(...)` |

通过 `{{ font_css | safe }}` 注入后，模板可以使用以下 CSS 变量：

```css
:root {
  --bili-accent: #fb7299;
  --bili-accent-2: #9edcff;
  --bili-theme: linear-gradient(135deg, #fb7299 0%, #9edcff 100%);
}

#bili-card { background: var(--bili-theme); }
.author-name { color: var(--bili-accent); }
```

建议在模板 `<style>` 开头保留：

```jinja2
{{ font_css | safe }}
```

模板遗漏该占位符时，渲染器会尽量自动向 `<head>` 注入已选择的字体，但依赖主题变量的模板仍应显式保留该占位符。支持 `.ttf`、`.otf`、`.woff` 和 `.woff2`，上限 10 MiB；截图前会等待 `document.fonts.ready`。

### 视频和直播模板字段建议

视频模板主要使用 `content.cover`、`content.title`、`content.text`、`content.author_name`、`content.author_avatar`、`content.published_text` 和 `content.id`。

开播模板主要使用 `content.cover`、`content.title`、`content.author_name`、`content.author_avatar`、`content.published_text`、`content.id` 和 `content.text`。下播固定发送 `🔴 用户名 直播结束啦，下次见~`，无需设计下播图片模板。

### 预览流程

1. 在 Web 后台资源页面上传模板和字体。
2. 选择动态、视频或直播预览类型。
3. 输入真实动态号、AV/BV 号或直播间号；留空使用示例数据。
4. 选择模板、字体、主色和可选渐变色。
5. 生成预览，检查长文本、表情、转发、九宫格和长图。
6. 回到订阅页面，在对应群卡片中保存动态、视频或直播方案。

真实编号预览只生成图片，不发送群消息，也不修改订阅。

### 常见问题

| 现象 | 原因和处理方式 |
| --- | --- |
| 上传提示缺少 `#bili-card` | 添加唯一的 `id="bili-card"` 截图元素 |
| 预览提示变量未定义 | 对照字段表检查拼写，并用 `{% if %}` 保护可选字段 |
| 图片不显示 | 使用标准化的 `cover/images/author_avatar`，不要引用任意外部域名 |
| 表情只显示文字 | 遍历 `rich_text`，不要只输出 `text` |
| 转发内容为空 | 判断并渲染 `content.forward` |
| 长图显示中段 | 使用 `image_dimensions` 判断长图并设置顶部定位 |
| 字体没有变化 | 确认字体有效，且文件内容与 TTF/OTF/WOFF/WOFF2 扩展名一致 |
| 页面正常但截图不完整 | 把全部可见内容放入 `#bili-card` |
| 脚本没有执行 | Playwright 已禁用 JavaScript，请改用 Jinja2 和 CSS |

### 自定义选择器

第三方扩展可以替换默认模板、字体和配色选择策略：

```python
from pathlib import Path

from nonebot_plugin_bilibili.models import PushContent
from nonebot_plugin_bilibili.selectors import (
    register_color_selector,
    register_font_selector,
    register_gradient_selector,
    register_template_selector,
)


async def choose_template(group_id: int, content: PushContent) -> Path | None:
    if content.kind.value == "live":
        return Path("/absolute/path/to/live.html")
    return None


async def choose_font(group_id: int, content: PushContent) -> Path | None:
    return Path("/absolute/path/to/font.woff2")


async def choose_color(group_id: int, content: PushContent) -> str | None:
    return "#00aeec"


async def choose_gradient(group_id: int, content: PushContent) -> str | None:
    return "#fb7299"


register_template_selector(choose_template)
register_font_selector(choose_font)
register_color_selector(choose_color)
register_gradient_selector(choose_gradient)
```

选择器必须是异步函数。模板和字体选择器返回存在的本地文件路径或 `None`，配色选择器
返回 `#RRGGBB` 或 `None`。返回 `None` 时使用对应的内置素材或默认配色；注册后会替换
进程级默认选择策略。第三方扩展应在本插件完成加载后注册选择器。

## Web 后台

后台支持：

- 从已连接的 OneBot V11 Bot 扫描群列表，并显示群名称、群头像和人数
- 添加和删除群订阅
- 查看 QQ 群头像和 UP 主头像
- 管理每个 UID 的六类 @全体开关
- 管理群过滤规则
- 设置或扫码刷新 Cookie
- 上传字体和模板
- 设置每个群的动态、视频、直播三类素材与配色
- 使用真实动态号、AV/BV 号或直播间号组合预览模板、字体和渐变
- 向指定群手动推送动态、视频或直播卡片
- 在线启停动态/直播任务并修改轮询间隔

Web 接口支持登录 Cookie、`X-Bili-Token` 请求头或 `?token=` 查询参数。上传文件名会被净化，文件类型和大小会被限制；Playwright 禁用 JavaScript，并只允许加载 Bilibili 图片域名和 QQ 群头像域名。

群列表扫描返回 `OneBot V11 尚未连接` 时，应先检查实现端与 NoneBot 的 WebSocket 连接，
而不是手动伪造群信息。扫码成功以后，后台状态以数据库中实际保存的 Cookie 为准；若仍
显示未配置，请查看 NoneBot 日志中的 Bilibili 登录接口返回信息，并确认浏览器没有打开
另一个 `BILI_DATA` 对应的后台实例。

### 常见运行问题

| 现象 | 检查项 |
| --- | --- |
| Web 路径返回 `404` | 确认 `BILI_SUBSCRIPTION_WEB_ENABLED=true`，并使用 FastAPI 驱动后重启 |
| 后台要求管理令牌 | 使用 `.env` 配置值，或启动日志中自动生成并持久化的令牌 |
| 无法扫描 QQ 群 | 确认 OneBot V11 Bot 已连接，且实现端支持 `get_group_list` |
| 动态接口返回 `412` | 重新扫码获取 Cookie，确认运行实例使用正确的数据目录 |
| 图片推送降级为文字 | 检查 Chromium、模板错误、字体文件以及图片域名加载日志 |
| 重启后没有补发停机期间动态 | 这是防止历史动态连发的基线策略；启动后新动态仍会推送 |
| 新订阅没有立即推送最新动态 | 这是预期行为；首次动态检查只建立基线 |
| 下播通知没有图片 | 这是预期行为；下播固定发送简洁文字消息 |

## 开发

```bash
pdm install -G dev
pdm run test
pdm run format
```

也可以在已安装开发依赖的环境中直接执行：

```bash
pytest
ruff check .
```

构建源码包和 Wheel：

```bash
pdm build
```

发布前建议执行：

```bash
pdm run test
ruff check .
twine check dist/*
check-wheel-contents dist/*.whl
```

## 鸣谢

- [bilibili-dynamic-mirai-plugin](https://github.com/Colter23/bilibili-dynamic-mirai-plugin) — 参考 v3 架构设计
- [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) — B 站 API 文档
- [NoneBot2](https://nonebot.dev/) — Python 异步聊天机器人框架

---

## 许可证

MIT License

Copyright (c) 2024 mengbingnaixi
