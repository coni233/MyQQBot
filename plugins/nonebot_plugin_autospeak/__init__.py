import json
import random
import re
from pathlib import Path
from datetime import datetime

from nonebot import get_bot, get_plugin_config, logger, require
from nonebot.plugin import PluginMetadata, on_command
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State
from nonebot.params import CommandArg
from nonebot.adapters import Event, Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

# 跨插件依赖需先 require 再 import
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")

from nonebot_plugin_apscheduler import scheduler
import nonebot_plugin_localstore as store

from .config import Config
from .images import save_image_segment
from .placeholders import render_placeholders

plugin_config = get_plugin_config(Config)

__plugin_meta__ = PluginMetadata(
    name="AutoSpeak",
    description="定时自动发言插件（群聊/私聊、JSON配置、多条随机消息、按星期发送、预设占位符）",
    usage=(
        "autospk on/off/add/addonce/del/list/edit/reload/preview/placeholders\n"
        "仅 SUPERUSER 可用，具体用法请发送指令查看提示。"
    ),
    type="application",
    homepage="https://github.com/TangTangChu/nonebot-plugin-autospeak",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

# localstore 管理存储路径
CONFIG_PATH = store.get_plugin_config_file("config.json")
IMAGES_DIR = store.get_plugin_data_dir() / "images"

# 旧版存储路径，用于一次性迁移
LEGACY_DATA_DIR = Path("data/autospeak")


def migrate_legacy_data():
    """旧版 data/autospeak/ 迁移到 localstore 路径，新路径已有数据则跳过。"""
    if CONFIG_PATH.is_file():
        return
    legacy_cfg = LEGACY_DATA_DIR / "config.json"
    if not legacy_cfg.is_file():
        return
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(legacy_cfg.read_text("utf-8"), "utf-8")
        logger.info(f"[AutoSpeak] 已从旧路径迁移配置文件: {LEGACY_DATA_DIR} -> {CONFIG_PATH}")
        legacy_images = LEGACY_DATA_DIR / "images"
        if legacy_images.is_dir():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            moved = 0
            for f in legacy_images.iterdir():
                if f.is_file():
                    (IMAGES_DIR / f.name).write_bytes(f.read_bytes())
                    moved += 1
            logger.info(f"[AutoSpeak] 已迁移 {moved} 张图片: {legacy_images} -> {IMAGES_DIR}")
    except Exception as e:
        logger.error(f"[AutoSpeak] 旧数据迁移失败: {e}")

CONFIG = {
    "enabled": False,
    "next_id": 1,
    "tasks": [],
}


def ensure_next_id():
    """扫描任务取最大 ID，确保 next_id 不重复。"""
    global CONFIG
    tasks = CONFIG.get("tasks", [])
    existed_next = CONFIG.get("next_id", 1)
    max_id = 0
    for t in tasks:
        try:
            tid = int(t.get("id", 0))
            if tid > max_id:
                max_id = tid
        except Exception:
            continue
    CONFIG["next_id"] = max(existed_next, max_id + 1)


def load_config():
    global CONFIG
    if CONFIG_PATH.is_file():
        try:
            CONFIG = json.loads(CONFIG_PATH.read_text("utf-8"))
            ensure_next_id()
        except Exception as e:
            logger.error(f"[AutoSpeak] 配置文件读取失败: {e}")
    else:
        # 文件缺失时重置为默认配置
        CONFIG = {"enabled": False, "next_id": 1, "tasks": []}
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        save_config()
    # {image:文件名} 占位符默认读取的图片目录
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def save_config():
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(CONFIG, ensure_ascii=False, indent=2), "utf-8"
        )
    except Exception as e:
        logger.error(f"[AutoSpeak] 配置文件写入失败: {e}")


