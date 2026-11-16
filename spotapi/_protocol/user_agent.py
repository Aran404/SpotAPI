"""Parse browser metadata from the supplied Go port of Spotify's JavaScript packs.

The ordered matching rules come from the supplied port. Parsing is local and
synchronous. The async session owns the requests that consume the metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

WEB_PLAYER_MODEL = "web_player"


@dataclass(frozen=True, slots=True)
class BrowserInfo:
    name: str = ""
    version: str = ""


@dataclass(frozen=True, slots=True)
class OSInfo:
    name: str = ""
    version: str = ""


@dataclass(frozen=True, slots=True)
class UserAgent:
    browser: BrowserInfo
    os: OSInfo
    platform: str
    engine: BrowserInfo

    @property
    def platform_identifier(self) -> str:
        """Return the web-player identifier used for a desktop registration."""
        os_name = _OS_ALIASES.get(self.os.name, self.os.name)
        os_version = self.os.version
        if self.os.name == "Windows":
            os_version = _WINDOWS_VERSIONS.get(os_version, "")

        browser = self.browser
        return (
            f"{WEB_PLAYER_MODEL} {os_name} {os_version};{browser.name} {browser.version};desktop"
        ).lower()

    @property
    def platform_name(self) -> str:
        return f"Web Player ({self.browser.name})"


@dataclass(frozen=True, slots=True)
class _Rule:
    name: str
    test: re.Pattern[str]
    versions: tuple[re.Pattern[str], ...]


def _rule(name: str, test: str, *versions: str) -> _Rule:
    return _Rule(name, re.compile(test, re.DOTALL), tuple(map(re.compile, versions)))


def _identify(value: str, rules: tuple[_Rule, ...]) -> BrowserInfo:
    for rule in rules:
        if not rule.test.search(value):
            continue

        for pattern in rule.versions:
            if match := pattern.search(value):
                return BrowserInfo(rule.name, match[1])

        return BrowserInfo(rule.name)

    return BrowserInfo()


@lru_cache(maxsize=128)
def parse_user_agent(value: str) -> UserAgent:
    """Classify the user-agent string with the source port's precedence."""
    if not value:
        raise ValueError("User agent cannot be empty")

    os = _identify(value, _OS)
    os_version = os.version.replace("_", ".") if os.name in {"iOS", "macOS"} else os.version

    return UserAgent(
        browser=_identify(value, _BROWSERS),
        os=OSInfo(os.name, os_version),
        platform=_identify(value, _PLATFORMS).name or "desktop",
        engine=_identify(value, _ENGINES),
    )


_OS_ALIASES = {"macOS": "osx", "Chrome OS": "chrome"}
_WINDOWS_VERSIONS = {
    "NT": "NT",
    "XP": "XP",
    "NT 5.0": "2000",
    "NT 5.1": "XP",
    "NT 5.2": "2003",
    "NT 6.0": "Vista",
    "NT 6.1": "7",
    "NT 6.2": "8",
    "NT 6.3": "8.1",
    "NT 10.0": "10",
}


