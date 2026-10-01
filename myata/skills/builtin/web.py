"""Search the web or YouTube in the browser."""

from __future__ import annotations

from urllib.parse import quote_plus

from myata.skills.base import SkillContext, SkillResult
from myata.skills.registry import skill

SEARCH_URLS = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
}


@skill(
    name="web_search",
    description=(
        "Search for something on the internet or on YouTube and open the results "
        "in the browser. Use it when the user asks to find, google or look up something."
    ),
    phrases=[],  # needs a query, so only the LLM can call it
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search words exactly as the user said them, in the same language. "
                    "Do not translate, expand or explain them and do not add the site name."
                ),
            },
            "site": {
                "type": "string",
                "enum": ["google", "youtube"],
                "description": "youtube for videos and music, google for everything else",
            },
        },
        "required": ["query"],
    },
)
def web_search(ctx: SkillContext) -> SkillResult:
    query = ctx.args["query"]
    site = ctx.args.get("site", "google")
    if not ctx.os.open_url(SEARCH_URLS[site].format(quote_plus(query))):
        return SkillResult(ctx.config.assistant.phrases.failed, ok=False)
    where = "на ютубе " if site == "youtube" else ""
    return SkillResult(f"Ищу {where}{query}")
