"""Build skills from the sites, apps and scenes listed in config.yaml."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from myata.config import AppConfig, Config, SceneConfig, SceneStep, SiteConfig
from myata.oslayer import MEDIA, VOLUME, LaunchError, OSActionError
from myata.skills.base import Skill, SkillContext, SkillResult

log = logging.getLogger(__name__)


def make_site_skill(site: SiteConfig) -> Skill:
    def handler(ctx: SkillContext) -> SkillResult:
        if ctx.os.open_url(site.url):
            return SkillResult(site.reply)
        log.warning("Could not open %s", site.url)
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)

    return Skill(
        name=f"open_{site.name}",
        description=site.description or f"Open {site.url} in the browser",
        phrases=site.phrases,
        handler=handler,
    )


def make_app_skill(app: AppConfig, argv: Sequence[str], os_name: str) -> Skill:
    def handler(ctx: SkillContext) -> SkillResult:
        try:
            ctx.os.launch(argv)
        except LaunchError as e:
            log.warning("Could not launch %s: %s", app.name, e)
            return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
        return SkillResult(app.reply)

    return Skill(
        name=f"launch_{app.name}",
        description=app.description or f"Launch the {app.name} application",
        phrases=app.phrases,
        handler=handler,
        platforms=frozenset({os_name}),
    )


def make_scene_skill(
    scene: SceneConfig, config: Config, os_name: str, capabilities: frozenset[str] | None
) -> Skill | None:
    """A scene runs several steps with one phrase, like "игровой режим".

    Steps that cannot work here (an app without a command for this OS, volume
    without a volume tool) are dropped. A scene with no steps left is skipped.
    """
    apps = {app.name: app.commands.get(os_name) for app in config.apps}
    sites = {site.name: site.url for site in config.sites}

    def available(step: SceneStep) -> bool:
        if step.launch is not None:
            return apps.get(step.launch) is not None
        if step.volume is not None:
            return capabilities is None or VOLUME in capabilities
        if step.media is not None:
            return capabilities is None or MEDIA in capabilities
        return True

    steps = [step for step in scene.steps if available(step)]
    for step in scene.steps:
        if step not in steps:
            log.info("Scene %s: step %s does not work on %s, dropped", scene.name, step, os_name)
    if not steps:
        log.info("Scene %s has no steps for %s, skipped", scene.name, os_name)
        return None

    def run(ctx: SkillContext, step: SceneStep) -> None:
        if step.launch is not None:
            ctx.os.launch(apps[step.launch])
        elif step.open is not None:
            if not ctx.os.open_url(sites[step.open]):
                raise OSActionError(f"cannot open {sites[step.open]}")
        elif step.volume is not None:
            ctx.os.set_volume(step.volume)
        elif step.media is not None:
            ctx.os.media_key(step.media)

    def handler(ctx: SkillContext) -> SkillResult:
        failed = 0
        for step in steps:
            try:
                run(ctx, step)
            except OSActionError as e:
                log.warning("Scene %s: step %s failed: %s", scene.name, step, e)
                failed += 1
        if failed == len(steps):
            return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
        if failed:
            return SkillResult(f"{scene.reply}. Но не всё получилось, сэр.", ok=False)
        return SkillResult(scene.reply)

    return Skill(
        name=f"scene_{scene.name}",
        description=scene.description or f"Run the {scene.name} scene",
        phrases=scene.phrases,
        handler=handler,
    )
