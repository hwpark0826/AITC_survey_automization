import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from playwright.sync_api import TimeoutError, sync_playwright

import cheese_button_agent as agent


REGION_GROUPS = [
    ("1권역", ["서울", "인천", "고양", "포천", "용인", "화성", "평택"]),
    ("2권역", ["강원", "경북", "부산", "울산", "진주", "김해", "제주"]),
    ("3권역", ["대전", "충남", "충북", "전북", "전남", "광주"]),
]


class CheeseButtonWizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("치즈버튼 QR 방명록 다운로더")
        self.geometry("720x520")
        self.minsize(640, 460)

        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.download_dir = tk.StringVar(value=str(agent.DOWNLOAD_DIR.resolve()))
        self.email = tk.StringVar()
        self.password = tk.StringVar()
        self.active_button: ttk.Button | None = None
        self.survey_titles: list[str] = []
        self.selected_surveys: dict[str, tk.BooleanVar] = {}
        self.select_all_surveys = tk.BooleanVar(value=True)
        self.group_vars: dict[str, tk.BooleanVar] = {}

        self._build_environment_step()
        self.after(100, self._drain_log_queue)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        if self.active_button and self.active_button.winfo_exists():
            self.active_button.configure(state=state)

    def _build_environment_step(self) -> None:
        self._clear()

        ttk.Label(self, text="치즈버튼 QR 방명록 다운로더", font=("맑은 고딕", 18, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        ttk.Label(self, text="1단계. 실행 환경 확인", font=("맑은 고딕", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 16))

        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=24)

        ttk.Label(frame, text="저장 경로").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.download_dir).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(frame, text="폴더 선택", command=self._choose_download_dir).grid(row=1, column=1, padx=(8, 0), pady=(4, 0))
        frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=24, pady=16)

        self.check_button = ttk.Button(button_frame, text="환경 확인 시작", command=self._start_environment_check)
        self.check_button.pack(side="left")
        self.active_button = self.check_button

        self.log_text = tk.Text(self, height=16, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def _build_login_step(self) -> None:
        self._clear()

        ttk.Label(self, text="치즈버튼 QR 방명록 다운로더", font=("맑은 고딕", 18, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        ttk.Label(self, text="2단계. 로그인", font=("맑은 고딕", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 16))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=24)

        ttk.Label(form, text="이메일").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.email).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        ttk.Label(form, text="비밀번호").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.password, show="*").grid(row=3, column=0, sticky="ew", pady=(4, 0))
        form.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=24, pady=16)

        self.login_button = ttk.Button(button_frame, text="로그인 확인", command=self._start_login_check)
        self.login_button.pack(side="left")
        self.active_button = self.login_button

        self.log_text = tk.Text(self, height=16, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def _build_load_surveys_step(self) -> None:
        self._clear()

        ttk.Label(self, text="치즈버튼 QR 방명록 다운로더", font=("맑은 고딕", 18, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        ttk.Label(self, text="3단계. 설문 불러오기", font=("맑은 고딕", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 16))
        ttk.Label(self, text="다음 단계에서는 로그인한 계정의 QR 방명록 설문 목록을 불러옵니다.").pack(anchor="w", padx=24)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=24, pady=16)
        self.load_surveys_button = ttk.Button(button_frame, text="설문 목록 불러오기", command=self._start_load_surveys)
        self.load_surveys_button.pack(side="left")
        self.active_button = self.load_surveys_button

        self.log_text = tk.Text(self, height=16, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def _build_select_surveys_step(self) -> None:
        self._clear()

        ttk.Label(self, text="치즈버튼 QR 방명록 다운로더", font=("맑은 고딕", 18, "bold")).pack(anchor="w", padx=24, pady=(24, 4))
        ttk.Label(self, text="4단계. 지역 선택", font=("맑은 고딕", 12, "bold")).pack(anchor="w", padx=24, pady=(0, 16))

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=24)
        ttk.Checkbutton(
            controls,
            text="전체 선택",
            variable=self.select_all_surveys,
            command=self._toggle_all_surveys,
        ).pack(anchor="w")

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=24, pady=12)

        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._bind_mousewheel(canvas, inner)

        self.selected_surveys = {}
        self.group_vars = {}
        titles_by_region = self._titles_by_region()
        rendered_titles: set[str] = set()

        for group_name, regions in REGION_GROUPS:
            group_var = tk.BooleanVar(value=True)
            self.group_vars[group_name] = group_var
            ttk.Checkbutton(
                inner,
                text=group_name,
                variable=group_var,
                command=lambda name=group_name: self._toggle_group_surveys(name),
            ).pack(anchor="w", pady=(8, 2))

            for region in regions:
                title = titles_by_region.get(region)
                if not title:
                    continue
                rendered_titles.add(title)
                var = tk.BooleanVar(value=True)
                self.selected_surveys[title] = var
                ttk.Checkbutton(
                    inner,
                    text=f"  {region}",
                    variable=var,
                    command=self._sync_group_checkboxes,
                ).pack(anchor="w", padx=18, pady=2)

        remaining_titles = [title for title in self.survey_titles if title not in rendered_titles]
        if remaining_titles:
            ttk.Label(inner, text="기타").pack(anchor="w", pady=(8, 2))
            for title in remaining_titles:
                var = tk.BooleanVar(value=True)
                self.selected_surveys[title] = var
                ttk.Checkbutton(
                    inner,
                    text=f"  {title}",
                    variable=var,
                    command=self._sync_group_checkboxes,
                ).pack(anchor="w", padx=18, pady=2)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=24, pady=(0, 24))
        ttk.Button(button_frame, text="이전", command=self._build_load_surveys_step).pack(side="left")
        ttk.Button(button_frame, text="다음 단계 준비 중").pack(side="right")

    def _clear(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def _bind_mousewheel(self, canvas: tk.Canvas, widget: tk.Widget) -> None:
        def on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def unbind(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")

        widget.bind("<Enter>", bind)
        widget.bind("<Leave>", unbind)
        canvas.bind("<Enter>", bind)
        canvas.bind("<Leave>", unbind)

    def _choose_download_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.download_dir.get() or str(Path.home()))
        if selected:
            self.download_dir.set(selected)

    def _start_environment_check(self) -> None:
        self._set_busy(True)
        self._clear_log()

        worker = threading.Thread(target=self._run_environment_check, daemon=True)
        worker.start()

    def _start_login_check(self) -> None:
        email = self.email.get().strip()
        password = self.password.get()

        if not email or not password:
            messagebox.showwarning("입력 확인", "이메일과 비밀번호를 모두 입력해주세요.")
            return

        self._set_busy(True)
        self._clear_log()

        worker = threading.Thread(target=self._run_login_check, args=(email, password), daemon=True)
        worker.start()

    def _start_load_surveys(self) -> None:
        self._set_busy(True)
        self._clear_log()

        worker = threading.Thread(target=self._run_load_surveys, daemon=True)
        worker.start()

    def _run_environment_check(self) -> None:
        try:
            self._log("저장 경로 쓰기 권한을 확인합니다.")
            self._check_download_dir()
            self._log("저장 경로 확인 완료")

            self._log("포함된 Chromium 브라우저 실행을 확인합니다.")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(15_000)
                page.set_content("<h1>ok</h1>")
                if page.inner_text("h1") != "ok":
                    raise RuntimeError("브라우저 화면 확인에 실패했습니다.")
                self._log("브라우저 실행 확인 완료")

                self._log("치즈버튼 로그인 페이지 접속을 확인합니다.")
                page.goto(agent.LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except TimeoutError:
                    pass
                if "cheesebutton" not in page.url:
                    raise RuntimeError(f"예상하지 못한 페이지로 이동했습니다: {page.url}")
                self._log("치즈버튼 접속 확인 완료")
                browser.close()

            self._log("실행 환경 확인 완료", "env_success")
        except Exception as exc:
            self._log(f"환경 확인 실패: {self._friendly_environment_error(exc)}", "env_error")
        finally:
            self.log_queue.put(("done", ""))

    def _check_download_dir(self) -> None:
        download_dir = Path(self.download_dir.get()).expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=download_dir, delete=True) as handle:
            handle.write("ok")

    def _run_login_check(self, email: str, password: str) -> None:
        try:
            self._log("치즈버튼 로그인 페이지를 엽니다.")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    accept_downloads=True,
                    viewport={"width": 1600, "height": 1000},
                    locale="ko-KR",
                )
                page = context.new_page()
                page.set_default_timeout(20_000)
                try:
                    page.goto(agent.LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
                except Exception as exc:
                    raise RuntimeError("치즈버튼 로그인 페이지에 접속할 수 없습니다. 인터넷 또는 회사 보안망을 확인해주세요.") from exc
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except TimeoutError:
                    pass

                self._log("입력한 계정으로 로그인을 확인합니다.")
                email_input = page.locator("input[name='email']")
                password_input = page.locator("input[name='password']")
                submit = page.locator("button[data-testid='submit']")
                try:
                    email_input.fill(email, timeout=10_000)
                    password_input.fill(password, timeout=10_000)
                    submit.wait_for(state="visible", timeout=10_000)
                except TimeoutError as exc:
                    raise RuntimeError("로그인 화면을 찾지 못했습니다. 치즈버튼 화면 구조가 변경되었을 수 있습니다.") from exc
                page.wait_for_function(
                    "selector => !document.querySelector(selector).disabled",
                    arg="button[data-testid='submit']",
                )
                submit.click()
                try:
                    page.wait_for_url(lambda url: "signin" not in url, timeout=15_000)
                except TimeoutError:
                    pass
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except TimeoutError:
                    pass

                if "signin" in page.url:
                    raise RuntimeError("이메일 또는 비밀번호가 올바르지 않습니다.")

                if "studio.cheesebutton.io" not in page.url:
                    try:
                        page.goto(agent.DEFAULT_BASE_URL, wait_until="domcontentloaded", timeout=15_000)
                    except Exception:
                        page.wait_for_timeout(1_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=5_000)
                    except TimeoutError:
                        pass

                try:
                    agent.enter_channel_if_needed(page)
                except TimeoutError as exc:
                    raise RuntimeError("로그인은 되었지만 전국 AI무역지원센터 채널을 찾지 못했습니다. 계정 권한을 확인해주세요.") from exc

                if "signin" in page.url:
                    raise RuntimeError("이메일 또는 비밀번호가 올바르지 않습니다.")

                context.storage_state(path=str(agent.STORAGE_STATE))
                browser.close()

            self._log("로그인 성공!", "login_success")
        except Exception as exc:
            self._log(f"로그인 실패: {self._friendly_login_error(exc)}", "login_error")
        finally:
            self.password.set("")
            self.log_queue.put(("done", ""))

    def _run_load_surveys(self) -> None:
        try:
            self._log("로그인 세션으로 설문 목록을 불러옵니다.")
            config = agent.make_default_config(Path(self.download_dir.get()), headless=True)
            titles = agent.list_surveys_for_gui(config, self._log)
            if not titles:
                raise RuntimeError("QR 방명록 설문을 찾지 못했습니다. 계정 권한 또는 채널 상태를 확인해주세요.")
            self.survey_titles = titles
            self._log(f"설문 {len(titles)}개를 불러왔습니다.", "surveys_success")
        except Exception as exc:
            self._log(f"설문 불러오기 실패: {self._friendly_survey_error(exc)}", "surveys_error")
        finally:
            self.log_queue.put(("done", ""))

    def _toggle_all_surveys(self) -> None:
        selected = self.select_all_surveys.get()
        for var in self.selected_surveys.values():
            var.set(selected)
        for var in self.group_vars.values():
            var.set(selected)

    def _toggle_group_surveys(self, group_name: str) -> None:
        selected = self.group_vars[group_name].get()
        titles_by_region = self._titles_by_region()

        for name, regions in REGION_GROUPS:
            if name != group_name:
                continue
            for region in regions:
                title = titles_by_region.get(region)
                if title in self.selected_surveys:
                    self.selected_surveys[title].set(selected)

        self._sync_group_checkboxes()

    def _sync_group_checkboxes(self) -> None:
        titles_by_region = self._titles_by_region()

        for group_name, regions in REGION_GROUPS:
            group_titles = [titles_by_region[region] for region in regions if region in titles_by_region]
            if group_titles:
                self.group_vars[group_name].set(all(self.selected_surveys[title].get() for title in group_titles))

        if self.selected_surveys:
            self.select_all_surveys.set(all(var.get() for var in self.selected_surveys.values()))

    def _titles_by_region(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for title in self.survey_titles:
            for _, regions in REGION_GROUPS:
                for region in regions:
                    if title.startswith(f"{region} "):
                        pairs[region] = title
        return pairs

    def _friendly_environment_error(self, exc: Exception) -> str:
        message = str(exc)
        if "ERR_NAME_NOT_RESOLVED" in message or "ERR_CONNECTION" in message:
            return "치즈버튼에 접속할 수 없습니다. 인터넷 또는 회사 보안망을 확인해주세요."
        if "Executable doesn't exist" in message or "browser" in message.lower():
            return "포함된 Chromium 브라우저를 실행할 수 없습니다. 배포 파일이 누락되었을 수 있습니다."
        if "Permission" in message or "Access is denied" in message:
            return "저장 경로나 브라우저 실행 권한이 막혀 있습니다."
        return message

    def _friendly_login_error(self, exc: Exception) -> str:
        message = str(exc)
        if "이메일 또는 비밀번호" in message:
            return message
        if "로그인 페이지에 접속" in message:
            return message
        if "로그인 화면을 찾지 못했습니다" in message:
            return message
        if "전국 AI무역지원센터 채널" in message:
            return message
        if "Timeout" in message:
            return "응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
        if "ERR_NAME_NOT_RESOLVED" in message or "ERR_CONNECTION" in message:
            return "치즈버튼에 접속할 수 없습니다. 인터넷 또는 회사 보안망을 확인해주세요."
        return "알 수 없는 오류가 발생했습니다. 로그를 관리자에게 전달해주세요."

    def _friendly_survey_error(self, exc: Exception) -> str:
        message = str(exc)
        if "QR 방명록 설문을 찾지 못했습니다" in message:
            return message
        if "signin" in message:
            return "로그인 세션이 만료되었습니다. 로그인 단계부터 다시 진행해주세요."
        if "Timeout" in message:
            return "설문 목록을 불러오는 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
        if "ERR_NAME_NOT_RESOLVED" in message or "ERR_CONNECTION" in message:
            return "치즈버튼에 접속할 수 없습니다. 인터넷 또는 회사 보안망을 확인해주세요."
        return "알 수 없는 오류가 발생했습니다. 로그를 관리자에게 전달해주세요."

    def _log(self, message: str, level: str = "info") -> None:
        self.log_queue.put((level, message))

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                level, message = self.log_queue.get_nowait()
                if level == "done":
                    self._set_busy(False)
                    continue
                self._append_log(message)
                if level == "env_success":
                    self.after(700, self._build_login_step)
                elif level == "login_success":
                    self.after(700, self._build_load_surveys_step)
                elif level == "surveys_success":
                    self.after(700, self._build_select_surveys_step)
                elif level == "env_error":
                    messagebox.showerror("환경 확인 실패", message)
                elif level == "login_error":
                    messagebox.showerror("로그인 실패", message)
                elif level == "surveys_error":
                    messagebox.showerror("설문 불러오기 실패", message)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

def main() -> None:
    app = CheeseButtonWizard()
    app.mainloop()


if __name__ == "__main__":
    main()
