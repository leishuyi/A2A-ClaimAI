# 星盾 StarShield — A2A 智能理赔助手

星联合健康保险 A2A 智能理赔助手，基于 6-Agent 协同架构，实现"Agent 协同处理 + 人工最终授权"的理赔审核闭环。

## 架构概览

```
报案受理 Agent A → 材料解析 Agent B → 核责判断 Agent C → 
理算 Agent D → 风控审查 Agent E → 结论汇总 Agent F → 人工授权 Gate
```

## 快速启动

```bash
# 启动全部服务（PostgreSQL + Backend + Frontend）
docker-compose up -d

# 访问前端
open http://localhost:5173

# API 文档
open http://localhost:8000/docs
```

## 使用流程

1. **新建报案** — 填写出险人、险种、出险描述等信息
2. **执行 Agent 链路** — 一键触发 6 个 Agent 协同处理
3. **查看追溯** — 全链路 Agent 推理过程可下钻查看
4. **人工授权** — 核赔人员审核 AI 建议，执行通过/驳回/修改后通过

## 项目结构

```
starshield/
├── backend/          # FastAPI + SQLAlchemy + PostgreSQL
│   └── app/
│       ├── agents/   # 6 个 Agent + 编排器
│       ├── routers/  # REST API
│       └── database/ # 数据模型
├── frontend/         # React + TypeScript + Ant Design
│   └── src/
│       ├── pages/    # 案件列表 / 详情 / 授权工作台
│       └── components/
└── docker-compose.yml
```

## 分阶段实施参考

| Phase | 内容 | 周期 |
|-------|------|------|
| MVP | 当前完整项目（模拟OCR/LLM/RAG） | 可立即部署 |
| Phase 2 | 接入真实 OCR + LLM API | 2-3周 |
| Phase 3 | RAG 知识库 + 向量检索 | 2-3周 |
| Phase 4 | 异步消息队列 + 生产加固 | 2周 |
