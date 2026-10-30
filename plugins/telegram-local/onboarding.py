"""One public instruction shared by installation and authorization failures."""

from pathlib import Path

AUTH_INSTRUCTIONS = (
    Path(__file__).with_name("onboarding.md").read_text(encoding="utf-8").strip()
)


def auth_configured(state):
    return bool(state.get("credentials") and state.get("session"))
