"""
導演鏈路自我測試（單指令、走 WebUI 同一套 client 代碼，不碰任務歷史）。

用途：模型與显存環境就緒後（例如关闭了佔显存的常駐程式），一條指令驗證
「builder 組合 → queue_prompt → ComfyUI 推論 → /history 取文字 → 雙段解析」
全部通。與網頁上的「🎬 影片導演」按鈕走完全相同的 call_director 路徑，
所以這裡綠 = 網頁導演也綠。

用法（專案根目錄）：
    python tools/director_selftest.py                     # 預設模型（清單第一個）+ GPU
    python tools/director_selftest.py --model qwen3vl_4b_bf16.safetensors --device cpu
    python tools/director_selftest.py --image 某張圖.jpg   # 帶參考圖測試視覺解讀
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from core import director_builder  # noqa: E402
from core.director_client import call_director  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="director live self-test")
    ap.add_argument("--model", default=None, help="text_encoders 裡的 qwen3vl 檔名（預設＝清單第一個）")
    ap.add_argument("--device", default=None, choices=["default", "cpu"],
                    help="覆蓋 CLIPLoader 放置裝置（cpu＝完全不吃显存的保底測法）")
    ap.add_argument("--image", default=None, help="參考圖片路徑（測試視覺解讀）")
    ap.add_argument("--brief", default="幫這張圖寫一段電影感的鏡頭提示詞：人物緩緩轉頭，鏡頭慢慢推近，逆光。")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    if args.image and not os.path.isfile(args.image):
        print(f"❌ 參考圖片不存在：{args.image}")
        return 2

    if args.device:
        director_builder.DIRECTOR_CLIP_DEVICE = args.device  # 只影響本次進程，不落 config

    models = config.get_director_models()
    print("掃描到的導演模型：", models or "（空！請確認 text_encoders 資料夾）")
    if not models:
        return 2

    print(f"送件中… model={args.model or models[0]} device={director_builder.DIRECTOR_CLIP_DEVICE} "
          f"image={'有' if args.image else '無'}")
    t0 = time.time()
    ok, note, text = call_director(brief=args.brief, image_path=args.image,
                                   model_name=args.model, timeout=args.timeout)
    dt = time.time() - t0
    if not ok:
        print(f"❌ 失敗（{dt:.0f}s）：{text}")
        return 1
    print(f"✅ 成功（{dt:.0f}s，{len(text)} chars）")
    print("【導演筆記】", note or "（模型沒分段）")
    print("【English Prompt】", text[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
