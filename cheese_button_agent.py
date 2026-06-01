import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from playwright.sync_api import BrowserContext, Download, Locator, Page, TimeoutError, sync_playwright


DEFAULT_BASE_URL = "https://studio.cheesebutton.io"
LOGIN_URL = "https://auth.cheesebutton.io/signin"
STORAGE_STATE = Path(".cheesebutton_state.json")
DOWNLOAD_DIR = Path("downloads")

STUDIO_TEXT = "스튜디오"
SURVEY_TEXT = "설문"
STATUS_TEXT = "현황보기"
RESULTS_TEXT = "결과보기"
RESULT_DOWNLOAD_TEXT = "결과 다운로드"
EXCEL_DOWNLOAD_TEXT = "엑셀 다운로드"
SELECT_ALL_ITEMS_TEXT = "전체 항목 선택"
DOWNLOAD_TEXT = "다운로드"
CLOSE_TEXT = "닫기"
CHANNEL_TEXT = "전국 AI무역지원센터"
AI_CENTER_TEXT = "AI무역지원센터"
QR_GUESTBOOK_TEXT = "QR 방명록"
QUALITY_TEXT = "품질"
CUSTOMER_SERVICE_TEXT = "고객 서비스"


CENTERS = [
    "김해 AI무역지원센터 QR 방명록",
    "진주 AI무역지원센터 QR 방명록",
    "울산 AI무역지원센터 QR 방명록",
    "부산 AI무역지원센터 QR 방명록",
    "경북 AI무역지원센터 QR 방명록",
    "강원 AI무역지원센터 QR 방명록",
    "광주 AI무역지원센터 QR 방명록",
    "전남 AI무역지원센터 QR 방명록",
    "전북 AI무역지원센터 QR 방명록",
    "충남 AI무역지원센터 QR 방명록",
    "충북 AI무역지원센터 QR 방명록",
    "대전 AI무역지원센터 QR 방명록",
    "평택 AI무역지원센터 QR 방명록",
    "화성 AI무역지원센터 QR 방명록",
    "용인 AI무역지원센터 QR 방명록",
    "포천 AI무역지원센터 QR 방명록",
    "고양 AI무역지원센터 QR 방명록",
    "인천 AI무역지원센터 QR 방명록",
    "서울 AI무역지원센터 QR 방명록",
    "제주 AI무역지원센터 QR 방명록",
]


@dataclass(frozen=True)
class AgentConfig:
    base_url: str
    headless: bool
    slow_mo: int
    timeout_ms: int
    download_dir: Path
    keep_open: bool


