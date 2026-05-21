#!/usr/bin/env python3
"""
Arena Play — 完整的竞技场出牌脚本

流程全部确定性，只有"选数字"这一步调 LLM。
不依赖 hermes agent 的 tool use 能力。

用法：
  python3 arena_play.py

环境变量：
  AGENTHANSA_API_KEY 或 ~/.hermes/agenthansa_key
  NEWAPI_API_KEY 或从 hermes .env 读取
  http_proxy / https_proxy（可选）
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error

API_BASE = "https://www.agenthansa.com/api"
TIMEOUT = 15

# LLM 配置：从环境或 hermes .env 读取
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:3000/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.6-plus")

SKILL_KNOWLEDGE = """你是博弈论专家。Coin Snipe 游戏规则：
两人同时选 1-10。低数赢，得 floor((a+b)/2)。同数双 0。10 sweep 1-5（得 10），但输给 6-9。

Payoff 矩阵（行=我，列=对手，值=我的得分）：
       1   2   3   4   5   6   7   8   9  10
  1  [ 0,  1,  2,  2,  3,  3,  4,  4,  5,  0]
  2  [ 0,  0,  2,  3,  3,  4,  4,  5,  5,  0]
  3  [ 0,  0,  0,  3,  4,  4,  5,  5,  6,  0]
  4  [ 0,  0,  0,  0,  4,  5,  5,  6,  6,  0]
  5  [ 0,  0,  0,  0,  0,  5,  6,  6,  7,  0]
  6  [ 0,  0,  0,  0,  0,  0,  6,  7,  7,  8]
  7  [ 0,  0,  0,  0,  0,  0,  0,  7,  8,  8]
  8  [ 0,  0,  0,  0,  0,  0,  0,  0,  8,  9]
  9  [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  9]
 10  [10, 10, 10, 10, 10,  0,  0,  0,  0,  0]

赛制：每轮淘汰累计分底部 50%。生存优先。

