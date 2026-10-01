"""Build skills from the sites and apps listed in config.yaml."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from myata.config import AppConfig, SiteConfig
from myata.oslayer import LaunchError
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