_BROWSERS = (
    _rule("AmazonBot", "(?i)Amazonbot", "(?i)Amazonbot/([0-9.]+)"),
    _rule("ClaudeBot", "(?i)ClaudeBot", "(?i)ClaudeBot/([0-9.]+)"),
    _rule("GPTBot", "(?i)GPTBot", "(?i)GPTBot/([0-9.]+)"),
    _rule("ChatGPT-User", "(?i)ChatGPT-User", "(?i)ChatGPT-User/([0-9.]+)"),
    _rule("OAI-SearchBot", "(?i)OAI-SearchBot"),
    _rule("PerplexityBot", "(?i)PerplexityBot"),
    _rule("Perplexity-User", "(?i)Perplexity-User"),
    _rule("Googlebot", "(?i)Googlebot", "(?i)Googlebot/([0-9.]+)"),
    _rule("BingCrawler", "(?i)bingbot", "(?i)bingbot/([0-9.]+)"),
    _rule("BaiduSpider", "(?i)Baiduspider"),
    _rule("YandexBot", "(?i)YandexBot", "(?i)YandexBot/([0-9.]+)"),
    _rule("DuckDuckBot", "(?i)DuckDuckBot"),
    _rule("FacebookExternalHit", "(?i)facebookexternalhit"),
    _rule("InternetArchiveCrawler", "(?i)ia_archiver"),
    _rule("Samsung Internet for Android", "SamsungBrowser", "SamsungBrowser/([0-9.]+)"),
    _rule("UC Browser", "UCBrowser|UCWEB", "UCBrowser/([0-9.]+)", "UCWEB([0-9.]+)"),
    _rule(
        "Microsoft Edge", "Edg/|EdgA/|Edge/", "Edg/([0-9.]+)", "EdgA/([0-9.]+)", "Edge/([0-9.]+)"
    ),
    _rule("Opera", "OPR/|Opera", "OPR/([0-9.]+)", "Opera/([0-9.]+)", "Version/([0-9.]+)"),
    _rule("Opera Coast", "Coast/", "Coast/([0-9.]+)"),
    _rule("NAVER Whale Browser", "Whale/", "Whale/([0-9.]+)"),
    _rule("Electron", "Electron/", "Electron/([0-9.]+)"),
    _rule("Vivaldi", "Vivaldi/", "Vivaldi/([0-9.]+)"),
    _rule("Yandex Browser", "YaBrowser/", "YaBrowser/([0-9.]+)"),
    _rule("Amazon Silk", "Silk/", "Silk/([0-9._]+)"),
    _rule("WeChat", "MicroMessenger/", "MicroMessenger/([0-9.]+)"),
    _rule("QQ", "QQBrowser/", "QQBrowser/([0-9.]+)"),
    _rule("Puffin", "Puffin/", "Puffin/([0-9.]+)"),
    _rule("Sogou Browser", "MetaSr|Sogou", "(?:SE|SogouMobileBrowser)/([0-9.]+)"),
    _rule("Maxthon", "Maxthon/", "Maxthon/([0-9.]+)"),
    _rule("PhantomJS", "PhantomJS/", "PhantomJS/([0-9.]+)"),
    _rule("Epiphany", "Epiphany/", "Epiphany/([0-9.]+)"),
    _rule("Focus", "Focus/", "Focus/([0-9.]+)"),
    _rule("SeaMonkey", "SeaMonkey/", "SeaMonkey/([0-9.]+)"),
    _rule("LibreWolf", "LibreWolf/", "LibreWolf/([0-9.]+)"),
    _rule("Pale Moon", "PaleMoon/", "PaleMoon/([0-9.]+)"),
    _rule("Firefox", "Firefox/", "Firefox/([0-9.]+)"),
    _rule("Chromium", "Chromium/", "Chromium/([0-9.]+)"),
    _rule(
        "Chrome",
        "\\A(?!.*(?:OPR/|Opera|Edg/|EdgA/|Edge/|SamsungBrowser|Silk/|Electron/|Whale/|YaBrowser/|UCBrowser|Chromium/)).*Chrome/",
        "Chrome/([0-9.]+)",
    ),
    _rule("Internet Explorer", "MSIE |Trident/", "MSIE ([0-9.]+)", "rv:([0-9.]+)"),
    _rule("Android Browser", "\\A(?!.*Chrome)(?=.*Android).*AppleWebKit", "Version/([0-9.]+)"),
    _rule(
        "Safari",
        "\\A(?!.*(?:Chrome/|Chromium/|OPR/|Opera|Edg/|EdgA/|Edge/|SamsungBrowser|Silk/|Electron/|Whale/|YaBrowser/|UCBrowser|Android)).*Safari",
        "Version/([0-9.]+)",
        "Safari/([0-9.]+)",
    ),
    _rule("BlackBerry", "BlackBerry|BB10", "BlackBerry[0-9a-z]+/([0-9.]+)", "Version/([0-9.]+)"),
    _rule("Roku", "Roku/DVP", "Roku/DVP-([0-9.]+)"),
    _rule("Tizen", "Tizen/", "Tizen/([0-9.]+)"),
    _rule("Bada", "Dolfin/", "Dolfin/([0-9.]+)"),
    _rule("Sailfish", "Sailfish", "Sailfish/([0-9.]+)"),
    _rule("WebOS Browser", "webOS|hpwOS", "(?:web|hpw)OS/([0-9.]+)"),
    _rule("Google Search", "GSA/", "GSA/([0-9.]+)"),
    _rule("Omgilibot", "(?i)Omgilibot"),
    _rule("PingdomBot", "(?i)Pingdom"),
    _rule("YahooSlurp", "(?i)Slurp"),
    _rule("YouBot", "(?i)YoudaoBot|YouBot"),
    _rule("Diffbot", "(?i)Diffbot"),
    _rule("Meta-ExternalAgent", "(?i)meta-externalagent"),
    _rule("Meta-ExternalFetcher", "(?i)meta-externalfetcher"),
)