def clean_filename(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def existing_storage_state() -> str | None:
    return str(STORAGE_STATE) if STORAGE_STATE.exists() else None


def make_context(browser, config: AgentConfig) -> BrowserContext:
    storage_state = existing_storage_state()
    return browser.new_context(
        accept_downloads=True,
        storage_state=storage_state,
        viewport={"width": 1600, "height": 1000},
        locale="ko-KR",
    )


def wait_for_network_quiet(page: Page, timeout_ms: int = 5_000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except TimeoutError:
        pass


def ensure_logged_in(page: Page, config: AgentConfig) -> None:
    if existing_storage_state():
        page.goto(config.base_url, wait_until="domcontentloaded")
        wait_for_network_quiet(page)
        if "signin" not in page.url:
            return

    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    wait_for_network_quiet(page)

    email = os.getenv("CHEESEBUTTON_EMAIL")
    password = os.getenv("CHEESEBUTTON_PASSWORD")
    if not email or not password:
        print("로그인이 필요합니다. 열린 브라우저에서 직접 로그인한 뒤 Enter를 누르세요.")
        input()
        page.context.storage_state(path=str(STORAGE_STATE))
        return

    page.locator("input[name='email']").fill(email)
    page.locator("input[name='password']").fill(password)

    submit = page.locator("button[data-testid='submit']")
    submit.wait_for(state="visible", timeout=10_000)
    page.wait_for_function(
        "selector => !document.querySelector(selector).disabled",
        arg="button[data-testid='submit']",
    )
    submit.click()
    wait_for_network_quiet(page)
    page.context.storage_state(path=str(STORAGE_STATE))
    click_studio(page)


def click_studio(page: Page) -> None:
    studio = page.get_by_text(STUDIO_TEXT, exact=True).first
    studio.wait_for(state="visible", timeout=15_000)
    studio.click()
    wait_for_network_quiet(page)
    scroll_to_bottom(page)
    print_survey_cards(collect_qr_survey_cards(page), "QR 방명록 카드 수집 완료")


def enter_channel_if_needed(page: Page) -> None:
    if "/channels" not in page.url:
        return

    channel = page.get_by_text(CHANNEL_TEXT).first
    channel.wait_for(state="visible", timeout=15_000)
    channel.click()
    wait_for_network_quiet(page)


def scroll_to_bottom(page: Page) -> None:
    last_height = -1
    stable_rounds = 0

    for _ in range(30):
        current_height = page.evaluate(
            """() => {
                const doc = document.scrollingElement || document.documentElement;
                return Math.max(doc.scrollHeight, document.body ? document.body.scrollHeight : 0);
            }"""
        )

        page.evaluate(
            """() => {
                const doc = document.scrollingElement || document.documentElement;
                doc.scrollTo(0, doc.scrollHeight);
            }"""
        )
        page.wait_for_timeout(700)

        if current_height == last_height:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= 2:
            break

        last_height = current_height


def collect_qr_survey_cards(page: Page) -> list[dict[str, str]]:
    cards = page.locator("div._1v99572_1v99574")
    total = cards.count()
    results: list[dict[str, str]] = []

    for index in range(total):
        card = cards.nth(index)
        title = extract_card_title(card)
        if not title:
            continue
        if not is_qr_survey_card(title):
            continue
        results.append({"title": title, "index": str(index)})

    return results


def collect_qr_survey_titles_from_page_text(page: Page) -> list[dict[str, str]]:
    text = page.locator("body").inner_text(timeout=5_000)
    titles: list[dict[str, str]] = []
    seen: set[str] = set()

    for line in text.splitlines():
        title = re.sub(r"\s+", " ", line).strip()
        if not title or title in seen:
            continue
        if is_qr_survey_card(title):
            seen.add(title)
            titles.append({"title": title, "index": "text"})

    return titles


def collect_visible_qr_survey_cards(page: Page) -> list[dict[str, str]]:
    cards = collect_qr_survey_cards(page)
    if cards:
        return cards
    return collect_qr_survey_titles_from_page_text(page)


def print_survey_cards(cards: list[dict[str, str]], heading: str) -> None:
    print(f"{heading}: {len(cards)}개")
    for index, card in enumerate(cards, start=1):
        print(f"[{index:02d}] {card['title']}")


def extract_card_title(card: Locator) -> str:
    title_selectors = [
        "div._1lf7asm9._1lf7asmy._1lf7asm1m._1lf7asm2b._1lf7asm3.svzt9xw._1lf7asm2y._1lf7asm35._1lf7asm0._1v9957a",
        "div._1lf7asm9",
    ]

    for selector in title_selectors:
        locator = card.locator(selector).first
        try:
            if locator.count() > 0:
                text = locator.inner_text(timeout=1000).strip()
                if text:
                    return re.sub(r"\s+", " ", text)
        except TimeoutError:
            continue

    try:
        text = card.inner_text(timeout=1000)
    except TimeoutError:
        return ""

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    for line in lines:
        if AI_CENTER_TEXT in line and (QR_GUESTBOOK_TEXT in line or QUALITY_TEXT in line):
            return line
    return ""


def is_qr_survey_card(title: str) -> bool:
    if QR_GUESTBOOK_TEXT not in title:
        return False
    if QUALITY_TEXT in title or CUSTOMER_SERVICE_TEXT in title:
        return False
    return True


def open_survey_from_card(page: Page, card_title: str) -> None:
    card = page.locator("div._1v99572_1v99574").filter(has_text=card_title).first
    card.wait_for(state="visible", timeout=10_000)
    card.get_by_text(STATUS_TEXT, exact=True).click()
    wait_for_network_quiet(page)


def fill_first_visible(page: Page, selectors: Iterable[str], value: str) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=1500):
                locator.fill(value)
                return
        except TimeoutError:
            continue
    raise RuntimeError(f"입력 필드를 찾지 못했습니다: {', '.join(selectors)}")


def click_first_visible(page: Page, selectors: Iterable[str]) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=1500):
                locator.click()
                return
        except TimeoutError:
            continue
    raise RuntimeError(f"클릭 대상을 찾지 못했습니다: {', '.join(selectors)}")