def parse_weekdays(spec: str):
    """解析星期配置，返回 0-6 列表，0=周一。

    支持空、*、all、everyday、workday、wd、数字 1-7 与英文缩写。
    """
    spec = (spec or "").strip().lower()
    if not spec or spec in ("*", "all", "everyday"):
        return list(range(7))
    if spec in ("workday", "wd"):
        return [0, 1, 2, 3, 4]

    token_map = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }

    days = set()
    for part in re.split(r"[,\u3001，]+", spec):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            n = int(part)
            if 1 <= n <= 7:
                days.add((n - 1) % 7)
        else:
            v = token_map.get(part)
            if v is not None:
                days.add(v)

    if not days:
        raise ValueError("invalid weekday spec")

    return sorted(days)


def format_weekdays(weekdays):
    """星期列表转中文描述。"""
    if not weekdays:
        return "（未设置，按每天处理）"
    wd_set = set(int(x) for x in weekdays)
    if wd_set == set(range(7)):
        return "每天"
    if wd_set == {0, 1, 2, 3, 4}:
        return "工作日（周一~周五）"
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return "、".join(names[d] for d in sorted(wd_set))


def compose_message(task) -> str | None:
    """随机取一条消息并渲染占位符，无消息返回 None。"""
    messages = task.get("messages") or []
    if not messages:
        return None
    return render_placeholders(str(random.choice(messages)), images_dir=IMAGES_DIR)


async def send_task_message(task_id: int):
    """按任务 ID 发送消息，一次性任务执行后自动移除。"""
    if not CONFIG.get("enabled", False):
        return

    task = next(
        (t for t in CONFIG.get("tasks", []) if int(t.get("id")) == int(task_id)), None
    )
    if not task:
        job_id = f"autospeak_{task_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        return

    msg = compose_message(task)
    if not msg:
        return

    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"[AutoSpeak] 获取 bot 失败: {e}")
        return

    ttype = task.get("type")
    target_id = task.get("target_id")

    try:
        if ttype == "group":
            await bot.call_api(
                "send_group_msg",
                group_id=int(target_id),
                message=msg,
            )
        elif ttype == "private":
            await bot.call_api(
                "send_private_msg",
                user_id=int(target_id),
                message=msg,
            )
        else:
            logger.warning(f"[AutoSpeak] 未知任务类型: {task}")
    except Exception as e:
        logger.error(f"[AutoSpeak] 发送消息失败: {e}")

    # 一次性任务执行后自动移除
    if task.get("kind") == "once":
        CONFIG["tasks"] = [
            t for t in CONFIG.get("tasks", []) if int(t.get("id")) != int(task_id)
        ]
        save_config()
        logger.info(f"[AutoSpeak] 一次性任务 {task_id} 已执行并自动移除")


def clear_jobs():
    for job in scheduler.get_jobs():
        if job.id.startswith("autospeak_"):
            scheduler.remove_job(job.id)


def cleanup_expired_once_tasks():
    """清理已过期或日期非法的一次性任务。"""
    now = datetime.now()
    tasks = CONFIG.get("tasks", [])
    keep = []
    removed = []
    for t in tasks:
        if t.get("kind") == "once":
            dt_str = t.get("datetime") or ""
            try:
                run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                if run_date <= now:
                    removed.append(t.get("id"))
                    continue
            except ValueError:
                removed.append(t.get("id"))
                continue
        keep.append(t)
    if removed:
        CONFIG["tasks"] = keep
        save_config()
        logger.info(f"[AutoSpeak] 清理已过期的一次性任务: {removed}")