你的任务：根据对手数据，选一个 1-10 的数字。
思考：对手最可能出什么？我的最优反制是什么？生存压力如何？
"""


def get_api_key():
    key = os.environ.get("AGENTHANSA_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.expanduser("~/.hermes/agenthansa_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    return None


def get_llm_key():
    key = os.environ.get("NEWAPI_API_KEY", "").strip()
    if key:
        return key
    # 尝试从 hermes .env 读取
    for env_path in [
        os.path.expanduser("~/.hermes/.env"),
        "/root/.hermes/profiles/agenthansa/.env",
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("NEWAPI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"')
    return None


def get_opener():
    proxy = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener()


OPENER = get_opener()


def api_get(path, key):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def api_post(path, key, body=None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:200]
        except Exception:
            pass
        return None, f"HTTP {e.code}: {body_text}"
    except Exception as e:
        return None, str(e)


def ask_llm(prompt, llm_key):
    """调 LLM API，返回文本响应"""
    url = f"{LLM_BASE_URL}/chat/completions"
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300,
    }).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {llm_key}",
            "Content-Type": "application/json",
        },
    )
    # LLM 调用不走外网 proxy（本机服务）
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return None


def parse_pick(llm_response):
    """从 LLM 响应中提取 1-10 的数字"""
    if not llm_response:
        return None
    # 尝试多种模式
    # 模式1: PICK=N
    m = re.search(r'PICK\s*[=:]\s*(\d+)', llm_response)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 10:
            return n
    # 模式2: 出 N
    m = re.search(r'出\s*(\d+)', llm_response)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 10:
            return n
    # 模式3: 第一个出现的 1-10 数字
    for m in re.finditer(r'\b(\d+)\b', llm_response):
        n = int(m.group(1))
        if 1 <= n <= 10:
            return n
    return None


def parse_message(llm_response):
    """从 LLM 响应中提取 message"""
    if not llm_response:
        return "gg"
    m = re.search(r'MSG\s*[=:]\s*["\']?([^"\'\n]+)', llm_response)
    if m:
        return m.group(1).strip()[:50]
    return "gg"


def main():
    key = get_api_key()
    if not key:
        return

    # Step 1: 查 live tournament
    data, err = api_get("/arena/tournaments?status=live&limit=1", key)
    if err or not data.get("items"):
        # 没有 live，尝试加入 upcoming
        upcoming, err = api_get("/arena/tournaments/upcoming", key)
        if err or not upcoming or not upcoming.get("id"):
            print("[SILENT]")
            return
        # 加入
        _, join_err = api_post(f"/arena/tournaments/{upcoming['id']}/participants", key)
        if join_err and "409" not in join_err:
            print("[SILENT]")
            return
        if not join_err:
            print(f"[JOINED] {upcoming['id'][:8]} ({upcoming.get('participant_count', '?')} agents)")
        else:
            print("[SILENT]")
        return

    t = data["items"][0]
    tid = t["id"]
    rnd = t.get("current_round", 0)
    if rnd < 1:
        print("[SILENT]")
        return

    # Step 2: 本地幂等检查（API 的 my_submission 字段不可靠，永远返回 null）
    state_file = os.path.expanduser("~/.hermes/arena_state.json")
    state = {}
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                state = json.load(f)
    except (json.JSONDecodeError, IOError):
        state = {}

    submitted_key = f"{tid}_R{rnd}"
    if submitted_key in state.get("submitted", []):
        print("[SILENT]")
        return

    # Step 3: 查 my-pairing
    pairing_data, err = api_get(f"/arena/tournaments/{tid}/rounds/{rnd}/my-pairing", key)
    if err:
        print("[SILENT]")
        return

    p = pairing_data.get("my_pairing", {})

    # 轮空
    if p.get("is_bye"):
        print("[SILENT]")
        return

    # 已淘汰
    opponent = p.get("opponent")
    if not opponent:
        print("[SILENT]")
        return

    # Step 3: 拉 leaderboard
    lb_data, _ = api_get(f"/arena/tournaments/{tid}/leaderboard", key)
    lb_info = ""
    if lb_data:
        stats = lb_data.get("stats", {})
        me_data, _ = api_get("/agents/me", key)
        my_id = me_data.get("id") if me_data else None
        my_score = None
        if my_id:
            for entry in lb_data.get("items", []):
                if entry.get("agent_id") == my_id:
                    my_score = entry.get("cumulative_score")
                    break
        lb_info = f"\n我的累计分: {my_score}, cutoff: {stats.get('cutoff_score')}, 存活: {stats.get('alive_count')}人"

    # Step 4: 构造 LLM prompt
    opp_name = opponent.get("name", "unknown")
    career_dist = opponent.get("career_pick_distribution", {})
    prior_subs = [s.get("submission") for s in opponent.get("prior_submissions", [])]

    llm_prompt = f"""{SKILL_KNOWLEDGE}

当前对手: {opp_name}
对手历史出牌分布: {json.dumps(career_dist)}
对手本场已出牌: {prior_subs}
当前轮次: R{rnd}{lb_info}

请选择你的出牌（1-10），格式：
PICK=<数字>
MSG=<一条短消息，不暴露策略>
REASON=<一句话理由>"""

    # Step 5: 调 LLM
    llm_key = get_llm_key()
    if not llm_key:
        # fallback: 出 6（vs uniform EV 最高）
        pick, msg, reason = 6, "gg", "no_llm_fallback"
    else:
        llm_response = ask_llm(llm_prompt, llm_key)
        pick = parse_pick(llm_response)
        msg = parse_message(llm_response)
        reason = ""
        if llm_response:
            m = re.search(r'REASON\s*[=:]\s*(.+)', llm_response)
            if m:
                reason = m.group(1).strip()[:80]
        if not pick:
            pick = 6  # fallback
            reason = "parse_failed_fallback"
        if not reason:
            reason = "llm_decided"

    # Step 6: 提交
    result, err = api_post(
        f"/arena/tournaments/{tid}/rounds/{rnd}/submission",
        key,
        {"submission": pick, "message": msg},
    )
    if err:
        if "409" in err:
            print("[SILENT]")
        else:
            print("[SILENT]")
        return

    # Step 7: 写入本地 state 防重复
    submitted = state.get("submitted", [])
    submitted.append(submitted_key)
    state["submitted"] = submitted[-50:]  # 只保留最近 50 条
    state["tournament_id"] = tid
    state["last_pick"] = {"round": rnd, "pick": pick, "vs": opp_name}
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, ensure_ascii=False)
    except IOError:
        pass

    print(f"[PICK] R{rnd}: 出 {pick} vs {opp_name} ({reason})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[SILENT]")
        sys.exit(0)
