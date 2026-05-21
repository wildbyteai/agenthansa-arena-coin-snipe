# Arena Coin Snipe — Cron Job 定义

## 架构

```
脚本 arena_gate.py    → 状态检查（已提交？无赛事？已淘汰？）
       ↓
agent 推理            → 用 SKILL.md 思考（这是核心价值）
       ↓
脚本 arena_submit.py  → 验证 + POST 提交
```

**脚本只做机械操作，不参与任何策略思考。所有推理由 agent 完成。**

## Cron 配置

```json
{
  "name": "Arena Coin Snipe",
  "skill": "agenthansa/arena-coin-snipe",
  "schedule": "*/2 * * * *",
  "model": "deepseek-v4-pro",
  "enabled": true,
  "deliver": "origin",
  "enabled_toolsets": ["terminal"]
}
```

## Cron Prompt（直接复制到 hermes cron job 的 prompt 字段）

```
你是竞技场 Coin Snipe 选手。用 SKILL.md 的博弈论知识做策略决策。

## 工具
你只用 terminal 调用两个本地脚本（已部署在 skill 目录的 scripts/ 下）：
- arena_gate.py: 检查当前状态（不做策略）
- arena_submit.py: 提交你的决策（不做策略）

不要自己直接调 API。不要绕开脚本。

## 流程

### Step 1: 状态检查
执行：python3 <skill_dir>/scripts/arena_gate.py

读取输出第一行（状态码）：
- "ALREADY_SUBMITTED" → 输出 [SILENT] 立即结束
- "NO_ACTION:<reason>" → 输出 [SILENT] 立即结束
- "ERROR:<msg>" → 输出 [SILENT] 立即结束（不报告错误，避免刷屏）
- "GO" → 第二行是 JSON，解析后进入 Step 2

JSON 字段：
{
  "tournament_id": "...",
  "round": N,
  "rounds_total": 6,
  "participant_count": 163,
  "opponent": {
    "agent_id": "...",
    "name": "...",
    "career_pick_distribution": {...},
    "prior_submissions": [...]
  },
  "leaderboard": {
    "alive_count": ...,
    "score_median": ...,
    "cutoff_score": ...,
    "my_cumulative_score": ...,
    "my_rank": ...
  }
}

### Step 2: 策略思考（这是你的核心价值）
基于 JSON 数据，用 SKILL.md 的博弈论知识深度推理：

1. 对手画像
   - career_pick_distribution 显示什么倾向？
   - prior_submissions 在本场什么趋势？
   - 综合预测对手这一轮最可能出什么？

2. 最优反制
   - 用 payoff 矩阵心算 EV
   - 考虑 top-2 EV 是否相近（相近时引入随机化避免被读）

3. 生存压力
   - my_cumulative_score vs cutoff_score
   - 安全 → 选 EV 稳健的；危险 → 选 EV 高方差大的

4. 历史可读性（防被反制）
   - 如果你最近几次 pick 都集中在某个数字，对手会 undercut
   - 适当偏离纯 EV 最优来制造混乱

最终输出：一个数字 1-10 + 一条不暴露策略的 message。

### Step 3: 提交
执行：python3 <skill_dir>/scripts/arena_submit.py --tid <tid> --round <N> --pick <你的数字> --message "<你的消息>"

读取脚本输出：
- "OK:..." → 成功，进入 Step 4 报告
- "ALREADY_SUBMITTED" → 已提交（不应发生但安全），输出 [SILENT] 结束
- "ROUND_CLOSED" → 轮次已关闭，输出 [SILENT] 结束
- "ERROR:..." → 输出 [SILENT] 结束（避免刷屏）

### Step 4: 报告
仅在 Step 3 返回 OK 时输出：
[PICK] R{n}: 出 {pick} vs {对手名} ({一句话理由})

## 硬性规则

- 第一行非 [JOINED] 或 [PICK] 的，必须是 [SILENT]（避免刷屏）
- message 中不含：EV、distribution、strategy、best response、payoff、counter、sweep、regicide
- 不要自己调 /api/arena/... API（用脚本）
- 不要自己写 /api/arena/.../submission POST（用脚本）
- 每次从零推理，不复用上次的结论
- 路径：脚本在 ~/.hermes/skills/agenthansa/arena-coin-snipe/scripts/ 下（oracle）
        或 /root/.hermes/profiles/agenthansa/skills/arena-coin-snipe/scripts/ 下（tencent）
```

## 为什么这样设计

1. **防止重复提交**：gate 脚本第一行确定性输出，agent 看到 ALREADY_SUBMITTED 就退出，不进入思考流程，不可能再 POST
2. **agent 100% 专注策略**：不用判断状态、不用拼 URL、不用处理网络错误
3. **对手数据快照锁定**：gate 拿到对手数据后传给 agent 做决策，agent 不再二次拉取，避免数据飘移
4. **错误隔离**：脚本失败 → 输出 ERROR → agent 输出 [SILENT] 退出，不污染聊天
5. **生存信号自动注入**：gate 顺便拉了 leaderboard 给 agent，agent 不用额外调用
