# Love Story MV — 세션 시작 시 먼저 읽기

이 저장소는 **인수인계 문서 보관용**이다. 실제 작업(ComfyUI, ffmpeg, 영상 파일)은 사용자 Windows PC
(`C:\Users\GUNWOO\Documents\Codex\2026-09-13\new-chat`)에 있다.

- 클라우드/휴대폰 세션에서는 ComfyUI(127.0.0.1:8188)·로컬 파일에 접근 불가 → 계획, 프롬프트 작성,
  사용자가 올린 이미지/영상 검수만 가능. 생성 작업은 PC의 Claude Desktop 또는 PC에서 `claude remote-control` 실행 후 진행.
- 문서:
  - `docs/HANDOFF_CURRENT_3cha.md` — **최신** (기준 편집본 `3차.mp4`, 빈 구간 GAP 01~07, 작업 절차). 이것이 우선.
  - `docs/HANDOFF_v6_claude.md` — 이전 Claude 세션의 경로·레퍼런스·검증된 워크플로(ComfyUI 스크립트, 함정).
  - `docs/NEXT_STEPS.md` — 현재 진행 상황/다음 할 일. **작업할 때마다 갱신하고 커밋·푸시.**
- 사용자 선호: 한국어, 짧게 보고. 이미지 1장씩 → 승인 → 그 이미지를 첫 프레임으로 I2V → QC → 승인 → 다음 컷.
  기존 완성 구간 덮어쓰기·삭제 금지. 유료 API 사용 전 승인. Z-Image 실사 보정 금지. 레퍼런스 최대 2장.
- 보고 마지막 줄: `승인 대기 중 — 승인 전 다음 컷으로 넘어가지 않음`
