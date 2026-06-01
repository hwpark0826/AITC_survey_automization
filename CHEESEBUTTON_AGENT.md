# 치즈버튼 QR 방명록 엑셀 다운로드 Agent

전국 AI무역지원센터 QR 방명록 설문을 찾아 각 설문의 `결과보기` 화면에서 `결과 다운로드 > 엑셀 다운로드`를 실행합니다.

## 설치

```powershell
python -m pip install -r requirements-cheesebutton.txt
python -m playwright install chromium
```

## 실행

처음 실행할 때는 브라우저가 열립니다. 치즈버튼에 직접 로그인한 뒤 터미널에서 Enter를 누르면 로그인 세션이 `.cheesebutton_state.json`에 저장됩니다.

```powershell
python cheese_button_agent.py
```

이후에는 저장된 로그인 세션으로 다시 실행됩니다.

## 계정 정보로 자동 로그인

환경변수를 설정하면 로그인 폼을 자동으로 입력합니다.

```powershell
$env:CHEESEBUTTON_EMAIL="your-email@example.com"
$env:CHEESEBUTTON_PASSWORD="your-password"
python cheese_button_agent.py
```

## 특정 센터만 다운로드

```powershell
python cheese_button_agent.py --center "김해 AI무역지원센터 QR 방명록"
```

여러 센터를 지정하려면 `--center`를 반복해서 넣으면 됩니다.

## 옵션

- `--download-dir downloads`: 엑셀 저장 폴더
- `--headless`: 브라우저를 숨기고 실행
- `--base-url`: 치즈버튼 기본 URL 변경
- `--slow-mo 150`: UI 동작 지연 시간 조정

## 센터 목록 확인 필요

`cheese_button_agent.py`의 `CENTERS`에는 기본 20개 센터명을 넣어두었습니다. 실제 치즈버튼 카드 제목과 다른 센터명이 있으면 해당 문자열만 수정하면 됩니다.