def schedule_task(task):
    """注册任务 job。cron 按 time+weekdays 循环，once 按 datetime 触发一次。"""
    task_id = task.get("id")
    if task_id is None:
        return

    job_id = f"autospeak_{task_id}"
    kind = task.get("kind", "cron")

    try:
        if kind == "once":
            dt_str = task.get("datetime")
            if not dt_str:
                return
            run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if run_date <= datetime.now():
                logger.warning(
                    f"[AutoSpeak] 一次性任务 {task_id} 已过期，跳过注册：{dt_str}"
                )
                return
            scheduler.add_job(
                send_task_message,
                "date",
                id=job_id,
                run_date=run_date,
                args=[int(task_id)],
                replace_existing=True,
            )
            logger.info(f"[AutoSpeak] 注册一次性任务 {task_id} @ {dt_str}")
            return

        time_str = task.get("time")
        if not time_str:
            return
        dt = datetime.strptime(time_str, "%H:%M")
        weekdays = task.get("weekdays")
        # 未设置则每天触发
        if not weekdays:
            day_of_week = "*"
        else:
            day_of_week = ",".join(str(int(d)) for d in weekdays)

        scheduler.add_job(
            send_task_message,
            "cron",
            id=job_id,
            hour=dt.hour,
            minute=dt.minute,
            day_of_week=day_of_week,
            args=[int(task_id)],
            replace_existing=True,
        )
        logger.info(f"[AutoSpeak] 注册任务 {task_id} @ {time_str} dows={day_of_week}")
    except Exception as e:
        logger.error(f"[AutoSpeak] 注册任务 {task_id} 失败: {e}")


def schedule_all_tasks():
    cleanup_expired_once_tasks()
    clear_jobs()

    if not CONFIG.get("enabled", False):
        return

    for task in CONFIG.get("tasks", []):
        schedule_task(task)


# 加载时迁移旧数据、读取配置并注册任务
migrate_legacy_data()
load_config()
schedule_all_tasks()


# 指令部分，仅 SUPERUSER 可用

HELP_TEXT = (
    "AutoSpeak 帮助：\n"
    "  autospk on                  开启自动发言\n"
    "  autospk off                 关闭自动发言\n"
    "  autospk add ...             添加循环任务（每天/指定星期几）\n"
    "  autospk addonce ...         添加一次性任务（精确到年月日时分）\n"
    "  autospk del <task_id>       删除任务\n"
    "  autospk list                列出所有任务\n"
    "  autospk edit ...            修改任务时间或消息\n"
    "  autospk preview <文本>      预览占位符渲染结果\n"
    "  autospk placeholders        查看预设占位符说明\n"
    "  autospk reload              重新加载并应用配置\n\n"
    "说明：\n"
    "  - 默认：循环任务在“每天”的指定时间发送\n"
    "  - 可选：通过 days=... 指定星期几发送（见 add 帮助）\n"
    "  - 一次性任务在指定时刻仅触发一次，触发后自动删除\n"
    "  - 消息内容支持预设占位符，配置时可直接发送图片，见 autospk placeholders\n"
    "提示：只有 SUPERUSER 可以使用本插件指令。"
)

PLACEHOLDERS_HELP = (
    "AutoSpeak 预设占位符（发送时自动替换为实际内容）：\n\n"
    "  {date} / {date:格式}          当前日期，默认 YYYY-MM-DD\n"
    "  {time} / {time:格式}          当前时间，默认 HH:MM:SS\n"
    "  {datetime} / {datetime:格式}  当前日期时间，默认 YYYY-MM-DD HH:MM:SS\n"
    "  {weekday}                     今天星期几（周一~周日）\n"
    "  {days_until:日期}             距目标日期还有几天（未来为正、过去为负、当天为 0）\n"
    "  {days_until_cn:日期}          中文描述：还有 N 天 / 就是今天 / 已过 N 天\n"
    "  {image:路径|URL|文件名}        发送图片，渲染为 CQ 码如 [CQ:image,file=...]\n\n"
    "格式说明：\n"
    "  - 日期支持 YYYY-MM-DD，或 YYYY-MM-DD HH:MM[:SS]（精确到秒）\n"
    "  - 日期时间格式为 strftime：%Y 年 %m 月 %d 日 %H 时 %M 分 %S 秒\n"
    "  - 图片支持 http(s):// 链接、base64:// 数据和绝对路径\n"
    "  - 裸文件名指向插件图片目录；配置任务时直接发图可自动保存\n"
    "  - CQ 码可直接写在消息里原样透传\n\n"
    "示例：\n"
    "  距离高考还有 {days_until_cn:2026-06-07}\n"
    "  今天是 {date:%Y年%m月%d日} {weekday} {time:%H:%M}\n"
    "  早安 {image:greeting.png}"
)