_OS = (
    _rule("Windows Phone", "Windows Phone", "Windows Phone (?:OS )?([0-9.]+)"),
    _rule(
        "Windows",
        "Windows",
        "Windows (NT [0-9.]+|XP|ME|CE|9[58]|3\\.1[1]?)",
        "Win(?:dows)?[ /]?([0-9a-zA-Z.]+)",
    ),
    _rule("iOS", "iP(?:hone|ad|od)", "CPU (?:iPhone )?OS ([0-9_]+)"),
    _rule(
        "macOS",
        "Macintosh|MacIntel|MacPPC|Mac68K|Mac OS X|macOS",
        "Mac OS X ([0-9_\\.]+)",
        "macOS ([0-9_\\.]+)",
    ),
    _rule("Android", "Android", "Android ([0-9.]+)"),
    _rule("HarmonyOS", "HarmonyOS", "HarmonyOS ([0-9.]+)"),
    _rule("Chrome OS", "CrOS", "CrOS [a-z0-9_]+ ([0-9.]+)"),
    _rule("PlayStation 4", "PlayStation 4", "PlayStation 4/([0-9.]+)"),
    _rule("Roku", "Roku", "Roku/DVP-([0-9.]+)"),
    _rule("Tizen", "Tizen", "Tizen ([0-9.]+)"),
    _rule("WebOS", "webOS|hpwOS", "(?:web|hpw)OS/([0-9.]+)"),
    _rule(
        "BlackBerry", "BlackBerry|BB10", "BlackBerry(?:[0-9a-z]+)?/([0-9.]+)", "Version/([0-9.]+)"
    ),
    _rule("Bada", "Bada/", "Bada/([0-9.]+)"),
    _rule("Linux", "\\A(?!.*Android).*Linux"),
)

_PLATFORMS = (
    _rule(
        "bot",
        "(?i)bot|spider|crawl|slurp|archiver|pingdom|validator|checker|fetcher|agent|scanner|monitor|Googlebot|bingbot|YandexBot|BaiduSpider|DuckDuckBot|facebookexternalhit|Diffbot|ia_archiver|Omgilibot|GPTBot|ClaudeBot|ChatGPT|OAI-Search|Perplexity|AmazonBot|YouBot",
    ),
    _rule(
        "tv",
        "(?i)Roku|PlayStation|SmartTV|SMART-TV|AppleTV|GoogleTV|HbbTV|BRAVIA|Tizen.*TV|Web0S.*TV|NetCast|WebOS.*TV",
    ),
    _rule("tablet", "iPad|(?i:Tablet|Kindle|Silk|GT-P|SCH-I|SM-T|Tab|Nexus 7|Nexus 10)"),
    _rule(
        "mobile",
        "(?i)\\A(?!.*(?-i:Kindle Fire)).*(?:iPhone|Android.*Mobile|BlackBerry|IEMobile|Windows Phone|webOS|Symbian|Nokia|Opera Mini|Opera Mobi|Fennec|Maemo|Bada|BREW)",
    ),
)

_ENGINES = (
    _rule("EdgeHTML", "Edge/", "Edge/([0-9.]+)"),
    _rule("Trident", "Trident/", "Trident/([0-9.]+)"),
    _rule("Presto", "Presto/", "Presto/([0-9.]+)"),
    _rule("Gecko", "Gecko/", "rv:([0-9.]+)"),
    _rule("Blink", "\\A(?=.*Chrome/).*AppleWebKit/", "Chrome/([0-9.]+)"),
    _rule("WebKit", "AppleWebKit/", "AppleWebKit/([0-9.]+)"),
)
