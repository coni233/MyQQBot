import random
import re

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import ArgStr, CommandArg, Depends

roll = on_command("rd", aliases={"roll", "掷骰"}, priority=10)


async def get_rd(matcher: Matcher, args: str = ArgStr("rd")) -> None:
    arg = args.strip().split()

    if arg and len(arg) > 0:
        if len(arg) > 1:
            await matcher.send("参数过多，仅第一个参数有效")

        matcher.set_arg("rd", arg[0])  # type: ignore
    else:
        await matcher.reject_arg("rd", "你还没掷骰子呢：[x]d[y]")


@roll.handle()
async def _(matcher: Matcher, args: Message = CommandArg()) -> None:
    arg = args.extract_plain_text().strip().split()

    if arg and len(arg) > 0:
        if len(arg) > 1:
            await matcher.send("参数过多，仅第一个参数有效")

        matcher.set_arg("rd", arg[0])  # type: ignore


@roll.got("rd", prompt="你还没掷骰子呢：rd [x]d[y]", parameterless=[Depends(get_rd)])
async def _(matcher: Matcher, event: MessageEvent):
    dice_num, dice_side = 0, 0

    _roll = matcher.get_arg("rd", None)

    if not _roll:
        # Never reach
        await matcher.finish("缺少参数！")

    roll_str = str(_roll)

    if re.match(r"^((\-|\+)?\d+)?[d]\d+$", roll_str):
        # <x>d<y>, where x can be > 0 and < 0.
        # d<y>, where x = 1.
        dice_info = roll_str.split("d")
        if dice_info[0] == "":
            dice_num, dice_side = 1, int(dice_info[1])
        else:
            dice_num, dice_side = int(dice_info[0]), int(dice_info[1])

    else:
        await matcher.finish("格式不对呢, 请重新输入: rd [x]d[y]")

    # Bonus
    if dice_num > 999 or dice_side > 999:
        await matcher.finish("错误！谁没事干扔那么多骰子啊😅")

    if dice_num <= 0 or dice_side <= 0:
        await matcher.finish("错误！你掷出了不存在的骰子, 只有上帝知道结果是多少🤔")

    if (dice_num == 114 and dice_side == 514) or (dice_num == 514 and dice_side == 114):
        await matcher.finish("恶臭！奇迹和魔法可不是免费的！🤗")

    if random.randint(1, 100) == 99:
        await matcher.finish("彩蛋！骰子之神似乎不看好你, 你掷出的骰子全部消失了😥")

    _bonus = random.randint(1, 1000)
    bonus = 0
    if _bonus % 111 == 0:
        bonus = _bonus
        await matcher.send(f"彩蛋！你掷出的点数将增加【{bonus}】")

    # 投掷骰子，并记录每颗骰子的结果
    dice_results = []

    for _ in range(dice_num):
        result = random.randint(1, dice_side)
        dice_results.append(result)

    # 计算总点数
    dice_result = sum(dice_results) + bonus

    if dice_result == 773:
        await matcher.send("彩蛋！nana7mi祝大家新年快乐！")

    dice_text = " ".join(f"[{result}]" for result in dice_results)

    # 获取发送者 QQ 昵称
    nickname = (
        getattr(event.sender, "card", None)
        or event.sender.nickname
        or str(event.user_id)
    )

    await matcher.finish(
        f"🎲 {nickname} 投出了 {dice_num} 个 {dice_side} 面骰子\n"
        f"{dice_text}\n"
        f"总点数：{dice_result}"
    )

