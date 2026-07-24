# A2A 智能理赔助手 — 面试高频问答

> 本文档覆盖面试官可能围绕本项目提出的常见问题，按「项目做法 → 为什么这样设计 → 优缺点 → 改进方向」四段式组织。

---

## 目录

- [一、架构设计类](#一架构设计类)
- [二、技术选型类](#二技术选型类)
- [三、数据流与状态管理类](#三数据流与状态管理类)
- [四、风控与安全类](#四风控与安全类)
- [五、扩展性与性能类](#五扩展性与性能类)
- [六、权衡与演进类](#六权衡与演进类)

---

## 一、架构设计类

### Q1: 为什么采用 6-Agent 架构，而不是传统的单体服务或微服务？

**项目做法：**  
将理赔流程拆解为 6 个独立的 Agent（报案受理 → 材料解析 → 核责判断 → 理算 → 风控审查 → 结论汇总），每个 Agent 是一个独立模块，通过标准化的 A2AMessage 协议通信，由编排器（Orchestrator）串行调度。

**为什么这样设计：**
- **职责单一**：理赔涉及多个不同能力——信息采集、OCR、法律条款匹配、计算、风控、报告生成，拆成独立 Agent 便于独立开发和测试
- **可追溯**：每个 Agent 的输入/输出/置信度/耗时都持久化到 `agent_traces` 表，形成全链路审计轨迹
- **渐进式落地**：MVP 可以串行跑通全链路，后续再优化单个 Agent（如 Agent B 从模拟OCR替换为真实PaddleOCR）

**优缺点：**
| 优势 | 劣势 |
|------|------|
| 每个 Agent 可独立演进、替换、扩缩 | Agent 间通过 payload 传参，payload 膨胀 |
| 全链路可追溯，人工可逐级下钻 | 串行编排下延迟累加（6 Agent × ~2s = 12s） |
| 新增 Agent 只需实现 process() 接口 | 降级/回退策略尚未完全实现 |

**改进方向：**
- 引入并行编排：核责(C)和理算(D)数据依赖不冲突时可同时执行
- 使用消息队列（如 RabbitMQ）替代同步调用，解耦 Agent 生命周期
- 增加 Agent 超时熔断机制

---

### Q2: A2A 通信协议为什么这么设计？为什么不用现成的 Agent 框架（LangGraph/CrewAI）？

**项目做法：**  
定义了轻量 `A2AMessage` 数据类，包含 `message_id`, `source/target_agent`, `case_id`, `message_type`, `payload`, `context`, `confidence`。

```python
@dataclass
class A2AMessage:
    message_id: str
    source_agent: str
    target_agent: str
    case_id: int
    message_type: str  # request | result_forward | rollback | terminate
    payload: dict[str, Any]
    confidence: Optional[float] = None
    error: Optional[str] = None
```

**为什么这样设计：**

- **轻量无依赖**：不需要引入 LangGraph/CrewAI 等重框架，MVP 阶段用简单数据类传递就够
- **置信度透传**：每个 Agent 输出都带 `confidence`，最终人工审核时能看到全链路置信度
- **预留扩展**：`message_type` 定义了 rollback/terminate 类型，为后续回退策略留了接口

**不用现成框架的原因：**

| 对比维度 | 自研方案 | LangGraph/CrewAI |
|----------|----------|------------------|
| 学习成本 | 低，一文件搞定 | 高，需要学 StateGraph/Node/Edge 概念 |
| 灵活性 | 完全可控 | 受框架约束 |
| 追溯集成 | 直接写 DB，结构可控 | 需要适配层 |
| 适合场景 | MVP/原型验证 | 生产级复杂编排 |

**改进方向：**
- 如果需要并行编排、条件路由、Agent 间动态协商，可迁移到 LangGraph
- 可引入 protobuf 序列化替代 dict，提升跨语言兼容性

---

### Q3: 为什么强制人工授权？AI 都处理完了为什么还要人点一下？

**项目做法：**  
案件经过 6 个 Agent 处理后，状态变为 `pending_review`，必须由核赔人员在 HumanGate 工作台点击「通过」「驳回」或「修改后通过」才能完结。AI 只生成"审核建议"，不直接执行赔付。

**为什么这样设计：**
- **监管合规**：保险理赔涉及资金赔付，银保监会要求核赔人员最终审核
- **责任归属**：AI 的错误无法追责，但核赔人员可以
- **兜底机制**：AI 可能在罕见场景下出错（如罕见病条款误读），人工是最后一道防线
- **行业实践**：元保、慧择、太保灵析、国任等行业方案都强调人工复核环节

**优缺点：**

```
优势：合规、可追责、安全兜底
劣势：无法做到全自动秒赔（但小额场景可通过快速确认优化）
```

**改进方向：**
- 做风险分层：低风险(≥90%置信度) → AI自动通过 + 事后抽查；中高风险 → 人工审核
- 快速确认按钮：一键通过 + 自动填充操作人（系统审核）

---

## 二、技术选型类

### Q4: 为什么后端选 FastAPI 而不是 Flask/Django/Spring Boot？

| 维度 | FastAPI | Flask | Django | Spring Boot |
|------|---------|-------|--------|-------------|
| 异步支持 | 原生 async | 需插件 | 3.1 后支持 | WebFlux |
| 性能 | 快（Starlette） | 一般 | 一般 | 好 |
| 自动文档 | Swagger/ReDoc 自动生成 | 需 flask-restx | 需 drf-spectacular | SpringDoc |
| 数据校验 | Pydantic 原生 | 需 marshmallow | DRF Serializer | Jakarta Validation |
| MVP 迭代速度 | 快 | 快 | 中 | 慢 |

**项目做法：** 选 FastAPI 的核心原因：
- Pydantic v2 + Python 3.11 类型注解，一套定义校验 + 序列化
- 自动生成 OpenAPI 文档，前后端联调效率高
- 异步 lifespan 管理 DB 连接池和事件总线生命周期
- Python 生态在 AI/ML 领域（OCR/LLM 调用）的优势

---

### Q5: 数据库为什么用 SQLAlchemy？为什么开发环境用 SQLite、生产用 PostgreSQL？

**项目做法：**  
使用 SQLAlchemy ORM，通过 `DATABASE_URL` 环境变量切换数据库，开发环境默认 `sqlite:///./starshield.db`，`docker-compose.yml` 配置了 PostgreSQL 16。

```
开发环境: SQLite（零配置、文件级、适合单机开发）
生产环境: PostgreSQL（高并发、事务、PGVector 扩展可做 RAG）
```

**SQLAlchemy 的优势：**
- **数据库无关**：ORM 层屏蔽 SQL 方言差异，切换 DB 只需改一行 URL
- **关系映射**：Case ↔ AgentTrace ↔ AuditLog ↔ Document 的关联关系通过 `relationship()` 声明式管理
- **迁移友好**：预留了 Alembic 依赖，后续可用 `alembic migrate` 管理 schema 变更

**为什么不能 SQLite 上生产：**
- SQLite 不支持并发写（写锁是表级）
- 缺少 PGVector 等扩展（后续 RAG 条款匹配需要）
- 无连接池管理，高并发下连接数会爆

---

## 三、数据流与状态管理类

### Q6: 描述一条完整的影像上传到 Agent 解析的数据流？

**完整链路：**

```
用户操作             前端                    后端 API                 文件存储              Agent 链路
────────────────     ──────────              ────────────             ────────              ──────────
1. 填写报案信息
                     POST /cases (JSON)
                                            → 创建 Case (DRAFT)
                                            → 返回 case_id
2. 选择影像文件
3. 提交报案
                     POST /cases/{id}/documents (multipart)
                                            → 校验文件类型/大小
                                            → 生成 UUID 文件名
                                            → 保存文件 ───────────→ data/uploads/{id}/{uuid}.ext
                                            → 写入 Document 记录
                                            → 检测发票号是否重复
                                            → 返回文档元信息
4. 点击"执行Agent"
                     POST /cases/{id}/run
                                            → 状态 → PROCESSING
                                            → Agent A 读取 Case + Document 元数据
                                            → Agent B 模拟 OCR 提取信息
                                            → Agent C 核责判断
                                            → Agent D 理算
                                            → Agent E 风控（人证/发票/逻辑校验）
                                            → Agent F 汇总
                                            → 状态 → PENDING_REVIEW
5. 进入人工授权
                     GET /cases/{id}/review
6. 审核操作
                     POST /cases/{id}/review
                                            → 状态 → APPROVED/REJECTED
                                            → 写入 AuditLog
```

**关键设计点：**
- 上传和报案是异步的：先报案拿到 case_id，再逐个上传文件绑定到案件
- Agent A 从 DB 加载 Document 元数据注入 payload，确保风控 Agent 能获取文档信息
- 每个 Agent 的中间结果持久化到 `agent_traces`，实现全链路追溯

---

### Q7: 状态机是怎么设计的？为什么用 Enum 而不是字符串？

**项目做法：**  
使用 Python `enum.Enum` 定义案件状态，状态字段在 ORM 层映射为 `SAEnum`：

```python
class CaseStatus(str, enum.Enum):
    DRAFT = "draft"              # 待处理
    PROCESSING = "processing"    # 处理中
    AGENTS_COMPLETED = "agents_completed"  # Agent完成（暂未使用）
    PENDING_REVIEW = "pending_review"  # 待审核
    APPROVED = "approved"        # 已通过
    REJECTED = "rejected"        # 已驳回
```

**状态流转：**
```
DRAFT → PROCESSING → PENDING_REVIEW → APPROVED
                                    → REJECTED
```

**为什么用 Enum 而不是裸字符串：**
- **编译期检查**：IDE 自动补全，拼写错误在编码阶段就被发现
- **可追溯**：`CaseStatus.PENDING_REVIEW` 比 `"pending_review"` 更语义化，IDE 跳转定义更快
- **序列化兼容**：继承 `str` 的 Enum 可以直接 JSON 序列化

---

### Q8: 事件总线（EventBus）的作用是什么？为什么是同步的？

**项目做法：**  
实现了一个轻量同步的发布-订阅模式的事件总线：

```python
event_bus.publish("agent.completed", {"case_id": 1, "agent": "agent_a"})
event_bus.publish("case.pending_review", {"case_id": 1})
```

目前注册了两个事件：`agent.completed` 和 `case.pending_review`。

**为什么是同步的：**
- **MVP 够用**：当前没有需要异步处理的订阅者（没有邮件通知、webhook 等）
- **简化部署**：不需要 Redis/RabbitMQ 等中间件，零依赖启动

**为什么还要做事件总线而不是直接调用：**
- **解耦**：发布者不需要知道订阅者是谁，新增订阅者不需要改发布者代码
- **预留升级路径**：后续从同步切换到 Redis pub/sub，替换 `EventBus` 实现即可，业务代码不需要改

---

## 四、风控与安全类

### Q9: 怎么防止用户传伪造材料？

**项目做法（P0 已实现）：**  
Agent E（风控审查）实现了三项硬校验：

```
① 人证一致性
   文档姓名 vs 报案姓名 → 不一致则标记"高风险"
   示例：发票上姓名"张三" vs 报案姓名"李四" → 标记

② 发票号全局查重
   上传时检查该发票号是否已在其他案件中使用
   示例：发票号 INV202407001 在案件 #2 中已存在 → 标记

③ 逻辑一致性
   单据日期 vs 出险日期（不超过出险后30天，不早于出险前7天）
   金额合理性（不超过100万）
   示例：发票日期 2024-09-01 但出险日期 2024-07-20 → 异常标记
```

**计划中但未实现（P1/P2）：**

| 能力 | 方案 | 优先级 |
|------|------|--------|
| 影像篡改检测 | ELA 算法检测 PS 痕迹 | P1 |
| EXIF 元数据分析 | 检查拍摄设备、修改时间 | P1 |
| 黑名单机构 | 对接卫健委 API 校验医院真实性 | P2 |
| 历史关联分析 | 图数据库查同一人短期多次出险 | P2 |
| OCR 真实接入 | 替换 Agent B 的模拟 OCR 为 PaddleOCR | P1 |

---

### Q10: 人证一致性怎么做模糊匹配的？遇到复姓/生僻字怎么办？

**项目做法：**

```python
def _normalize_name(self, name: str) -> str:
    """姓名归一化：去空格、全半角转半角"""
    return name.replace(" ", "").replace("　", "").strip()
```

当前是精确归一化比对（去空格 + 全半角统一）。这层处理能覆盖：
- 用户输入「张 三」vs OCR 识别「张三」
- 用户输入「张 三」vs 影像「张　三」（全角空格）

**局限性（后续改进方向）：**

| 场景 | 当前 | 改进后 |
|------|------|--------|
| 音同字不同（峰/锋） | 判不匹配 | 引入拼音相似度 |
| 复姓（欧阳/欧陽） | 繁简不一致会判不匹配 | 繁简归一化 |
| 别名/曾用名 | 无法匹配 | 对接客户信息系统的别名库 |

---

## 五、扩展性与性能类

### Q11: 如果后续需要对接真实 OCR（PaddleOCR/腾讯云 OCR），怎么改？

**项目做法（预留的扩展点）：**  
只需要替换 Agent B 的实现，其他模块完全不需要改。

```python
# 当前：模拟 OCR
class DocParserAgent(BaseAgent):
    def process(self, message, db):
        extracted = {"diagnosis": self._extract_diagnosis(desc)}
        ...

# 改后：真实 OCR
class DocParserAgent(BaseAgent):
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    
    def process(self, message, db):
        # 从 payload 获取文档信息
        docs = message.payload.get("documents", [])
        for doc in docs:
            file_path = doc["file_path"]
            # 读取文件内容进行 OCR
            result = self.ocr.ocr(file_path)
            extracted = self._parse_ocr_result(result)
        ...
```

**为什么能做到无侵入替换：**
- Agent 基类定义了 `process()` 接口，入参出参统一
- payload 中已有文档元数据和存储路径，OCR Agent 可直接读取
- 置信度机制本身就是为真实 OCR 设计的（模拟置信度后面会被真实置信度取代）

---

### Q12: 文件存储现在用的是本地文件系统，怎么切换 MinIO/S3？

**项目做法（StorageBackend 抽象）：**

```python
class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_content, relative_path) -> str: ...
    @abstractmethod
    def get(self, relative_path) -> bytes: ...
    @abstractmethod
    def delete(self, relative_path) -> bool: ...
    @abstractmethod
    def get_url(self, relative_path) -> str: ...

class LocalStorage(StorageBackend): ...  # 当前实现
class MinioStorage(StorageBackend): ...  # 后续添加
```

**切换方式：** 改一行工厂函数：

```python
def get_storage_backend() -> StorageBackend:
    if settings.app_env == "production":
        return MinioStorage(endpoint=settings.minio_endpoint)
    return LocalStorage()
```

整个过程对业务代码完全透明，因为所有文件操作都通过 `StorageBackend` 接口。

---

### Q13: Agent 链路目前是串行的，怎么改成并行？

**项目做法（预留了 feature flag）：**  
`config.py` 中已有 `feature_agent_parallel: bool = False`，为并行编排预留了开关。

**并行方案：**
```
串行: A → B → C → D → E → F   (6 × t = 总时间)
并行: A → B → (C ‖ D) → E → F  (5 × t，核责和理算并行)
```

**实现思路：**

```python
# orchestrator.py 中的并行段落
if settings.feature_agent_parallel:
    # C 和 D 并行执行
    with ThreadPoolExecutor() as executor:
        future_c = executor.submit(self.agents["agent_c_liability"].process, msg_c, db)
        future_d = executor.submit(self.agents["agent_d_calculation"].process, msg_d, db)
        result_c = future_c.result()
        result_d = future_d.result()
        payload = {**result_c.payload, **result_d.payload}
```

**为什么 MVP 不做并行：**
- 串行链路更容易调试和追溯
- Agent B/C/D/E 当前都是 ~2ms 的模拟实现，并行收益为 0
- 等真实 OCR/LLM 接入后，Agent 耗时变成秒级，再启用并行

---

## 六、权衡与演进类

### Q14: 为什么 Agent B/C/D/E 当前都是模拟实现？

| Agent | 模拟内容 | 真实集成方向 |
|-------|----------|-------------|
| B 材料解析 | OCR 识别（硬编码诊断）、置信度随机 | PaddleOCR + 多模态 LLM |
| C 核责判断 | RAG 检索模拟、免责条款硬编码 | LangChain + Milvus 向量库 |
| D 理算 | 分项计算硬编码（比例固定） | Drools 规则引擎 |
| E 风控审查 | 部分逻辑已真实实现（P0） | 图数据库、图像篡改检测 |

**为什么 MVP 阶段用模拟：**
- **快速验证架构**：6-Agent 链路是否能跑通、状态流转是否正确、前端展示是否完整
- **降低成本**：真实 OCR/LLM 需要 API 费用（PaddleOCR 免费但部署有成本）
- **风险可控**：模拟数据让前端开发和联调不受外部服务可用性影响

**什么时候切换真实实现：**
- 确定合作的 OCR 服务商（PaddleOCR/腾讯云 OCR）
- 确定 LLM 供应商（通义千问/DeepSeek）
- 险种条款结构化完成（RAG 知识库构建）

---

### Q15: 你们的数据模型设计中，为什么 Case 要用软删除（deleted_at）？

**项目做法：**  

```python
class Case(Base):
    deleted_at = Column(DateTime, nullable=True, index=True)
```

所有查询都过滤 `Case.deleted_at.is_(None)`，删除操作只是设置时间戳而非真删除。

**为什么：**
- **监管要求**：保险理赔数据不允许物理删除，需保留全量审计轨迹
- **数据恢复**：误删可以找回
- **关联保护**：AgentTrace/AuditLog/Document 通过外键关联，软删除不会破坏引用完整性

---

### Q16: 幂等防重怎么做的？防止审核员重复点击提交？

**项目做法：**  
审核提交时基于 `case_id + action + operator + date` 生成 SHA256 哈希作为幂等键：

```python
raw = f"{case_id}:{action}:{operator}:{date.today()}"
idempotency_key = hashlib.sha256(raw.encode()).hexdigest()
```

`audit_logs` 表的 `idempotency_key` 字段设置了 `unique=True`，重复提交会触发数据库唯一约束异常，被捕获后返回已有记录。

**为什么不用前端防重（按钮置灰）：**
- 前端防重可以被绕过（刷新页面、多标签页、API 直接调用）
- 幂等是后端安全底线，即使前端没做防重，后端也不会产生重复数据

---

### Q17: 你们的前端为什么选 React + Ant Design，而不是 Vue？

| 维度 | React + AntD | Vue + Element |
|------|-------------|---------------|
| 组件丰富度 | AntD 5 的 Table/Form/Upload/Timeline 覆盖需求 | Element Plus 同样丰富 |
| TypeScript 支持 | 天然优秀（tsx） | 需要额外配置 |
| Dialog/Modal 嵌套 | 良好 | 良好 |
| Table 虚拟滚动 | AntD 5 支持虚拟列表 | Element 需插件 |

**真实原因：** 技术栈一致性。团队 React 经验更多，Ant Design 5 的组件 API 和设计模式适配企业级后台效率高。具体到本项目：

- `CaseList.tsx` 的 Table + Modal + Form 组合：AntD 的 Form 通过 `form.validateFields()` 一行搞定表单校验
- `CaseDetail.tsx` 的 Descriptions + Timeline + Tag：AntD 的企业后台组件开箱即用
- `HumanGate.tsx` 的 Radio.Button + Timeline：用于审核操作选择非常直观

---

### Q18: 你们项目的状态为什么用 Enum，但前端又定义了 statusMap，这不是重复吗？

**项目做法：**  
后端用 Python Enum 定义状态，前端用 `statusMap` 映射展示文案：

```python
# 后端
class CaseStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
```

```typescript
// 前端
const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待处理' },
  approved: { color: 'green', text: '已通过' },
}
```

**这不是重复，而是关注点分离：**
- 后端 Enum 负责**状态机的行为语义**（哪些转换合法、业务逻辑判断）
- 前端的 statusMap 负责**UI 展示语义**（颜色、中文标签）

后端不关心前端用什么颜色展示"待处理"，前端也不关心后端状态枚举的业务含义。如果后端要改，前端不改也能工作（只是显示 enum.value），反之亦然。

---

## 常见面试追问速查

| 追问方向 | 回答要点 |
|----------|----------|
| "你们遇到过最大的技术挑战是什么？" | 状态一致性问题（Agent 部分失败时回滚）、Payload 膨胀（6个Agent的数据层层叠加） |
| "如果让你重做这个项目，哪里会不一样？" | 事件总线一开始就用 Redis（避免后续重构）、Agent 间通信改用 DB 记录而非内存传参 |
| "你们和传统理赔系统比优势在哪？" | 全链路可追溯（每个Agent中间结果可视化）、强制人工授权（合规兜底）、6-Agent 分工可独立演进 |
| "这个系统能处理百万级案件吗？" | 当前 SQLite/单机不行。PostgreSQL + 分库分表 + Agent 异步化 + 并行编排 可以 |
| "上线后 AI 判错了怎么办？" | 人工授权 Gate 兜底 + Agent 中间结果可追溯 + AuditLog 全量审计 |
