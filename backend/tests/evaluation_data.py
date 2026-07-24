"""意图识别测试数据集 — 标注样本

每条样本 = (text, intent)
intent: claim | progress | upload | consult | complaint
"""
import random

# ── 种子测试集（人工标注，60条） ──────────────────────────────
SEED_DATA: list[tuple[str, str]] = [
    # ── 报案/报销 (claim) ──
    ("我要报销医疗费", "claim"),
    ("住院花了2万块，怎么理赔", "claim"),
    ("申请理赔", "claim"),
    ("我要报案", "claim"),
    ("医疗费报销", "claim"),
    ("我老婆住院了，要报销", "claim"),
    ("看病花了好多钱，能赔多少", "claim"),
    ("发票已经开好了，申请赔付", "claim"),
    ("做手术花了5万，要报销", "claim"),
    ("住院费用报销", "claim"),
    ("我要申请赔偿", "claim"),
    ("医疗赔付申请", "claim"),
    ("报销医药费", "claim"),
    ("理赔申请", "claim"),
    ("住院花了12500，要报销", "claim"),

    # ── 查进度 (progress) ──
    ("我的理赔到哪了", "progress"),
    ("查一下进度", "progress"),
    ("审核结果出来了吗", "progress"),
    ("案件怎么样了", "progress"),
    ("理赔款什么时候到账", "progress"),
    ("查查我的案件状态", "progress"),
    ("都一个星期了还没好", "progress"),
    ("还要等多久", "progress"),
    ("我的报销进度", "progress"),
    ("理赔审核到哪一步了", "progress"),
    ("什么时候能下来", "progress"),
    ("帮我查一下案件进度", "progress"),
    ("结果出来没有", "progress"),
    ("报销到哪了", "progress"),
    ("理赔款还没到", "progress"),

    # ── 上传材料 (upload) ──
    ("我要补充材料", "upload"),
    ("上传发票照片", "upload"),
    ("补交诊断证明", "upload"),
    ("身份证照片怎么上传", "upload"),
    ("再传一份住院病历", "upload"),
    ("补充影像资料", "upload"),
    ("拍照上传发票", "upload"),
    ("材料补交", "upload"),
    ("上传图片", "upload"),
    ("补传住院记录", "upload"),
    ("扫描件怎么传", "upload"),
    ("补充医疗单据", "upload"),
    ("上传住院照片", "upload"),
    ("材料补充", "upload"),
    ("再补几张发票", "upload"),

    # ── 咨询 (consult) ──
    ("这个病能报销吗", "consult"),
    ("感冒发烧算不算医保范围", "consult"),
    ("拔牙能报销吗", "consult"),
    ("进口药属于报销范围吗", "consult"),
    ("请问门诊可以报销吗", "consult"),
    ("体检费用包含吗", "consult"),
    ("我想问一下报销比例", "consult"),
    ("这个条款什么意思", "consult"),
    ("牙科治疗能不能报", "consult"),
    ("等待期多久", "consult"),
    ("哪些医院可以报销", "consult"),
    ("报销上限是多少", "consult"),
    ("这个属于保险责任吗", "consult"),
    ("咨询一下理赔流程", "consult"),
    ("报销需要什么材料", "consult"),

    # ── 投诉 (complaint) ──
    ("我要投诉", "complaint"),
    ("你们理赔太慢了", "complaint"),
    ("客服态度很差", "complaint"),
    ("投诉电话多少", "complaint"),
    ("非常不满意你们服务", "complaint"),
    ("都一个月了还没处理", "complaint"),
    ("我要举报", "complaint"),
    ("差评", "complaint"),
    ("投诉理赔员", "complaint"),
    ("服务太差了", "complaint"),
]

# ── 边角案例 ──
EDGE_CASES: list[tuple[str, str, str]] = [
    ("hello", "claim", "无意义输入，默认归为报案"),
    ("", "claim", "空输入，默认归为报案"),
    (" ", "claim", "空白输入，默认归为报案"),
    ("查", "progress", "单字查归为查进度"),
    ("你好请问在吗", "claim", "泛问候，无明确意图"),
    ("报销报销报销报销", "claim", "关键词重复"),
]


def build_dataset(include_edge_cases: bool = True, shuffle: bool = True) -> list[tuple[str, str]]:
    """构建完整数据集"""
    data = list(SEED_DATA)
    if include_edge_cases:
        data.extend([(text, intent) for text, intent, _ in EDGE_CASES])
    if shuffle:
        random.seed(42)
        random.shuffle(data)
    return data


def get_intent_distribution(data: list[tuple[str, str]]) -> dict[str, int]:
    """统计意图分布"""
    dist = {}
    for _, intent in data:
        dist[intent] = dist.get(intent, 0) + 1
    return dist
