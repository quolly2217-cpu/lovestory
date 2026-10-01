# Love Story MV — 인수인계 v6 (2026-10-02)

v3~v5(`Downloads\CLAUDE_HANDOFF_v3/v4/v5.md`)의 경로·함정은 그대로 유효. 이 문서는 **레퍼런스와 작업 방법**만 정리.
(이 세션 이후 사용자가 ChatGPT로 따로 작업한 부분이 있음 → 최신 상태는 사용자에게 확인.)

## 0. 사용자 선호
- 한국어, 짧게 보고. 결과는 `SendUserFile`로 전송.
- **결과 저장: `outputs\lovestroy0930\`** (폴더명 오타 그대로 사용). 덮어쓰기·삭제 금지(`lp.next_version`).
- 이미지는 **한 번에 1장씩** (구도 비교가 필요할 때만 여러 장).
- 사용자가 **첫 프레임 이미지 + 영문 동작 프롬프트**를 주면 프롬프트 **원문 그대로** 넣어 영상만 만든다.
- 보고 표: `얼굴 / 손·몸 / 동작 / 첫 프레임 / 재생성`. 검수는 원본 해상도로(`work\qc.py`는 중앙 크롭이라 전체 구도는 `ffmpeg fps=2,tile=5x2` 시트로 따로 봄).
- **비워둘 구간:** 랩(124.6~146.9 중 멤버 랩 립싱크), 60.8~67.8("L-O-V-E 너에게 닿기를 / 스파크") — 별도 요청 예정.
- Pro 주간 한도 초과 시 추가 사용(유료)으로 넘어감 → 사용자에게 알릴 것.

## 1. 경로
- 프로젝트 `C:\Users\GUNWOO\Documents\Codex\2026-09-13\new-chat` (`scripts\ls_pipeline.py`, `work\`)
- ComfyUI `127.0.0.1:8188`, venv python `...\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe`
- ffmpeg(시스템 PATH 없음): `C:\Users\GUNWOO\AppData\Local\CapCut\Apps\9.3.0.3970\ffmpeg.exe`
- 기준 영상: `C:\Users\GUNWOO\Pictures\challenge\2차수정.mp4` (204.8초, 검은 빈 구간 9곳)
- 가사 시간표: `work\lyrics_timeline_actual.md` (whisper 기준, 신뢰)

## 2. 레퍼런스
| 용도 | 파일 |
|---|---|
| 블루 얼굴 (각도 맞는 크롭, 제일 잘 먹힘) | `outputs\lovestroy0930\ref_blue_face_F05.png` |
| 블루 공식 정면 | `outputs\Love_Story_main_character_v1.png` |
| 피치 | `outputs\Love_Story_member_peach_idol_sheet_v4.png` (시트 → 왼쪽 1/3·위 55% 크롭해서 얼굴만) |
| 민트 | `outputs\Love_Story_mint_face_crop_v1.png` (일자 단발) |
| 퍼플 | `outputs\Love_Story_lilac_face_front_v1.png` / MV 퍼플은 앞머리 있는 하이포니 (`사용자이미지\..._F03_user_v1.png`) |
| 남자 | `outputs\Love_Story_man_ref_v1.png` |
| 그림체·방 기준 (거울 장면) | `outputs\lovestroy0930\ref_mirror_nosub_21s.png` |
| 지하철역 블루 | `outputs\lovestroy0930\ref\mv_subway_102.png` |
| 사용자 원본 이미지 | `outputs\0930_FILL\사용자이미지\` (F01 피치, F02 민트 온실, F03 퍼플 계단, F05 블루 현관, F21/F27 단체 등) |

멤버 기본 순서(왼→오): 피치(레드 웨이브+리본핀) · 민트(검은 단발) · 블루(긴 갈색 웨이브, 별귀걸이, 중앙) · 퍼플(하이포니).

## 3. 작업 방법 (검증됨)
- **이미지:** Qwen-Image-Edit 2511 + Lightning 4스텝 (`lp.cmd_keyframe`). 이웃 MV 프레임을 image1로 넣어 편집하면 그림체가 맞음.
  - **Z-Image 실사 보정(`work\zit_real.py`)은 쓰지 말 것** — MV 그림체(광택·파스텔)와 안 맞는다는 피드백.
  - 레퍼런스 3장 이상 넣으면 얼굴이 겹쳐 콜라주처럼 깨짐 → 최대 2장.
  - 얼굴 교정: 전체 이미지에 "Replace only the face of ... with image 2" (단체는 한 명씩 순서대로, `work\groupface_1001.py`). 블루 단독은 얼굴 크롭→교정→붙여넣기(`work\gap1_refine.py`)도 가능, 단 반투명 재합성은 입이 번짐.
  - 편집으로 "커튼 닫힘"처럼 상태를 뒤집는 건 잘 안 됨 → 사용자에게 이미지 요청.
- **영상:** MiniMax 30스텝 템플릿 `work\animatediff_ref\minimax_hq30.json`, 범용 함수 `work\overnight_0930.py`의 `gen()` / `solo_prompt()` / `group_prompt()` / `couple_prompt()`.
  - 1인 0.65MP, 단체·커플 0.6MP 사다리. 5초 ≈ 15분.
  - **립싱크(블루 외 멤버/단체):** 노래 구간을 `ref_audios.ref_audio_0`에 연결(`audio=True`). 단체 중 한 명만 부르게 하는 것도 가능하나 100%는 아님.
  - 카메라가 줌인/틸트업하며 **다른 인물로 바뀌는** 경우가 있음(발 클로즈업) → "never tilts up" 명시, 결과 끝부분 꼭 확인.
  - 동작이 약하면 "within the first second … big, clear" 식으로 강하게 + 시드 변경.
  - 사용자 프롬프트 사용 예: `work\letsgo_user.py`, `work\elevator_user.py`, `work\curtain_user2.py`.
- 큐: `lp.submit`은 큐가 비어야 제출됨. 이미지 작업을 영상 사이에 끼우려면 1초 폴링 `fast_idle` 사용(`work\kf_1001b.py`).

## 4. 결과물 (`outputs\lovestroy0930\`)
- `영상\` — 이번 세션 영상 전부. 사용자 반응 좋았던 것: `01_아침커튼_사용자이미지_B/C`, `03_민트_창가_립싱크_스쳐가는바람`, `00_단체_렛츠고_핑거하트`/`_방향가리키기`, `08_단체_엘리베이터_립싱크`, `09_카세트_윙크1/2`, `02_발걸음_경쾌`.
- `첫프레임_1001\` — 10/1 첫 프레임들(퍼플 인형뽑기/마술상자 스토리 제안 포함, 미선택).
- `얼굴교정_1001\` — 노을 옥상 단체 3장 얼굴(+1·2번은 머리) 교정 결과, **검수 전**.
- `overnight_log.txt` — 생성 기록.

## 5. 남은 일 (이 세션 기준)
1. 노을 옥상 단체 3장 얼굴교정 결과 검수·전달.
2. **블루 자전거 영상 2개(미착수):** 사용자 이미지 2장(낮/노을, 강변 자전거) → "자전거를 타고 와서 세우고, 숨을 고른 뒤 머리를 정리하고 앞으로 걸어감", 각 1개 고화질. 이미지 원본: `C:\Users\GUNWOO\.claude\uploads\a701b1a7-83a5-4bce-bc2a-981296a6497b\5522c265-image.png`, `5cc09e40-image.png` (새 창에서 다시 받는 게 안전).
3. 블루 역 출구 립싱크(103.8초, `첫프레임_1001\05_블루_역출구_꽃길_v2_v1.png`) — 보류 중.
4. 퍼플 "하나 둘 셋 ~ right now" 스토리 선택 대기.
