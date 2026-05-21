#!/usr/bin/env python3
"""
Arena Submit — 提交脚本（不做任何策略推理）

职责：
1. 验证 pick 在 1-10 整数范围
2. 调用 POST submission API
3. 严格区分 4xx（业务错误）vs 5xx（网络错误）
4. 输出明确的成功/失败信息

用法：
  python3 arena_submit.py --tid <tournament_id> --round <N> --pick <1-10> --message "<msg>"

输出格式：
  OK:<round_score_if_returned>      - 提交成功
  ALREADY_SUBMITTED                 - 已提交（409），不是错误
  ROUND_CLOSED                      - 轮次已关闭，不是错误
  ERROR:<msg>                       - 真实错误

退出码：
  0 = 提交成功 / 幂等（已提交）
  1 = 业务错误（参数无效、轮次关闭等）
  2 = 网络错误（应该被外部观察到，但 cron 单次不重试）
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

API_BASE = "https://www.agenthansa.com/api"
TIMEOUT = 15


def get_api_key():
    key = os.environ.get("AGENTHANSA_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.expanduser("~/.hermes/agenthansa_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tid", required=True, help="tournament_id")
    parser.add_argument("--round", type=int, required=True, dest="rnd")
    parser.add_argument("--pick", type=int, required=True)
    parser.add_argument("--message", default="gg")
    args = parser.parse_args()

    # 输入校验
    if not (1 <= args.pick <= 10):
        print(f"ERROR:invalid_pick:{args.pick} (must be 1-10)")
        return 1

    if len(args.message) > 200:
        # 截断到 200 字符避免 API 拒绝
        args.message = args.message[:200]

    key = get_api_key()
    if not key:
        print("ERROR:no_api_key")
        return 1

    url = f"{API_BASE}/arena/tournaments/{args.tid}/rounds/{args.rnd}/submission"
    body = json.dumps({"submission": args.pick, "message": args.message}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    # 自动识别代理
    proxy = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read())
            score = result.get("round_score")
            print(f"OK:score={score}" if score is not None else "OK")
            return 0
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except Exception:
            pass

        if e.code == 409:
            # 已提交或轮次关闭
            if "already" in body_text.lower() or "submitted" in body_text.lower():
                print("ALREADY_SUBMITTED")
                return 0
            if "closed" in body_text.lower() or "lock" in body_text.lower():
                print("ROUND_CLOSED")
                return 0
            print(f"ERROR:409:{body_text}")
            return 1

        if 400 <= e.code < 500:
            print(f"ERROR:client_{e.code}:{body_text}")
            return 1

        # 5xx
        print(f"ERROR:server_{e.code}:{body_text}")
        return 2

    except urllib.error.URLError as e:
        print(f"ERROR:network:{e.reason}")
        return 2
    except Exception as e:
        print(f"ERROR:unhandled:{type(e).__name__}:{e}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR:fatal:{type(e).__name__}:{e}")
        sys.exit(1)
