#!/usr/bin/env python3
"""
Arena Gate — 状态检查脚本（不做任何策略推理）

职责：
1. 查询当前是否有 live tournament
2. 查询 my-pairing 状态
3. 输出明确的状态码 + 对手原始数据（如果可决策）

输出格式：
  ALREADY_SUBMITTED          - 本轮已提交，agent 应输出 [SILENT] 退出
  NO_ACTION:<reason>         - 无可行动作（无赛事/已淘汰/轮空），agent 应输出 [SILENT] 退出
  GO                         - 可以决策，紧接着输出 JSON 数据
  ERROR:<msg>                - 脚本错误（网络/API失败），agent 应输出 [SILENT] 退出

成功路径示例输出：
  GO
  {"tournament_id": "...", "round": 3, "opponent": {...}}

退出码：
  0 = 正常完成（任何状态）
  1 = 脚本异常（unhandled exception）
"""

import json
import os
import sys
import urllib.request
import urllib.error

API_BASE = "https://www.agenthansa.com/api"
TIMEOUT = 15


def get_api_key():
    """跨服务器自适应：环境变量优先，fallback 到 ~/.hermes/agenthansa_key"""
    key = os.environ.get("AGENTHANSA_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.expanduser("~/.hermes/agenthansa_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    return None


def get_opener():
    """构建 urllib opener，自动从环境变量识别代理"""
    proxy = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        return urllib.request.build_opener(proxy_handler)
    return urllib.request.build_opener()


_OPENER = get_opener()


def api_get(path, key):
    """GET 请求，返回 (data, error_msg)。error_msg 为 None 表示成功。"""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"URL error: {e.reason}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    key = get_api_key()
    if not key:
        print("ERROR:no_api_key")
        return 0

    # Step 1: 查 live tournament
    data, err = api_get("/arena/tournaments?status=live&limit=1", key)
    if err:
        print(f"ERROR:live_query_failed:{err}")
        return 0

    items = data.get("items", [])
    if not items:
        print("NO_ACTION:no_live_tournament")
        return 0

    t = items[0]
    tid = t["id"]
    rnd = t.get("current_round", 0)

    if rnd < 1:
        print("NO_ACTION:round_not_started")
        return 0

    # Step 2: 查 my-pairing
    data, err = api_get(f"/arena/tournaments/{tid}/rounds/{rnd}/my-pairing", key)
    if err:
        print(f"ERROR:pairing_query_failed:{err}")
        return 0

    pairing = data.get("my_pairing", {})

    # Step 3: 判断状态（顺序很重要）
    if pairing.get("my_submission") is not None:
        print("ALREADY_SUBMITTED")
        return 0

    if pairing.get("is_bye"):
        print("NO_ACTION:bye_round")
        return 0

    opponent = pairing.get("opponent")
    if not opponent:
        print("NO_ACTION:eliminated_or_no_opponent")
        return 0

    # Step 4: 拉 leaderboard 给 agent 做生存判断（可选，失败不影响）
    lb_data, _ = api_get(f"/arena/tournaments/{tid}/leaderboard", key)
    leaderboard_summary = None
    if lb_data:
        stats = lb_data.get("stats", {})
        leaderboard_summary = {
            "alive_count": stats.get("alive_count"),
            "score_median": stats.get("score_median"),
            "cutoff_score": stats.get("cutoff_score"),
            "next_round_survivors": stats.get("next_round_survivors"),
        }
        # 找我自己的累计分
        my_id = None
        # 从 me 接口拿 agent_id
        me_data, _ = api_get("/agents/me", key)
        if me_data:
            my_id = me_data.get("id")
        if my_id:
            for entry in lb_data.get("items", []):
                if entry.get("agent_id") == my_id:
                    leaderboard_summary["my_cumulative_score"] = entry.get("cumulative_score")
                    leaderboard_summary["my_rank"] = entry.get("rank")
                    break

    # Step 5: 输出 GO 信号 + 对手数据
    output = {
        "tournament_id": tid,
        "round": rnd,
        "rounds_total": t.get("rounds_per_match"),
        "participant_count": t.get("participant_count"),
        "opponent": opponent,
        "leaderboard": leaderboard_summary,
    }
    print("GO")
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"ERROR:unhandled:{type(e).__name__}:{e}")
        sys.exit(1)
