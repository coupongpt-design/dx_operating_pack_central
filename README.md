# 🖱️ ImageMacro

> **Windows 화면 자동화 매크로 툴** — 이미지 인식·OCR·스케줄러·멀티 세션을 하나로

---

## 이런 분께 맞습니다

- 반복 클릭/입력 작업을 자동화하고 싶은 분
- 이미지가 화면에 나타나면 자동으로 클릭하고 싶은 분
- 여러 계정·창을 동시에 관리하고 싶은 분
- 코딩 없이 조건 분기·스케줄링까지 쓰고 싶은 분

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🎥 **녹화** | 마우스/키 동작을 그대로 녹화해 즉시 재생 |
| 🖼️ **이미지 인식** | 화면에서 이미지를 찾아 클릭 (해상도 무관) |
| 🔤 **OCR 분기** | 숫자/문자를 읽어 조건에 따라 흐름 분기 |
| 📅 **스케줄러** | 특정 시간에 자동 실행 |
| 👥 **멀티 세션** | 여러 창을 라운드로빈으로 동시 관리 |
| 📊 **Excel 연동** | CSV/XLSX 데이터를 행마다 자동 입력 |
| 🧩 **시나리오 마법사** | 46종 템플릿으로 복잡한 흐름 빠르게 생성 |

---

## 설치

### 1. 필수 요구사항
- **Windows 10/11**
- **Python 3.10+** ([다운로드](https://www.python.org/downloads/))
- **Tesseract OCR** — OCR 기능 사용 시만 필요 ([다운로드](https://github.com/UB-Mannheim/tesseract/wiki))

### 2. 설치

```powershell
git clone https://github.com/<your-org>/ImageMacro.git
cd ImageMacro
pip install -r requirements-dev.txt
```

### 3. 실행

```powershell
python run.py
```

> 관리자 권한이 필요한 앱을 자동화하려면 **관리자 권한으로 실행**하세요.

---

## 30초 빠른 시작

```
1. Record 버튼 클릭 → 마우스/키 동작 수행 → Record 다시 클릭(중지)
2. Run 버튼으로 바로 재생
3. Save로 저장 (.macro 파일)
```

이미지 클릭 예시:
```
1. Add Image 클릭 → 화면 영역 드래그 선택
2. Run → 해당 이미지가 화면에 있으면 자동 클릭
```

---

## 상세 사용법

→ **[USER_GUIDE.md](docs/USER_GUIDE.md)** 참고

---

## 단축키

| 키 | 기능 |
|----|------|
| `F10` | 실행 중 일시정지 / 재개 |
| `F12` | 긴급 종료 |
| `Ctrl+Z / Ctrl+Y` | 스텝 Undo / Redo |

---

## EXE 빌드 (배포용)

```powershell
# 로컬 빌드
.\tools\build_exe.ps1
```

또는 GitHub Actions의 `build-exe.yml` 수동 실행(`workflow_dispatch`)

---

## 라이선스

MIT
