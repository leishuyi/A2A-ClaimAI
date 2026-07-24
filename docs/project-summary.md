# 星盾 A2A 智能理赔助手 — 项目归纳总结

> 版本：v1.0  
> 定位：保险理赔领域的人机协同审核系统（非纯 AI Agent 系统）

---

## 一、项目真实定位

### 1.1 当前本质

```
宣称的目标架构             实际 MVP 实现
─────────────────          ─────────────────
6-Agent A2A 协同           6 个模块化服务串行调用
AI 智能理赔                硬编码模拟（无 LLM/OCR/RAG）
Agent 自主决策             无 ReAct 循环、无工具调用
自研 Agent 框架            简单 class + process() 方法
```

**一句话**：这是"披着 Agent 外衣的工作流引擎"，不是真正的 AI Agent 系统。

### 1.2 做得好的

| 维度 | 内容 |
|------|------|
| **接口设计有前瞻性** | StorageBackend 抽象、Agent 接口、A2AMessage 预留 rollback/terminate、Feature Flag 为并行留开关 |
| **全链路追溯** | Agent 输入/输出/置信度/耗时写入 DB，前端 Timeline 可视化 |
| **P0 风控真实** | 人证一致性、发票查重、逻辑校验是真正业务规则 |
| **强制人工授权** | 符合保险监管合规要求 |

### 1.3 需要正视的

| 问题 | 说明 |
|------|------|
| Agent ≠ AI Agent | 面试不能包装成 AI 决策，要说清是模拟实现 |
| 串行链路用工作流就够了 | 无条件路由/回退/并行，多 Agent 架构当前属于过度设计 |
| 自研编排器 vs LangGraph | 不上 LLM 够用；上 LLM 应直接换 LangGraph |

---

## 二、核心架构

### 2.1 分层架构

```
┌─────────────────────────────────────┐
│  前端层 (React + AntD + Vite)       │
│  路由: /cases /cases/:id /review    │
├─────────────────────────────────────┤
│  API 层 (FastAPI + SQLAlchemy)      │
│  /api/v1/cases/* — CRUD + 文件上传  │
│  /api/v1/cases/*/run — Agent 链路   │
│  /api/v1/cases/*/review — 人工授权   │
├─────────────────────────────────────┤
│  Agent 编排层 (自研 Orchestrator)    │
│  A(报案) → B(解析) → C(核责) →     │
│  D(理算) → E(风控) → F(汇总)       │
├─────────────────────────────────────┤
│  数据层 (SQLite/PostgreSQL)         │
│  cases / agent_traces / audit_logs  │
│  documents                          │
├─────────────────────────────────────┤
│  存储层 (StorageBackend 抽象)        │
│  LocalStorage / MinIO(规划)          │
└─────────────────────────────────────┘
```

### 2.2 核心数据模型

```
Case (案件)
  ├── AgentTrace (Agent 执行记录)       1:N
  ├── AuditLog (审计日志/审核记录)       1:N
  └── Document (影像材料)               1:N
        ├── extracted_name  — 文档姓名（人证比对用）
        ├── invoice_no      — 发票号码（查重用）
        └── document_date   — 单据日期（逻辑校验用）
```

### 2.3 状态机

```
DRAFT → PROCESSING → PENDING_REVIEW → APPROVED
                                    → REJECTED
```

---

## 三、Agent 通信协议（A2AMessage）

```python
@dataclass
class A2AMessage:
    message_id: str
    source_agent: str
    target_agent: str
    case_id: int
    message_type: str       # request | result_forward | rollback | terminate
    payload: dict           # 业务负载（层层累加传递）
    context: dict           # 上下文元数据
    confidence: float | None # 置信度
    error: str | None
```

**消息传递方式**：Orchestrator 维护共享 payload dict，每个 Agent 追加自己的输出，一路串行累加。

---

## 四、当前不完善的地方

### 4.1 技术层面

| 问题 | 影响 | 改进方向 |
|------|------|----------|
| 无真实 LLM/OCR | Agent B/C/D 全是模拟数据 | 接 PaddleOCR + 通义千问 |
| Payload 层层累加 | 数据膨胀，6层后含大量冗余 | 改用 Trace Store 按需读取 |
| 同步事件总线 | 无异步能力 | 升级为 Redis pub/sub |
| 无条件路由 | 无法提前终止/回退 | 用 LangGraph StateGraph |

### 4.2 设计层面

| 问题 | 说明 |
|------|------|
| Agent 架构过度设计 | 当前串行链路用工作流模式（tool chain）完全够用，多 Agent 未发挥价值 |
| 无真实 AI 能力 | 整个系统核心环节（OCR/RAG/理算）全硬编码，AI 标签全靠模拟 |
| 自研框架 vs 业界方案 | LangGraph 的 StateGraph/条件路由/并行节点完全覆盖当前需求且做得更好 |

### 4.3 演进路线

```
Phase 1 (当前)：模块化服务编排 ✅
  6 个 process() 串行调用，全硬编码，自研编排器

Phase 2：引入真实 AI
  Agent B 接 PaddleOCR，Agent C 接 LangChain RAG

Phase 3：条件路由 + 并行
  terminate 提前终止、rollback 回退、C‖D 并行

Phase 4：迁移 LangGraph
  替换自研编排器，Agent 内部改为 LLM + Tool 模式
```

---

## 五、面试高频问题速查

### Q1: 你们用的什么 Agent 框架？

**自研的轻量编排器，没用 LangChain/LangGraph。** 当前是模块化服务编排，6 个 process() 通过 A2AMessage 通信，Orchestrator 串行调度。如果上真实 LLM，计划迁移到 LangGraph。

### Q2: 多 Agent 和普通工作流有什么区别？

**当前没区别。** 串行 A→B→C→D→E→F 用工作流 + 工具调用完全能实现。多 Agent 的真正价值在条件路由、回退循环、并行计算上——这些我们都还没做。

### Q3: Agent 间上下文怎么管理的？

Orchestrator 维护共享 dict payload，一路层层累加传递。每个 Agent 读自己需要的字段，追加自己的输出。问题是 payload 会膨胀，理想方案是用独立 Trace Store（DB/Redis）按需存取。

### Q4: 为什么不用 LangGraph？

MVP 阶段想快速验证链路可追溯性和前端展示，自研轻量方案迭代更快。生产级应该用 LangGraph——它的 StateGraph 正好解决状态管理和条件路由问题。

### Q5: 你们系统是 AI Agent 系统吗？

**不是真正的 AI Agent 系统。** 当前是模块化服务编排 + 人工审核工作台，核心价值在流程标准化和全链路追溯，不在 AI 决策。Agent B/C/D/E 当前全是模拟实现。

### Q6: 项目亮点是什么？

1. **全链路追溯**：6 个节点中间结果可视化，人工可逐级下钻
2. **强制人工授权**：AI 只出建议，最终审核权在核赔人员手中
3. **接口设计有前瞻性**：存储、Agent、通信协议都做了抽象，为后续升级留了接口
4. **风控 P0 真实**：人证一致性、发票查重是真正的业务规则