def open_survey(page: Page, title: str) -> None:
    title_locator = page.get_by_text(title, exact=True).first
    title_locator.wait_for(state="visible")

    survey_card = title_locator.locator(
        f"xpath=ancestor::*[self::div or self::article or self::li][.//*[normalize-space()='{STATUS_TEXT}']][1]"
    )
    survey_card.get_by_text(STATUS_TEXT, exact=True).click()
    page.get_by_text(RESULTS_TEXT, exact=True).first.wait_for(state="visible", timeout=15_000)


def go_to_survey_list(page: Page, config: AgentConfig) -> None:
    page.goto(config.base_url, wait_until="domcontentloaded")
    wait_for_network_quiet(page)
    enter_channel_if_needed(page)

    target = page.get_by_text(f"{AI_CENTER_TEXT} {QR_GUESTBOOK_TEXT}").first
    try:
        target.wait_for(state="visible", timeout=3_000)
        return
    except TimeoutError:
        pass

    click_first_visible(page, [f"text={SURVEY_TEXT}", f"a:has-text('{SURVEY_TEXT}')", f"button:has-text('{SURVEY_TEXT}')"])
    target.wait_for(state="visible", timeout=20_000)


def open_result_download_menu(page: Page) -> None:
    page.get_by_text(RESULTS_TEXT, exact=True).first.click()
    page.wait_for_timeout(500)
    click_first_visible(page, [f"button:has-text('{RESULT_DOWNLOAD_TEXT}')", f"text={RESULT_DOWNLOAD_TEXT}"])
    page.get_by_text(EXCEL_DOWNLOAD_TEXT, exact=True).wait_for(state="visible", timeout=10_000)


def download_excel(page: Page, title: str, download_dir: Path) -> Path:
    open_result_download_menu(page)
    page.get_by_text(EXCEL_DOWNLOAD_TEXT, exact=True).click()
    page.get_by_text(SELECT_ALL_ITEMS_TEXT).wait_for(state="visible", timeout=10_000)
    select_all_excel_items(page)

    with page.expect_download(timeout=30_000) as download_info:
        page.get_by_text(DOWNLOAD_TEXT, exact=True).last.click()
    download = download_info.value
    return save_download(download, title, download_dir)


def select_all_excel_items(page: Page) -> None:
    row = page.get_by_text(SELECT_ALL_ITEMS_TEXT).locator("xpath=ancestor::*[self::div or self::label][1]")
    checkbox = row.locator("input[type='checkbox']").first
    if checkbox.count() > 0:
        checkbox.check(force=True)
        return

    row.locator("xpath=.//*[self::button or @role='checkbox' or self::span or self::div][1]").click()


def save_download(download: Download, title: str, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    suggested = download.suggested_filename or f"{clean_filename(title)}.xlsx"
    suffix = Path(suggested).suffix or ".xlsx"
    target = download_dir / f"{clean_filename(title)}{suffix}"
    download.save_as(str(target))
    return target


def close_detail(page: Page) -> None:
    candidates = [
        "button[aria-label='Close']",
        f"button[aria-label='{CLOSE_TEXT}']",
        f"button:has-text('{CLOSE_TEXT}')",
        "text=×",
    ]
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=1000):
                locator.click()
                wait_for_network_quiet(page)
                return
        except TimeoutError:
            continue
    page.keyboard.press("Escape")
    page.wait_for_timeout(800)


ProgressCallback = Callable[[str], None]


def make_default_config(download_dir: Path = DOWNLOAD_DIR, *, headless: bool = False) -> AgentConfig:
    return AgentConfig(
        base_url=DEFAULT_BASE_URL,
        headless=headless,
        slow_mo=150,
        timeout_ms=20_000,
        download_dir=download_dir,
        keep_open=False,
    )


def set_login_env(email: str, password: str) -> None:
    os.environ["CHEESEBUTTON_EMAIL"] = email
    os.environ["CHEESEBUTTON_PASSWORD"] = password


