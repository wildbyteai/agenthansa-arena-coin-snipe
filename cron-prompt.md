# Arena Coin Snipe — Cron Job 定义

## 设计原则

- Prompt 只给具体的 terminal 命令，不描述数据结构
- 模型必须执行 terminal 才能获得信息，无法"脑补"
- 本地 state 文件做幂等检查（API 的 my_submission 字段不可靠）
- SKILL.md 通过 skill 引用自动注入 context，提供博弈论知识

## Cron 配置

```json
{
  "name": "Arena Coin Snipe",
  "skill": "agenthansa/arena-coin-snipe",
  "schedule": "*/2 * * * *",
  "enabled": false,
  "deliver": "origin",
  "enabled_toolsets": ["terminal"]
}
```

## Oracle Prompt

```
执行竞技场出牌任务。严格按步骤用 terminal 执行，每一步都必须看到真实输出后再继续。

Step 1: 读取 API key
terminal: KEY=$(cat ~/.hermes/agenthansa_key) && echo "KEY_OK"

Step 2: 查赛事状态
terminal: curl -s -H "Authorization: Bearer $(cat ~/.hermes/agenthansa_key)" "https://www.agenthansa.com/api/arena/tournaments?status=live&limit=1"

如果 items 为空：
  terminal: curl -s -H "Authorization: Bearer $(cat ~/.hermes/agenthansa_key)" "https://www.agenthansa.com/api/arena/tournaments/upcoming"
  如果有结果 → terminal: curl -s -X POST -H "Authorization: Bearer $(cat ~/.hermes/agenthansa_key)" -H "Content-Type: application/json" -d "{}" "https://www.agenthansa.com/api/arena/tournaments/{id}/participants"
  输出 [JOINED] 或 [SILENT] → 结束

如果 items 有赛事 → 记住 tid 和 current_round，继续。

Step 3: 幂等检查
terminal: cat ~/.hermes/arena_state.json 2>/dev/null || echo "{}"

检查 submitted 数组里有没有 "{tid}_R{round}"。有 → 输出 [SILENT] 结束。

Step 4: 查对手
terminal: curl -s -H "Authorization: Bearer $(cat ~/.hermes/agenthansa_key)" "https://www.agenthansa.com/api/arena/tournaments/{tid}/rounds/{round}/my-pairing"

如果 is_bye=true 或 opponent 为空 → [SILENT] 结束。
否则读取对手的 career_pick_distribution 和 prior_submissions。

Step 5: 决策
用 SKILL.md 的博弈论知识推理：对手最可能出什么？我的最优反制？
选一个数字 1-10 和一条短 message（不暴露策略）。

Step 6: 提交
terminal: curl -s -X POST -H "Authorization: Bearer $(cat ~/.hermes/agenthansa_key)" -H "Content-Type: application/json" -d '{"submission": N, "message": "xxx"}' "https://www.agenthansa.com/api/arena/tournaments/{tid}/rounds/{round}/submission"

Step 7: 写 state 防重复
terminal: python3 -c "import json,os; f=os.path.expanduser('~/.hermes/arena_state.json'); s=json.load(open(f)) if os.path.exists(f) else {}; s.setdefault('submitted',[]).append('{tid}_R{round}'); s['submitted']=s['submitted'][-50:]; json.dump(s,open(f,'w'))"

Step 8: 输出
[PICK] R{round}: 出 {N} vs {对手名} ({一句话理由})

硬性规则：
- 每一步必须用 terminal 执行并看到真实输出，不要跳步
- 无动作时输出 [SILENT]
- message 不含技术词汇（EV、strategy、payoff 等）
```

## Tencent Prompt

同上，区别：
- Key: `$AGENTHANSA_API_KEY`（环境变量）
- 所有 curl 加 `--proxy http://127.0.0.1:7890`
- State 文件: `~/arena_state.json`
