"""Check the browser precedence and wire identifiers used by Spotify."""

import pytest
import wreq

from spotapi._protocol.user_agent import parse_user_agent
from spotapi.connection import HTTPClient


@pytest.mark.parametrize(
    ("header", "browser", "os_name", "os_version", "platform", "identifier"),
    [
        (
            "Windows NT 10.0 AppleWebKit/537.36 Chrome/136.0 Safari/537.36 Edg/136.0",
            "Microsoft Edge",
            "Windows",
            "NT 10.0",
            "desktop",
            "web_player windows 10;microsoft edge 136.0;desktop",
        ),
        (
            "iPad CPU OS 17_4 AppleWebKit/605.1.15 Version/17.4 Safari/604.1",
            "Safari",
            "iOS",
            "17.4",
            "tablet",
            "web_player ios 17.4;safari 17.4;desktop",
        ),
        (
            "CrOS x86_64 15572.4.0 Chrome/126.0 AppleWebKit/537.36",
            "Chrome",
            "Chrome OS",
            "15572.4.0",
            "desktop",
            "web_player chrome 15572.4.0;chrome 126.0;desktop",
        ),
    ],
)
def test_user_agent_metadata(
    header: str,
    browser: str,
    os_name: str,
    os_version: str,
    platform: str,
    identifier: str,
) -> None:
    agent = parse_user_agent(header)

    assert agent.browser.name == browser
    assert (agent.os.name, agent.os.version) == (os_name, os_version)
    assert agent.platform == platform
    assert agent.platform_identifier == identifier
    assert agent.platform_name == f"Web Player ({browser})"


@pytest.mark.parametrize(
    ("profile", "browser"),
    [
        (wreq.Profile.Chrome147, "Chrome"),
        (wreq.Profile.Firefox149, "Firefox"),
        (wreq.Profile.Opera130, "Opera"),
    ],
)
async def test_transport_reads_the_generated_profile_header(
    profile: wreq.Profile, browser: str
) -> None:
    emulation = wreq.Emulation(profile=profile, platform=wreq.Platform.Windows)

    async with HTTPClient(emulation=emulation) as client:
        header = await client.profile_user_agent()
        assert await client.profile_user_agent() == header

    agent = parse_user_agent(header)
    assert agent.browser.name == browser
    assert agent.os.name == "Windows"


async def test_transport_rejects_a_conflicting_user_agent_override() -> None:
    async with HTTPClient(user_agent="Custom test client") as client:
        with pytest.raises(ValueError, match="Remove the User-Agent override"):
            await client.profile_user_agent()