def list_surveys_for_gui(config: AgentConfig, progress: ProgressCallback | None = None) -> list[str]:
    progress = progress or (lambda message: None)
    progress("브라우저를 실행합니다.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        context = make_context(browser, config)
        page = context.new_page()
        page.set_default_timeout(config.timeout_ms)

        try:
            progress("로그인 상태를 확인합니다.")
            ensure_logged_in(page, config)
            progress("설문 목록으로 이동합니다.")
            go_to_survey_list(page, config)
            scroll_to_bottom(page)
            titles = [card["title"] for card in collect_visible_qr_survey_cards(page)]
            progress(f"설문 {len(titles)}개를 찾았습니다.")
            return titles
        finally:
            context.storage_state(path=str(STORAGE_STATE))
            browser.close()


def download_surveys_for_gui(
    config: AgentConfig,
    centers: list[str],
    progress: ProgressCallback | None = None,
) -> list[Path]:
    progress = progress or (lambda message: None)
    saved_paths: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        context = make_context(browser, config)
        page = context.new_page()
        page.set_default_timeout(config.timeout_ms)

        try:
            progress("로그인 상태를 확인합니다.")
            ensure_logged_in(page, config)
            go_to_survey_list(page, config)
            scroll_to_bottom(page)

            for index, title in enumerate(centers, start=1):
                progress(f"[{index}/{len(centers)}] {title} 다운로드를 시작합니다.")
                open_survey(page, title)
                saved_path = download_excel(page, title, config.download_dir)
                saved_paths.append(saved_path)
                progress(f"저장 완료: {saved_path}")
                close_detail(page)
                go_to_survey_list(page, config)

            progress("선택한 설문 다운로드가 완료되었습니다.")
            return saved_paths
        finally:
            context.storage_state(path=str(STORAGE_STATE))
            browser.close()


def run_agent(config: AgentConfig, centers: list[str], *, list_surveys: bool = False, limit: int | None = None) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        context = make_context(browser, config)
        page = context.new_page()
        page.set_default_timeout(config.timeout_ms)

        try:
            ensure_logged_in(page, config)
            go_to_survey_list(page, config)
            scroll_to_bottom(page)

            if list_surveys:
                print_survey_cards(collect_visible_qr_survey_cards(page), "현재 화면에서 찾은 QR 방명록 설문")
                return

            selected_centers = centers[:limit] if limit else centers
            for index, title in enumerate(selected_centers, start=1):
                print(f"[{index:02d}/{len(selected_centers):02d}] {title}")
                open_survey(page, title)
                saved_path = download_excel(page, title, config.download_dir)
                print(f"  저장 완료: {saved_path}")
                close_detail(page)
                go_to_survey_list(page, config)
        finally:
            context.storage_state(path=str(STORAGE_STATE))
            if config.keep_open:
                print("브라우저를 열어둡니다. 확인이 끝나면 Enter를 누르세요.")
                input()
            browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="치즈버튼 QR 방명록 엑셀 다운로드 agent")
    parser.add_argument("--base-url", default=os.getenv("CHEESEBUTTON_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--download-dir", default=str(DOWNLOAD_DIR))
    parser.add_argument("--headless", action="store_true", help="브라우저를 숨기고 실행합니다.")
    parser.add_argument("--slow-mo", type=int, default=150, help="브라우저 동작 지연 시간(ms)")
    parser.add_argument("--timeout-ms", type=int, default=20_000)
    parser.add_argument("--center", action="append", help="특정 센터명만 다운로드합니다. 여러 번 지정 가능.")
    parser.add_argument("--limit", type=int, help="앞에서부터 지정한 개수만 다운로드합니다. 테스트할 때 --limit 1을 권장합니다.")
    parser.add_argument("--list-surveys", action="store_true", help="다운로드하지 않고 현재 계정에서 보이는 QR 방명록 설문 제목만 출력합니다.")
    parser.add_argument("--keep-open", action="store_true", help="실패 지점을 직접 볼 수 있도록 종료 전에 브라우저를 열어둡니다.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    centers = args.center or CENTERS
    config = AgentConfig(
        base_url=args.base_url,
        headless=args.headless,
        slow_mo=args.slow_mo,
        timeout_ms=args.timeout_ms,
        download_dir=Path(args.download_dir),
        keep_open=args.keep_open,
    )
    run_agent(config, centers, list_surveys=args.list_surveys, limit=args.limit)


if __name__ == "__main__":
    main()