autospeak_cmd = on_command(
    "autospk",
    aliases={"autospeak"},
    permission=SUPERUSER,
    priority=plugin_config.autospeak_command_priority,
    block=True,
)


def args_text_prefix(plain: str, n: int) -> str:
    """取 plain 中前 n 个 token 的原文。"""
    m = re.match(rf"^\s*\S+(?:\s+\S+){{{n - 1}}}", plain)
    return m.group(0) if m else plain


async def rebuild_content_from_message(msg: Message, args_text: str) -> str:
    """按消息段重建内容文本：先消耗参数前缀，图片段保存并转 {image:文件名}。"""
    parts_out = []
    rest = args_text
    for seg in msg:
        if seg.type == "text":
            t = str(seg.data.get("text", ""))
            if rest:
                n = min(len(rest), len(t))
                t = t[n:]
                rest = rest[n:]
            if t:
                parts_out.append(t)
        elif seg.type == "image":
            name = await save_image_segment(seg, IMAGES_DIR)
            if name:
                parts_out.append(f"{{image:{name}}}")
    return "".join(parts_out)


@autospeak_cmd.handle()
async def _(event: Event, state: T_State, arg: Message = CommandArg()):
    """autospk 主命令入口。"""
    text = arg.extract_plain_text().strip()
    if not text:
        await autospeak_cmd.finish(HELP_TEXT)

    parts = text.split()
    sub = parts[0].lower()

    if sub == "on":
        CONFIG["enabled"] = True
        save_config()
        schedule_all_tasks()
        await autospeak_cmd.finish("✅ 自动发言功能已开启。")

    elif sub == "off":
        CONFIG["enabled"] = False
        save_config()
        clear_jobs()
        await autospeak_cmd.finish("✅ 自动发言功能已关闭。")

    elif sub == "reload":
        load_config()
        schedule_all_tasks()
        await autospeak_cmd.finish("✅ 配置已重新加载并应用。")

    elif sub == "list":
        tasks = CONFIG.get("tasks", [])
        if not tasks:
            await autospeak_cmd.finish("当前没有任何定时任务。")
        lines = []
        for t in tasks:
            if t.get("kind") == "once":
                lines.append(
                    f"- id: {t.get('id')}  [一次性]\n"
                    f"  type: {t.get('type')}  target: {t.get('target_id')}\n"
                    f"  fire at: {t.get('datetime')}\n"
                    f"  messages: {len(t.get('messages') or [])} 条"
                )
            else:
                wds = t.get("weekdays")
                lines.append(
                    f"- id: {t.get('id')}  [循环]\n"
                    f"  type: {t.get('type')}  target: {t.get('target_id')}\n"
                    f"  time: {t.get('time')}  weekdays: {format_weekdays(wds)}\n"
                    f"  messages: {len(t.get('messages') or [])} 条"
                )
        await autospeak_cmd.finish("当前定时任务如下：\n" + "\n".join(lines))

    elif sub == "del":
        if len(parts) < 2:
            await autospeak_cmd.finish(
                "用法：autospk del <task_id>\n(task_id 为 list 里看到的整形 ID)"
            )

        try:
            task_id = int(parts[1])
        except ValueError:
            await autospeak_cmd.finish("task_id 必须为整数，请从 autospk list 中复制。")

        tasks = CONFIG.get("tasks", [])
        new_tasks = [t for t in tasks if int(t.get("id")) != task_id]
        if len(new_tasks) == len(tasks):
            await autospeak_cmd.finish(f"未找到任务 id = {task_id}。")
        CONFIG["tasks"] = new_tasks
        save_config()
        try:
            scheduler.remove_job(f"autospeak_{task_id}")
        except Exception:
            pass
        await autospeak_cmd.finish(f"✅ 任务 {task_id} 已删除。")

    elif sub == "add":
        # 支持 days= 指定星期几，缺省每天
        if len(parts) < 5:
            await autospeak_cmd.finish(
                "用法：\n"
                "  autospk add <group|private> <target_id|here|me> <HH:MM> <msg1>|<msg2>|... [days=...]\n"
                "示例（每天）：\n"
                "  autospk add group here 09:00 早上好呀|大家早上好！|起床啦~\n"
                "示例（工作日）：\n"
                "  autospk add group here 09:00 早上好，上班啦 days=workday\n"
                "示例（周一、周三、周五）：\n"
                "  autospk add group here 09:00 早上好呀 days=1,3,5\n"
                "提示：任务 ID 将自动生成为整形，无需手动指定。"
            )

        ttype = parts[1].lower()
        raw_target = parts[2]
        time_str = parts[3]

        days_spec = None
        tail = None
        if len(parts) >= 6 and parts[-1].lower().startswith("days="):
            days_spec = parts[-1][5:]
            tail = parts[-1]
        raw_msgs = await rebuild_content_from_message(arg, args_text_prefix(text, 4))
        if tail:
            raw_msgs = re.sub(r"\s+" + re.escape(tail) + r"$", "", raw_msgs)

        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            await autospeak_cmd.finish(
                "时间格式错误，请使用 24 小时制 HH:MM，例如 09:00 或 21:30。"
            )

        # here/me 解析为当前会话 ID
        target_id = None
        if isinstance(event, GroupMessageEvent):
            if raw_target.lower() in ("here", "this"):
                target_id = event.group_id
        if isinstance(event, PrivateMessageEvent):
            if raw_target.lower() == "me":
                target_id = event.user_id

        if target_id is None:
            try:
                target_id = int(raw_target)
            except ValueError:
                await autospeak_cmd.finish(
                    "目标 ID 解析失败，请使用数字，或在群里用 here，在私聊用 me。"
                )

        if ttype not in ("group", "private"):
            await autospeak_cmd.finish("第一个参数必须是 group 或 private。")

        messages = [m.strip() for m in raw_msgs.split("|") if m.strip()]
        if not messages:
            await autospeak_cmd.finish("至少需要一条非空的消息内容。")

        # 未提供 days= 时默认每天
        try:
            weekdays = parse_weekdays(days_spec)
        except Exception:
            await autospeak_cmd.finish(
                "days= 参数解析失败，请使用：\n"
                "  - 不写：默认每天\n"
                "  - days=workday / days=wd      => 周一~周五\n"
                "  - days=1,3,5                  => 周一、周三、周五\n"
                "  - days=mon,tue,fri            => 周一、周二、周五\n"
                "  - days=* / all / everyday     => 每天"
            )

        task_id = int(CONFIG.get("next_id", 1))
        CONFIG["next_id"] = task_id + 1

        new_task = {
            "id": task_id,
            "type": ttype,
            "target_id": target_id,
            "time": time_str,
            "messages": messages,
            "weekdays": weekdays,
        }
        tasks = CONFIG.get("tasks", [])
        tasks.append(new_task)
        CONFIG["tasks"] = tasks
        save_config()

        if CONFIG.get("enabled", False):
            schedule_task(new_task)

        await autospeak_cmd.finish(
            "✅ 已添加定时任务：\n"
            f"  id: {task_id}\n"
            f"  type: {ttype}\n"
            f"  target: {target_id}\n"
            f"  time: {time_str}\n"
            f"  weekdays: {format_weekdays(weekdays)}\n"
            f"  messages: {len(messages)} 条"
        )

    elif sub == "addonce":
        # 一次性任务，到点触发后自动删除
        if len(parts) < 6:
            await autospeak_cmd.finish(
                "用法：\n"
                "  autospk addonce <group|private> <target_id|here|me> <YYYY-MM-DD> <HH:MM> <msg1>|<msg2>|...\n"
                "示例：\n"
                "  autospk addonce group here 2026-06-01 09:00 早上好|早安~\n"
                "  autospk addonce private me  2026-12-31 23:59 新年快乐！\n"
                "说明：仅触发一次，到达指定时刻后任务会自动删除。"
            )

        ttype = parts[1].lower()
        raw_target = parts[2]
        date_str = parts[3]
        time_str = parts[4]
        raw_msgs = await rebuild_content_from_message(arg, args_text_prefix(text, 5))

        if ttype not in ("group", "private"):
            await autospeak_cmd.finish("第一个参数必须是 group 或 private。")

        dt_str = f"{date_str} {time_str}"
        try:
            run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            await autospeak_cmd.finish(
                "日期/时间格式错误，请使用：\n"
                "  日期：YYYY-MM-DD（如 2026-06-01）\n"
                "  时间：HH:MM 24 小时制（如 09:30）"
            )

        if run_date <= datetime.now():
            await autospeak_cmd.finish(
                f"指定时间 {dt_str} 已经过去，请使用未来时间。"
            )

        # here/me 解析为当前会话 ID
        target_id = None
        if isinstance(event, GroupMessageEvent):
            if raw_target.lower() in ("here", "this"):
                target_id = event.group_id
        if isinstance(event, PrivateMessageEvent):
            if raw_target.lower() == "me":
                target_id = event.user_id

        if target_id is None:
            try:
                target_id = int(raw_target)
            except ValueError:
                await autospeak_cmd.finish(
                    "目标 ID 解析失败，请使用数字，或在群里用 here，在私聊用 me。"
                )

        messages = [m.strip() for m in raw_msgs.split("|") if m.strip()]
        if not messages:
            await autospeak_cmd.finish("至少需要一条非空的消息内容。")

        task_id = int(CONFIG.get("next_id", 1))
        CONFIG["next_id"] = task_id + 1

        new_task = {
            "id": task_id,
            "kind": "once",
            "type": ttype,
            "target_id": target_id,
            "datetime": dt_str,
            "messages": messages,
        }
        tasks = CONFIG.get("tasks", [])
        tasks.append(new_task)
        CONFIG["tasks"] = tasks
        save_config()

        if CONFIG.get("enabled", False):
            schedule_task(new_task)

        await autospeak_cmd.finish(
            "✅ 已添加一次性任务：\n"
            f"  id: {task_id}\n"
            f"  type: {ttype}\n"
            f"  target: {target_id}\n"
            f"  fire at: {dt_str}\n"
            f"  messages: {len(messages)} 条\n"
            "（仅触发一次，到点后自动删除）"
        )

    elif sub == "edit":
        # 支持 time / datetime / msg 三种编辑模式
        if len(parts) < 4:
            await autospeak_cmd.finish(
                "编辑任务用法：\n"
                "  autospk edit time     <id> <HH:MM>                   修改循环任务时间\n"
                "  autospk edit datetime <id> <YYYY-MM-DD> <HH:MM>      修改一次性任务时间\n"
                "  autospk edit msg      <id> <msg1>|<msg2>|...         替换任务消息列表\n"
                "示例：\n"
                "  autospk edit time 1 08:30\n"
                "  autospk edit datetime 2 2026-06-01 09:00\n"
                "  autospk edit msg 1 新早安1|新早安2"
            )

        mode = parts[1].lower()
        try:
            task_id = int(parts[2])
        except ValueError:
            await autospeak_cmd.finish("task_id 必须为整数，请从 autospk list 中复制。")

        tasks = CONFIG.get("tasks", [])
        task = next((t for t in tasks if int(t.get("id")) == task_id), None)
        if not task:
            await autospeak_cmd.finish(f"未找到任务 id = {task_id}。")

        if mode == "time":
            if task.get("kind") == "once":
                await autospeak_cmd.finish(
                    f"任务 {task_id} 是一次性任务，请使用：\n"
                    f"  autospk edit datetime {task_id} <YYYY-MM-DD> <HH:MM>"
                )
            if len(parts) < 4:
                await autospeak_cmd.finish("用法：autospk edit time <id> <HH:MM>")
            new_time = parts[3]
            try:
                datetime.strptime(new_time, "%H:%M")
            except ValueError:
                await autospeak_cmd.finish(
                    "时间格式错误，请使用 24 小时制 HH:MM，例如 09:00 或 21:30。"
                )

            task["time"] = new_time
            save_config()

            if CONFIG.get("enabled", False):
                schedule_task(task)

            await autospeak_cmd.finish(
                "✅ 任务时间已修改：\n"
                f"  id: {task_id}\n"
                f"  new time: {new_time}\n"
                f"  weekdays: {format_weekdays(task.get('weekdays'))}"
            )

        elif mode == "datetime":
            if task.get("kind") != "once":
                await autospeak_cmd.finish(
                    f"任务 {task_id} 是循环任务，请使用：\n"
                    f"  autospk edit time {task_id} <HH:MM>"
                )
            if len(parts) < 5:
                await autospeak_cmd.finish(
                    "用法：autospk edit datetime <id> <YYYY-MM-DD> <HH:MM>"
                )
            date_str = parts[3]
            time_str = parts[4]
            dt_str = f"{date_str} {time_str}"
            try:
                run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except ValueError:
                await autospeak_cmd.finish(
                    "日期/时间格式错误，请使用 YYYY-MM-DD HH:MM，例如 2026-06-01 09:30。"
                )
            if run_date <= datetime.now():
                await autospeak_cmd.finish(
                    f"指定时间 {dt_str} 已经过去，请使用未来时间。"
                )

            task["datetime"] = dt_str
            save_config()

            if CONFIG.get("enabled", False):
                schedule_task(task)

            await autospeak_cmd.finish(
                "✅ 一次性任务时间已修改：\n"
                f"  id: {task_id}\n"
                f"  fire at: {dt_str}"
            )

        elif mode in ("msg", "message", "messages"):
            if len(parts) < 4:
                await autospeak_cmd.finish(
                    "用法：autospk edit msg <id> <msg1>|<msg2>|..."
                )

            raw_msgs = await rebuild_content_from_message(
                arg, args_text_prefix(text, 3)
            )
            messages = [m.strip() for m in raw_msgs.split("|") if m.strip()]
            if not messages:
                await autospeak_cmd.finish("至少需要一条非空的消息内容。")

            task["messages"] = messages
            save_config()

            await autospeak_cmd.finish(
                "✅ 任务消息已修改：\n"
                f"  id: {task_id}\n"
                f"  messages: {len(messages)} 条"
            )

        else:
            await autospeak_cmd.finish(
                "未知 edit 类型，请使用：\n"
                "  autospk edit time     <id> <HH:MM>\n"
                "  autospk edit datetime <id> <YYYY-MM-DD> <HH:MM>\n"
                "  autospk edit msg      <id> <msg1>|<msg2>|..."
            )

    elif sub in ("placeholders", "ph"):
        await autospeak_cmd.finish(PLACEHOLDERS_HELP)

    elif sub == "preview":
        sample = text[len("preview"):].strip()
        if not sample:
            await autospeak_cmd.finish(
                "用法：autospk preview <文本>\n"
                "示例：autospk preview 距离{days_until:2026-06-07}天"
            )
        await autospeak_cmd.finish(f"渲染结果：\n{render_placeholders(sample)}")

    else:
        await autospeak_cmd.finish("未知子命令，请使用 autospk 查看帮助。")
