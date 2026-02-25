import logging

from playwright.async_api import Page

from core.scraper.browser import StealthBrowser

logger = logging.getLogger(__name__)

LOGIN_INDICATORS = [
    "input[type='password']",
    "[name='login']",
    "[name='signin']",
    "[href*='/login']",
    "[href*='/signin']",
    "[aria-label*='log in' i]",
    "[aria-label*='sign in' i]",
]

PLATFORM_LOGIN_SELECTORS: dict[str, dict] = {
    "twitter": {
        "url": "https://x.com/i/flow/login",
        "username_selector": "input[autocomplete='username']",
        "password_selector": "input[type='password']",
        "submit_selector": "[data-testid='LoginForm_Login_Button']",
    },
    "instagram": {
        "url": "https://www.instagram.com/accounts/login/",
        "username_selector": "input[name='username']",
        "password_selector": "input[name='password']",
        "submit_selector": "button[type='submit']",
    },
    "github": {
        "url": "https://github.com/login",
        "username_selector": "#login_field",
        "password_selector": "#password",
        "submit_selector": "input[type='submit']",
    },
    "reddit": {
        "url": "https://www.reddit.com/login/",
        "username_selector": "#loginUsername",
        "password_selector": "#loginPassword",
        "submit_selector": "button[type='submit']",
    },
    "steam": {
        "url": "https://store.steampowered.com/login/",
        "username_selector": "#input_username",
        "password_selector": "#input_password",
        "submit_selector": "#login_btn_signin button",
    },
}


async def detect_login_wall(page: Page) -> bool:
    """Check if the current page is behind a login wall."""
    for selector in LOGIN_INDICATORS:
        try:
            element = await page.query_selector(selector)
            if element:
                return True
        except Exception:
            continue
    return False


async def attempt_login(
    browser: StealthBrowser,
    platform_name: str,
) -> Page | None:
    """
    Attempt to log in to a platform using a BurnerAccount credential.
    Returns an authenticated Page on success, None on failure.
    """
    from core.models import BurnerAccount

    selectors = PLATFORM_LOGIN_SELECTORS.get(platform_name)
    if not selectors:
        logger.warning("No login selectors defined for '%s'", platform_name)
        return None

    credential = await _get_burner_account(platform_name)
    if not credential:
        logger.warning("No active BurnerAccount for '%s'", platform_name)
        return None

    page = await browser.new_page()
    try:
        await page.goto(selectors["url"], wait_until="domcontentloaded", timeout=15000)
        await browser.random_delay(1.5, 3.0)

        await page.fill(selectors["username_selector"], credential.username)
        await browser.random_delay(0.5, 1.5)

        await page.fill(selectors["password_selector"], credential.password)
        await browser.random_delay(0.5, 1.2)

        await page.click(selectors["submit_selector"])
        await page.wait_for_load_state("networkidle", timeout=15000)

        if await detect_login_wall(page):
            logger.warning("Login failed for '%s'", platform_name)
            await page.close()
            return None

        logger.info("Login successful for '%s'", platform_name)
        return page

    except Exception as exc:
        logger.error("Login attempt raised for '%s': %s", platform_name, exc)
        await page.close()
        return None


async def _get_burner_account(platform_name: str):
    """Fetch an active BurnerAccount for a platform (sync ORM via thread)."""
    import asyncio

    def _query():
        from core.models import BurnerAccount
        return BurnerAccount.objects.filter(
            platform_name=platform_name,
            is_active=True,
        ).first()

    return await asyncio.to_thread(_query)
