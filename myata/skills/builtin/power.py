"""Shut down, restart or put the computer to sleep. Always asks for confirmation."""

from __future__ import annotations

import logging
import threading

from myata.oslayer import POWER, OSActionError
from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

log = logging.getLogger(__name__)


def _power(ctx: SkillContext, action: str, reply: str) -> SkillResult:
    settings = ctx.config.skills
    if settings.power_dry_run:
        log.info("Power action %s skipped: skills.power_dry_run is on", action)
        return SkillResult(f"{reply}. Это тренировка, ничего не делаю")

    def run() -> None:
        try:
            ctx.os.power(action)
        except OSActionError as e:
            log.error("Power action %s failed: %s", action, e)

    if settings.power_delay_sec <= 0:
        run()
    else:
        # A short delay, so Myata finishes saying the reply before the system goes down.
        timer = threading.Timer(settings.power_delay_sec, run)
        timer.daemon = True
        timer.start()
    return SkillResult(reply)


@skill(
    name="shutdown_computer",
    description=(
        "Shut down (turn off) the whole computer. Only when the user clearly says "
        "компьютер or ПК, never when they ask to turn off the assistant herself."
    ),
    phrases=["выключи компьютер", "выключи пк", "заверши работу компьютера"],
    requires=[POWER],
    dangerous=True,
    confirm="Выключить компьютер, сэр? Скажите да или нет.",
)
def shutdown_computer(ctx: SkillContext) -> SkillResult:
    return _power(ctx, "shutdown", "Выключаю компьютер, сэр")


@skill(
    name="restart_computer",
    description="Restart (reboot) the whole computer, only when the user says компьютер or ПК",
    phrases=["перезагрузи компьютер", "перезагрузи пк", "перезагрузка компьютера"],
    requires=[POWER],
    dangerous=True,
    confirm="Перезагрузить компьютер, сэр? Скажите да или нет.",
)
def restart_computer(ctx: SkillContext) -> SkillResult:
    return _power(ctx, "reboot", "Перезагружаю компьютер, сэр")


@skill(
    name="sleep_computer",
    description="Put the computer to sleep (спящий режим)",
    phrases=["спящий режим", "переведи компьютер в сон", "усыпи компьютер"],
    requires=[POWER],
    dangerous=True,
    confirm="Перевести компьютер в сон, сэр? Скажите да или нет.",
)
def sleep_computer(ctx: SkillContext) -> SkillResult:
    return _power(ctx, "sleep", "Перевожу компьютер в сон, сэр")
