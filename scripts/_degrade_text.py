#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_degrade_text.py — narrative.py 的降级叙述文案引擎（纯标准库，不调 API）

设计要点
--------
不做「一句话模板 + 填空」，而是先给每条命中的规则做一次**事实抽取**（Facts），
再由 Facts 驱动三组互相独立的构造器：
  · _build_title      —— 业务化标题（机制短语 / 客群短语 / 环节短语 + 量级尾巴）
  · _build_mechanism  —— 机制段（source×stage 决定话语体系，essence 决定内容）
  · _build_decision   —— 决策（按 stage 路由到 8 个动作族，六字段 + 经营代价/风险收益）
  · _build_caveats    —— 反证（引用真实数据盲区：折算来源 / 接管线索 / 承接线 / 缺什么）
所有业务名词都来自三个来源：规则 essence、命中成员名、8 维度回调的档位名。
本模块不含任何表名/字段名常量——derived 规则里的技术标识在抽取时即被剥离。
"""
from __future__ import annotations

import re

# ============================================================ 业务词典

# 环节 → (客户经理听得懂的业务名词, 所属条线/动作主体)
STAGE_WORD = {
    "营销获客": ("获客", "营销获客"),
    "贷前准入": ("准入", "准入审批"),
    "贷前": ("贷前", "贷前调查"),
    "贷中审查": ("审查", "审查审批"),
    "审批": ("审批", "审查审批"),
    "贷后管理": ("贷后", "贷后管理"),
    "贷后": ("贷后", "贷后管理"),
    "到期续贷": ("续贷", "续贷管理"),
    "催收": ("催收", "清收处置"),
    "账龄结构": ("账龄", "风险分析"),
    "产品结构": ("产品", "产品管理"),
}
FRONT = ("营销获客", "贷前准入", "贷前", "贷中审查", "审批")
BACK = ("贷后管理", "贷后", "到期续贷", "催收")

# 特征名 → (业务名词, 资产口径, 动作族, 数据盲区)
# act 族：access 准入闸门 / limit 额度敞口 / diligence 尽调建档 / monitoring 贷后监控 /
#         collection 催收处置 / renewal 续贷接续 / conduct 人员行为 / structural 结构处置
FEATURE_DICT = {
    "零散获客": ("零散获客", "户数", "access", "缺少客户来源与营销渠道的逐户登记，无法区分主动申请与扫街拉客"),
    "批量建档": ("批量建档", "户数", "diligence", "缺少建档时的原始影像与入户记录，无法判断材料是实地采集还是批量录入"),
    "无抵押缓释": ("纯信用（无抵押、无第二还款来源）", "余额", "limit", "未接入押品与第二还款来源的完整登记，无法核实信用敞口是否被其他担保覆盖"),
    "低评分准入": ("评分逼近准入线", "户数", "access", "缺少评分卡各指标的原值与通过线距离，只能看到分段占比"),
    "评分贴线": ("评分逼近准入线", "户数", "access", "缺少评分卡各指标的原值与通过线距离，只能看到分段占比"),
    "欺诈风险敞口": ("反欺诈线索未落地核查", "户数", "access", "缺少申请环节的设备和位置指纹，无法还原同一批申请是否由同一渠道代办"),
    "审查质量": ("审查只走形式", "户数", "access", "缺少审查意见与后续不良的逐笔对应，无法判断审查是否真的看过材料"),
    "审查流于形式": ("审查只走形式", "户数", "access", "缺少审查意见与后续不良的逐笔对应，无法判断审查是否真的看过材料"),
    "贷后管理不到位": ("贷后检查未按期办结", "户数", "monitoring", "缺少上门走访与影像留证记录，无法验证检查是否真的到过现场"),
    "贷后检查流于形式": ("贷后检查只填表不到场", "户数", "monitoring", "缺少上门走访与影像留证记录，无法验证检查是否真的到过现场"),
    "接续不到位": ("续贷接续不良", "余额", "renewal", "缺少每笔接续前后的经营流水比对，无法区分真实续做与借新还旧"),
    "还款行为恶化": ("还款行为恶化（逾期天数拉长）", "余额", "renewal", "只有逾期天数，看不到客户其他机构的还款记录，恶化起点无法定位"),
    "与客户资金往来": ("客户经理与借款人存在资金往来", "户数", "conduct", "缺少客户经理与借款人账户的真实流水，资金往来只能靠关联线索间接认定"),
    "高风险客户经理": ("管户集中在中高风险客户", "户数", "conduct", "缺少客户经理的能力评估与轮岗记录，只能从所管客户的不良分布反推"),
    "高风险经理": ("管户集中在中高风险客户", "户数", "conduct", "缺少客户经理的能力评估与轮岗记录，只能从所管客户的不良分布反推"),
    "客户经理异常": ("客户经理行为异常", "户数", "conduct", "缺少客户经理与借款人账户的真实流水，行为异常只能靠关联线索间接认定"),
    "行业性风险": ("所属行业整体下行", "余额", "structural", "缺少行业景气与订单数据，行业下行只能从不良率反推"),
    "行业集中": ("产品与行业双重集中", "余额", "structural", "缺少行业敞口的分布与上限设定，集中度只能用不良占比近似"),
    "过度杠杆": ("负债水平超出经营承受力", "余额", "limit", "未接入外部负债全景，客户总负债只能由本行额度推算"),
    "多头借贷": ("同时在多家机构借款", "户数", "limit", "征信查询记录只覆盖接入机构，未接入的小贷与民间借贷看不到"),
    "超额授信": ("授信额度超过经营所需", "余额", "limit", "缺少授信额度与实际资金用途的逐笔匹配，超额部分无法直接计量"),
    "频繁试探": ("短期内反复提交申请试探额度", "户数", "access", "缺少申请被拒后的再申请轨迹，试探行为只能从查询频次近似"),
    "还款能力弱": ("第一还款来源不足", "余额", "limit", "缺少经营现金流的实测数据，还款能力只能从授信与负债比推算"),
    "第一还款来源不足": ("第一还款来源不足", "余额", "limit", "缺少经营现金流的实测数据，还款能力只能从授信与负债比推算"),
    "地址异常": ("地址与经营地对不上", "户数", "diligence", "缺少地址标准化与地理定位核对，异常只能靠字符串比对发现"),
    "尽调失真": ("入户调查材料失真", "户数", "diligence", "缺少入户调查的影像与GPS留痕，材料真实性无法逐户复核"),
    "扶贫客群": ("脱贫人口小额信贷集中承接", "户数", "diligence", "缺少脱贫人口的动态认定数据，客群认定只能按放款时点状态"),
    "老资产": ("早年发放的存量资产", "余额", "structural", "缺少存量资产的逐笔清收进度，老化程度只能用账龄档近似"),
    "征信查询密集": ("短期内征信查询密集", "户数", "access", "征信查询记录只覆盖接入机构，查询背后的真实借款去向看不到"),
    "已生不良仍准入": ("已有不良记录仍被放款", "户数", "access", "跨机构不良记录存在时滞，准入时点的真实信用状态可能被低估"),
}
FEATURE_GENERIC = {"access": ("准入条件偏松", "户数"), "limit": ("额度与敞口偏大", "余额"),
                   "diligence": ("尽调建档不实", "户数"), "monitoring": ("贷后监控缺位", "户数"),
                   "collection": ("催收处置不力", "户数"), "renewal": ("接续安排不当", "余额"),
                   "conduct": ("人员行为失范", "户数"), "structural": ("结构类风险", "余额")}

# 机制短语池（按 source × 主导环节）。标题、机制段首句、决策开篇都从这里取，
# 不同规则落到的池子不同 —— 这是 4 条标题不会同句式的主因。
MECH_PHRASES = {
    ("manual", "front"): [
        "把规模指标压到网点、准入动作整体松了一档",
        "获客节奏快过风控节奏，批量放行了没核实清楚的客户",
        "考核看放款不看质量，客户经理用降低条件换放款数",
    ],
    ("manual", "back"): [
        "贷后动作按台账走、按形式办，信号亮了没人处置",
        "客户已经出现还款困难，处置动作仍然停在流程层面",
        "风险暴露以后的补救动作迟了一整轮",
    ],
    ("manual", "cross"): [
        "前面放得松、后面没人接，风险在两段之间越滚越大",
        "审批放行的客户在贷后没有对应的跟踪，缺口就此形成",
        "准入与贷后各管一段，中间那段没人接手",
    ],
    ("manual", "cross_back"): [
        "风险在准入时埋下、却在贷后处置环节集中兑现，两端不在同一张表上",
        "前端放行时按材料齐全审、后端处置时按当期表现管，两套标准对不上",
        "准入和贷后各用各的判断依据，中间没有一次交叉复核",
    ],
    ("mined", "front"): [
        "几个单看都过得去的特征叠在一起，风险被乘法放大",
        "数据里挖出来的弱信号组合，单独不起眼、组合起来失控",
        "按单一维度挑客户挑不出来的问题，在这个交叉客群里集中暴露",
    ],
    ("mined", "back"): [
        "逾期、接续、催收行为的组合把风险不断往后挪",
        "数据挖出来的强叠加组合，暴露在贷后处置环节集中兑现",
        "几个贷后行为指标同时恶化时，单笔处置已经来不及",
    ],
    ("mined", "cross"): [
        "放款时的客群结构和处置时的动作一起出了问题",
        "数据挖出的强叠加组合，横跨准入与处置两端",
        "起点在准入、爆点在处置，中间是一条没人复核的通道",
    ],
    ("derived", "front"): [
        "数据口径本身盖住了风险——符合纸面条件不等于低风险",
        "流程留痕齐全掩盖了真实的执行松动",
        "现有报表口径把这条风险切成两半、两边都不超标",
    ],
    ("derived", "back"): [
        "处置动作被系统记录为已完成，但风险没有真正化解",
        "数据里的已完成不等于结果已化解",
        "流程口径显示正常，实际风险被推迟而不是消除",
    ],
    ("derived", "cross"): [
        "数据口径把人分成段、把风险分成环，中间那一环没人看",
        "每个环节的数据都正常，串起来才看得出问题",
        "现有口径把两段各截一半，拼起来才看得到缺口",
    ],
}

# 客群短语模板：{m} 主导成员
COHORT_PHRASES = {
    "manual": ["{m}这类客户在审批时被整体放行", "{m}客群获得了与资质不匹配的准入", "{m}客户被成批放进了授信名单"],
    "manual_back": ["{m}的这类客户，不良在贷后环节兑现", "{m}客群的风险在贷后暴露时已错过处置窗口",
                    "{m}客户在贷后阶段集中劣化"],
    "mined": ["{m}与{more}同时出现的客群", "{m}叠加{more}的交叉客群",
              "{m}与{more}两项同时命中的客户"],
    "derived": ["{m}、却仍符合纸面条件的客户", "表上看合规、实际{m}的客群", "{m}但流程上全部合规的客户"],
}

# 量级尾巴（标题尾句，按 source 用不同口径，避免 4 条都是「X 倍」）
TAILS = {
    "manual": ["不良率高出全辖 {lift:.1f} 倍（{hit} 对 {non}）", "不良率 {hit}，是全辖平均的 {lift:.1f} 倍",
               "不良率打到 {hit}，高出全辖平均 {lift:.1f} 倍"],
    "mined": ["两项以上同时命中时不良率跳到 {hit}，单看每项都只是略高于平均", "叠加客群不良率 {hit}，是单项均值的 {lift:.1f} 倍",
              "交叉客群不良率 {hit}，单项信号解释不了这个高度"],
    "derived": ["这批客户不良率 {hit}，高出全辖 {lift:.1f} 倍、却全部通过了流程审查",
                "不良率 {hit}、是均值的 {lift:.1f} 倍，系统里却查不到违规记录",
                "不良率 {hit}，越靠近准入红线越差，高出 {lift:.1f} 倍"],
}

# 动作族：按主导环节 + 特征动作族派生的管理动作。变量：{amt} {cnt} {hit} {non}
ACTIONS = {
    ("front", "access"): dict(
        verb="把准入闸门改成「批量预授信 + 用信前逐户核额」：预授信额度先放出去保住营销触点，"
             "但用信前必须补一次入户核实并双人签批，{m}的客户一律回到人工复核通道",
        cost="预授信照发，获客动作不变、营销触点不丢；多出来的是用信前的核额工时，每户按半天计",
        benefit="把「批量放进来」改成「批量先挂账、逐户再核」，新增不良可压到全辖平均附近"),
    ("front", "limit"): dict(
        verb="对{m}类客户改为「限额 + 分层」：存量按经营流水分三档，一档维持额度、二档只续不增、三档只收不贷；"
             "新增一律先按担保方式补足缓释或降到额度下限",
        cost="二、三档客户的本期放款会减少，但一档优质客户额度不动，保住主体客群",
        benefit="把敞口收缩集中到真正高风险的那部分，避免一刀切把优质客户一起挤走"),
    ("front", "diligence"): dict(
        verb="对{m}的合同逐笔回溯建档：调阅调查影像与入户记录，本月起新受理件改为「现场定位 + 双人见证 + 影像入档」，"
             "建档要素不全的不进入审查环节",
        cost="新增受理单的处理时长会拉长，需要给网点补充临时人力",
        benefit="消除纸面建档带来的准入失真，让审查看到的是真实的客户"),
    ("back", "monitoring"): dict(
        verb="把{m}的客户全部提到「周巡」名单：本周起每户指定一名贷后责任人，两周一次电访、一月一次上门，"
             "检查任务逾期未办结的直接冻结该客户新增授信",
        cost="客户经理管户数上限会被打下来，短期人均产出下降，需要调整片区划分",
        benefit="让贷后检查从填表变成能看到人的动作，把风险发现的时点前移一个季度"),
    ("back", "collection"): dict(
        verb="对{m}客户按逾期天数重排处置顺序：30 天内电话+短信双触达、60 天内上门+签还款计划、90 天进入司法或转让准备，"
             "每档设专人盯办",
        cost="清收人力向高风险客户集中，会挤占正常客户的维护时间",
        benefit="把有限的清收资源放在回收概率最高的窗口，回收率抬升"),
    ("back", "renewal"): dict(
        verb="把{m}的续贷改成「先评后续」：续贷前必须看一次近期经营流水和还款来源，"
             "接续材料与上一轮明显重复的暂停接续、转入重组谈判",
        cost="部分老客户会因续贷收紧而流失，需要提前做客户沟通与分级告知",
        benefit="止住借新还旧把风险往后推，让真实不良按期暴露而不是越滚越大"),
    ("back", "conduct"): dict(
        verb="对{m}涉及的客户经理启动「双人复核 + 家访影像留证」专项排查：排查期间不冻结其放款权限，"
             "只对排查中确认存在往来的客户加设第二还款来源",
        cost="排查占用人均两周工时，业务节奏会短暂受影响；不冻结权限是为了避免整条支线停摆",
        benefit="切断利益联结，同时避免因个别人员问题误伤整个网点"),
    ("back", "structural"): dict(
        verb="对{m}按存量/新增两条线分别处置：存量按账龄分年压降、每年设定清收下限；新增暂停同结构产品投放并重新设定额度上限",
        cost="同结构产品的投放会阶段性收缩，要提前与业务条线沟通替代产品",
        benefit="把存量风险按期出清、同时堵住同结构风险的再生产"),
    ("back", "access"): dict(
        verb="回溯{m}的准入档案：抽查审批意见与调查材料的一致性，本月起该客群的新增申请全部转上级行二次审查",
        cost="二次审查会拉长审批链条，需要同步下放部分低风险业务的审批权限以对冲效率损失",
        benefit="先把已经放出去的口子堵住，再谈投放"),
    ("back", "limit"): dict(
        verb="对{m}客户的已有额度做一次重估：按当前经营规模重新核定，超出部分只降不增；"
             "新增一律以实际用途为限、按笔核额",
        cost="降额会带来客户投诉和部分存款流失，需要配合分期压降而不是一次性砍",
        benefit="把授信规模拉回与经营能力匹配的水平"),
    ("back", "diligence"): dict(
        verb="对{m}客户开展建档质量复核：材料缺失的补齐、信息相互矛盾的实地重新采集，复核不通过的转入关注类管理",
        cost="复核工作量集中在前两个月，建议抽调内勤人员集中办理",
        benefit="让后续所有风控动作建立在真实材料上"),
    ("back", "renewal2"): dict(
        verb="对{m}客户的接续需求改为「一客一议」：能证明经营真实的继续接续但降低接续额度，不能证明的停止接续并启动清收",
        cost="部分确有困难的客户会被迫提前暴露，需要配套分期与展期安排",
        benefit="把接续从「自动通过」变回「逐笔判断」"),
    ("front", "monitoring"): dict(
        verb="把贷后检查的触发条件前移到放款环节：{m}类客户放款时即生成首期检查任务，逾期未办结的冻结该客户后续用信",
        cost="放款环节多一道系统校验，审批时效会多半天",
        benefit="让检查任务从放款就开始计时，堵住「放完就不管」"),
    ("front", "structural"): dict(
        verb="对{m}类客户单独设行业与额度上限：行业敞口按月统计、超过上限的只降不增；新增以订单和经营流水为依据核定额度",
        cost="超限行业的新增会暂停，短期放款量下降，可由其他优质行业补位",
        benefit="避免行业敞口继续扩大，把有限额度投向真实经营需求"),
    ("front", "collection"): dict(
        verb="对{m}的新增客户强制设置预警标签：放款后 30 天未按计划用款、或首次还款延后的，立即转贷后处置",
        cost="预警标签会带来额外的客户回访，占用部分客户经理时间",
        benefit="把刚出问题的客户拦在早期，避免拖成不良"),
    ("front", "renewal"): dict(
        verb="对{m}的客户在放款时同步做一次续贷可行性判断：经营数据不达标的直接缩短授信期限，避免到期只能靠接续",
        cost="部分客户授信期限被缩短，续贷压力前移，需要提前告知",
        benefit="减少未来到期时只能靠接续工具硬撑的客户数量"),
}
ACTION_CROSS_TAIL = dict(
    cost="两端联动会带来重复核查的工时，建议由风险条线统一发一次核查清单、两边共用",
    benefit="前端堵住新增、后端处置存量，避免只改一头、另一头继续漏",
)

CAVEAT_REJECTED_NOISE = "「{c}」这条线索被核查标记为不属实的比例达 {p}，这条主线的结论受其拖累，需要剔除该线索后复算"

BLIND_SPOT_BY_SIGNAL = [
    (re.compile(r"clue_matrix"), "线索级不良率由各机构均值折算，不是逐笔线索实测；单条线索的倍数只能看方向，不能当精确值"),
    (re.compile(r"continuation\.(tools|chain)|continuation 缺失"), "尚无按接续工具逐类拆分的余额与不良明细，接续类结论只能用均值口径，工具之间的优劣比较不可靠"),
    (re.compile(r"c4|CONT_QUAL", re.I), "接续客户的存量质量明细缺失，接续链到底滚了多少轮、滚了多久算不出来"),
    (re.compile(r"features\[\d+\]"), "部分衍生指标不可用，相关规则只能按剩余成员的部分命中计算，可能低估强度"),
    (re.compile(r"cohort|折算"), "客群校验的 lift 由多维度几何平均折算，属于下界估计；真实交集客群的差距通常更大，方向可信、幅度待实测"),
    (re.compile(r"继承"), "部分矩阵继承自上一期结果、本期未重算，跨期口径未做校正"),
]

# ============================================================ 事实抽取

TECH_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]{2,}\b")     # 字段/表名形态
NUM_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def _clean_essence(s):
    """剥离 essence 里的技术标识与裸数值，只留业务语义"""
    s = TECH_TOKEN.sub("", s or "")
    # 去掉「不良率 13.35%」「增量 1.10」这类纯数据尾巴，但这些数字本身是有用的量级
    s = re.sub(r"[（(]\s*[A-Z_0-9=, ]*\s*[)）]", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ，,、；;——-")
    return s


def _feature_of(name):
    """特征名 → 词典条目（模糊包含匹配，保证未登记的特征也有业务化说法）"""
    if not name:
        return None
    n = str(name).strip()
    if n in FEATURE_DICT:
        return FEATURE_DICT[n]
    for k, v in sorted(FEATURE_DICT.items(), key=lambda x: -len(x[0])):
        if k and (k in n or n in k):
            return v
    return None


def stage_bucket(stages):
    """阶段 → front / back / cross / other"""
    st = set(stages or [])
    f = bool(st & set(FRONT))
    b = bool(st & set(BACK))
    if f and b:
        return "cross"
    if f:
        return "front"
    if b:
        return "back"
    return "front"


# essence 里出现、但成员名里没有的「区分性修饰语」→ 业务名词
ESSENCE_MODS = [
    ("小额", "小额、高频、额度极小"),
    ("存量", "早年发放、尚未出清的存量"),
    ("老资产", "早年发放、尚未出清的存量"),
    ("2023 年及以前", "2023 年以前形成的老资产"),
    ("贫困", "脱贫人口小额信贷"),
    ("脱贫", "脱贫人口小额信贷"),
    ("扶贫", "脱贫人口小额信贷"),
    ("金额", "单笔金额大"),
    ("大额", "单笔金额大"),
    ("贴线", "评分刚过准入线"),
    ("略高于", "评分刚过准入线"),
    ("反复", "反复接续"),
    ("滚动", "反复接续"),
    ("5 万元以下", "5 万元以下的小额"),
    ("5万以下", "5 万元以下的小额"),
    ("纯信用", "纯信用"),
    ("无抵押", "纯信用"),
    ("多头", "同时在多家机构借款"),
    ("负债", "自身负债偏高"),
    ("经营恶化", "主业收入下滑"),
    ("下行", "所处行业整体下行"),
    ("地址", "注册地址与经营地对不上"),
    ("征信", "征信查询密集"),
]


def _essence_mods(essence, member_words):
    """从 essence 找出成员名里没覆盖的修饰语，用于区分「同名但不同机制」的规则"""
    out = []
    for kw, word in ESSENCE_MODS:
        if kw in essence and not any(word in w or kw in w for w in member_words):
            if word not in out:
                out.append(word)
    return out


class Facts:
    """一条主题的全部可用素材（全部来自 attribution / evidence / signals）"""

    def __init__(self, plan, ins, prev_ins, signals, td=None):
        self.plan = plan
        self.ins = ins or {}
        self.prev = prev_ins or {}
        self.signals = signals or {}
        self.td = td

        self.rule_id = self.ins.get("rule_id") or plan.get("linked_rule") or "?"
        self.name = self.ins.get("name") or plan.get("topic_hint") or ""
        self.source = (self.ins.get("source") or "manual").lower()
        if self.source not in ("manual", "mined", "derived"):
            self.source = "manual"
        self.strength = self.ins.get("strength")
        self.cross = bool(self.ins.get("cross_stage"))
        self.stages = [s for s in (self.ins.get("stages") or []) if s]
        self.bucket = "cross" if self.cross else stage_bucket(self.stages)
        # 主导环节（用于动作路由）：优先取真正承载风险的那一环
        self.stage = self._lead_stage()

        self.cohort = dict(self.ins.get("cohort") or {})
        if not self.cohort:
            if self.ins.get("cohort_lift") is not None:
                self.cohort = {"source": "cohort_json", "lift": self.ins.get("cohort_lift"),
                               "size": self.ins.get("cohort_size"), "npl_rate": self.ins.get("cohort_npl_rate")}
            else:
                sel = self.prev.get("topic_selection") or []
                hit = next((t for t in sel if t.get("rule_id") == self.rule_id), None)
                if hit and hit.get("cohort_lift") is not None:
                    self.cohort = {"source": hit.get("cohort_source") or "cohort_json",
                                   "lift": hit.get("cohort_lift"), "size": hit.get("cohort_size")}
        self.cohort_src = self.cohort.get("source") or ""
        self.cohort_lift = self.cohort.get("lift")

        self.members = [m for m in (self.ins.get("members") or []) if (m.get("name") or m.get("feature_id"))]
        self.feats = []
        for m in self.members:
            nm = m.get("name") or ""
            ent = _feature_of(nm) or FEATURE_GENERIC["structural"] + ("structural", "")
            self.feats.append({"name": nm or ent[0], "word": ent[0], "amount": ent[1],
                               "act": ent[2], "blind": ent[3] if len(ent) > 3 else ""})
        # 主成员优先取金额口径为「余额」的（更能代表敞口），其次取第一个
        if self.feats:
            top = next((f for f in self.feats if f["amount"] == "余额"), self.feats[0])
            self.lead = top
        else:
            self.lead = {"name": "(整体)", "word": "这类客户", "amount": "户数", "act": "access", "blind": ""}
        self.acts = {f["act"] for f in self.feats} or {"access"}

        self.essence = _clean_essence(self.ins.get("essence") or "")
        self.mods = _essence_mods(self.essence, [x["word"] for x in self.feats])
        # 客群名 = 主导成员 + essence 修饰语：这是「同一特征、不同机制」不会写出同一句话的关键
        self.cohort_word = self.lead["word"]
        if self.mods:
            self.cohort_word = f"{self.mods[0]}的{self.cohort_word}"
        if self.cohort_word.endswith("客户"):
            self.cohort_word = self.cohort_word[:-2]
        # 去「反复接续的续贷接续不良」这类同义重复：修饰语与成员名共享同一动名词干时只留成员名
        if self.mods and len(self.cohort_word) > 8:
            stem = set(self.mods[0]) & set(self.lead["word"])
            if stem and len(stem) >= 2:
                self.cohort_word = self.lead["word"]
        self.derivation_note = ""

        c = (plan.get("comparisons") or [{}])[0]
        self.hit = c.get("hit") or {}
        self.nonhit = c.get("nonhit") or {}
        self.lift = c.get("lift")
        self.hit_rate = self.hit.get("npl_rate")
        self.non_rate = self.nonhit.get("npl_rate")
        self.overall = (self.signals.get("overall") or {})
        self.base_rate = self.overall.get("npl_rate")
        self.n_hit = self.hit.get("n")
        self.n_non = self.nonhit.get("n")

        # 8 维度回调：找到与成员同名/近名的档位，拿到真实档位名与偏移
        # 注意：上游 overview 的档位键是 bucket，部分口径写作 dim_value，两种都认
        self.dims = []
        for key, dim in (self.signals.get("dimensions") or {}).items():
            dname = dim.get("name") or key
            for b in dim.get("buckets") or []:
                bk = str(b.get("bucket") or b.get("dim_value") or "")
                if not bk:
                    continue
                for f in self.feats:
                    toks = [t for t in re.split(r"[（(、/]", f["word"]) if len(t) >= 2]
                    if f["word"] and (f["word"] in bk or bk in f["word"] or any(t in bk for t in toks)):
                        self.dims.append({"dim": dname, "bucket": bk, "rate": b.get("npl_rate"),
                                          "offset": b.get("offset_pp"), "share": b.get("npl_share"),
                                          "bal": b.get("bal"), "feature": f["word"]})
                        break
        seen, dims2 = set(), []
        for d in self.dims:
            if (d["dim"], d["bucket"]) not in seen:
                seen.add((d["dim"], d["bucket"]))
                dims2.append(d)
        self.dims = dims2

    # ---------- 派生量 ----------
    def _lead_stage(self):
        if not self.stages:
            return "贷前"
        # 贷后/续贷/催收 优先（这些环节的动作最具体），其次贷中审查，最后货前
        for pref in ("催收", "到期续贷", "贷后管理", "贷后", "贷中审查", "审批", "贷前准入", "贷前", "营销获客"):
            if pref in self.stages:
                return pref
        return self.stages[0]

    @property
    def stage_word(self):
        return STAGE_WORD.get(self.stage, (self.stage, self.stage))

    @property
    def more_words(self):
        return [f["word"] for f in self.feats if f["word"] != self.lead["word"]][:2]

    @property
    def amount(self):
        return self.lead["amount"]

    def severity(self):
        """把「倍数」压成业务话术的分档用词"""
        L = self.lift or 0
        if L >= 4:
            return "extreme"
        if L >= 2.5:
            return "high"
        if L >= 1.5:
            return "mid"
        return "low"


# ============================================================ 标题

def _lift_tail(f, idx):
    """量级尾巴：source 决定口径，idx 保证同 source 的多条标题也不撞句式"""
    hit = f"{f.hit_rate:.2%}" if f.hit_rate is not None else "—"
    non = f"{f.non_rate:.2%}" if f.non_rate is not None else "—"
    L = f.lift or 0
    pool = TAILS[f.source]
    t = pool[idx % len(pool)]
    return t.format(hit=hit, non=non, lift=L)


def build_title(f, idx):
    """业务化标题 = 机制短语 + 客群短语 + 环节短语 + 量级尾巴（不用规则名）"""
    mb = (f.source, f.bucket)
    if f.source == "manual" and f.bucket == "cross" and f.lead["act"] in ("renewal", "monitoring", "collection", "conduct"):
        mb = ("manual", "cross_back")
    mech = MECH_PHRASES.get(mb, MECH_PHRASES[(f.source, f.bucket)])[idx % 3]
    head = mech[0].upper() + mech[1:] if not mech.startswith("数据") else mech
    # 话语池：manual 再按「风险真正发生在哪一端」细分，避免贷后议题借用准入的措辞
    pool_key = f.source
    if f.source == "manual" and (f.bucket == "back" or f.lead["act"] in ("renewal", "monitoring", "collection", "conduct")):
        pool_key = "manual_back"
    cp = COHORT_PHRASES[pool_key][idx % 3].format(m=f.cohort_word,
                                                  more="与".join(f.more_words) or "同类弱信号")
    if f.bucket == "cross":
        _fr = '/'.join(STAGE_WORD.get(s, (s,))[0] for s in f.stages if s in FRONT) or "贷前"
        _bk = '/'.join(STAGE_WORD.get(s, (s,))[0] for s in f.stages if s in BACK) or "贷后"
        seg = f"「{_fr}放进来、{_bk}没接住」"
    elif f.bucket == "back":
        seg = f"「{f.stage_word[0]}环节失守」"
    else:
        seg = f"「{f.stage_word[0]}关口失守」"
    tail = _lift_tail(f, idx)
    # 3 种排列，配合 source 池错位，保证同批 4 条标题结构不同
    forms = [
        f"{head}｜{cp}：{tail}",
        f"{seg}{cp}——{head}，{tail}",
        f"{cp}：{head}，{tail}",
    ]
    title = forms[idx % 3]
    # 若标题意外命中规则名，换一种排列
    if f.name and f.name in title:
        title = forms[(idx + 1) % 3]
    if f.name and f.name in title:
        title = f"{seg}{cp}：{tail}"
    return title


# ============================================================ 机制段

def _dims_sentence(f):
    if not f.dims:
        return ""
    d = max(f.dims, key=lambda x: abs(x.get("offset") or 0))
    off = d.get("offset") or 0
    return (f"在「{d['dim']}」维度上，「{d['bucket']}」这一档不良率 {d['rate']:.2%}、"
            f"偏离全辖 {off:+.2f} 个百分点，与这条线索指向的是同一批客户。")


def _members_sentence(f):
    if not f.feats:
        return ""
    ws = "、".join(f["word"] for f in f.feats[:3])
    extra = f"；从线索定义看，它特指{f.mods[0]}这一部分" if f.mods else ""
    return f"命中的具体特征是{ws}{extra}。"


def _source_sentence(f):
    if f.source == "manual":
        return (f"这是经过多轮验证的经典风险组合，机制链条清楚：{f.essence}。"
                f"因果是单向的——动作先松，客户结构随后劣化，不良最后才浮出来。")
    if f.source == "mined":
        bits = []
        if f.cohort_lift:
            bits.append(f"独立客群校验的 lift 为 {f.cohort_lift}")
        if f.ins.get("incremental_lift"):
            bits.append(f"相对单成员的增量 lift 为 {f.ins['incremental_lift']}")
        pre = "、".join(bits) or "尚未取得独立客群校验"
        return (f"这不是预设的风险假设，是从全样本里挖出来的强叠加组合——{f.essence}；{pre}。"
                f"单项信号都很弱，两项同时命中才拉开差距，属于「事先没人想到、数据先说话」的类型。")
    der = f.derivation_note or "现有报表口径"
    return (f"这条风险不是业务动作直接做错的，而是数据口径造成的盲区：{f.essence}。"
            f"{der}把每个环节都记成了「正常」，风险因此被切成两半、两边都不超标。")


def build_mechanism(f, idx):
    parts = [_source_sentence(f)]
    key = (f.source, f.bucket)
    if f.source == "manual" and f.bucket == "cross" and f.lead["act"] in ("renewal", "monitoring", "collection", "conduct"):
        key = ("manual", "cross_back")
    phrase = MECH_PHRASES.get(key, MECH_PHRASES[(f.source, f.bucket)])[idx % 3]
    if f.source == "manual":
        parts.append(f"传导路径是：{phrase}。")
    elif f.source == "mined":
        parts.append(f"它在数据形态上表现为：{phrase}。")
    else:
        parts.append(f"这次把数据重新串起来才看出：{phrase}。")
    ms = _members_sentence(f)
    if ms:
        parts.append(ms)
    ds = _dims_sentence(f)
    if ds:
        parts.append(ds)
    if f.cross:
        fronts = "、".join(STAGE_WORD.get(s, (s,))[0] for s in f.stages if s in FRONT) or "贷前"
        backs = "、".join(STAGE_WORD.get(s, (s,))[0] for s in f.stages if s in BACK) or "贷后"
        parts.append(f"这条线索横跨{fronts}与{backs}两端，单独改任何一端都会从另一端漏回来。")
    return "".join(parts)


# ============================================================ 决策

OWNER_BY_ACT = {
    "access": "风险管理部（准入管理岗）+ 支行行长",
    "limit": "授信审批部（额度管理岗）+ 客户经理",
    "diligence": "信贷管理部（调查管理岗）+ 支行行长",
    "monitoring": "信贷管理部（贷后管理岗）+ 客户经理",
    "collection": "资产保全部（清收岗）+ 支行行长",
    "renewal": "信贷管理部（续贷审批岗）+ 客户经理",
    "conduct": "纪检监察室 + 风险管理部",
    "structural": "风险管理部（组合管理岗）+ 业务条线负责人",
}
DEADLINE_BY_BUCKET = {
    "front": "专项方案 2 周内下发，1 个月内完成存量回溯，新受理件本月起执行",
    "back": "1 周内完成名单下发，2 个月内完成首轮处置，按月复盘",
    "cross": "两端同步：前端 2 周内上收审批权，后端 1 个月内完成存量复核，联席月度督办",
}
KPI_BY_ACT = {
    "access": ("{m}客群新增不良率", "用信前核额覆盖率"),
    "limit": ("{m}客群户均授信额与不良率", "分层覆盖率"),
    "diligence": ("{m}客群建档要素完整率与新增不良率", "回溯建档完成率"),
    "monitoring": ("{m}客群贷后检查按期办结率与不良迁徙率", "周巡覆盖率"),
    "collection": ("{m}客群回收率", "分档处置完成率"),
    "renewal": ("{m}客群接续后再不良率", "接续前经营流水核验覆盖率"),
    "conduct": ("{m}相关客户不良率", "排查覆盖率"),
    "structural": ("{m}客群余额占比与不良率", "存量压降完成率"),
}


def _pick_act(f):
    """动作族选择：主导环节 + 特征动作族共同决定，跨环节取「前端闸门 + 后端处置」组合"""
    act = f.lead["act"]
    if f.bucket == "cross":
        # 跨环节：后端取贷后/续贷类动作，前端取准入类动作
        lead_act = f.lead["act"]
        back_set = ("renewal", "monitoring", "collection", "structural", "conduct")
        # 主导成员的动作用族就是主体动作：风险出在贷后，主轴就放在贷后，前端只作为配套
        if lead_act in back_set:
            key_back = lead_act
            key_front = next((a for a in ("access", "limit", "diligence") if a in f.acts), "access")
            return (f"back", key_back), ("front", key_front)
        key_back = next((a for a in ("renewal", "monitoring", "collection") if a in f.acts), "monitoring")
        return (f"front", lead_act), ("back", key_back)
    return (f.bucket if f.bucket in ("front", "back") else "front", act), None


def _fmt_action(e, f):
    return e["verb"].format(m=f.cohort_word, cnt=f.n_hit or 0)


def build_decision(f, idx):
    primary, secondary = _pick_act(f)
    me = ACTIONS.get(primary) or ACTIONS[("front", "access")]
    action = _fmt_action(me, f)
    cost = me["cost"]
    gain = me["benefit"]
    if secondary:
        se = ACTIONS.get(secondary) or ACTIONS[("back", "monitoring")]
        action += ("；配套改造：" if primary[0] == "back" else "；后端同步：") + _fmt_action(se, f)
        cost += "；" + ACTION_CROSS_TAIL["cost"]
        gain += "；" + ACTION_CROSS_TAIL["benefit"]
    hit = f"{f.hit_rate:.2%}" if f.hit_rate is not None else "—"
    non = f"{f.non_rate:.2%}" if f.non_rate is not None else "—"
    baseline_extra = (f"（命中客群实测 {hit}，同期未命中客群 {non}，倍数 {f.lift:.2f}）"
                      if f.lift else "")
    act_key = primary[1]
    kpi0, kpi1 = KPI_BY_ACT.get(act_key, KPI_BY_ACT["access"])
    return {
        "action": (f"【处置动作】{action}。"
                   f"【经营代价】{cost}。"
                   f"【风险收益】{gain}。"),
        "owner": OWNER_BY_ACT.get(act_key, "风险管理部"),
        "deadline": DEADLINE_BY_BUCKET.get(f.bucket, DEADLINE_BY_BUCKET["front"]),
        "kpi": f"{kpi0.format(m=f.lead['word'])}；辅以{kpi1}",
        "baseline": f"{hit}（全辖 {f.base_rate:.2%}）" + baseline_extra if f.base_rate else hit,
        "target": (f"整改后 6 个月，该客群不良率降到全辖 {f.base_rate:.2%} 的 1.2 倍以内"
                   if f.base_rate else "整改后 6 个月，该客群不良率回落至全辖平均 1.2 倍以内"),
    }


# ============================================================ caveats

def _noise_hits(f):
    cm = f.signals.get("clue_matrix") or {}
    out = []
    for feat in f.feats:
        v = cm.get(feat["word"])
        if not v:
            # 特征名与线索名不完全一致时做包含匹配
            for k, vv in cm.items():
                if feat["word"][:2] and feat["word"][:2] in k:
                    v = vv
                    break
        if v and (v.get("verify_false_pptn") or 0) >= 0.2:
            out.append((feat["word"], v["verify_false_pptn"]))
    return out


def _cohort_gap(f):
    """规则级 lift 与客群校验 lift 的背离：客群扩张后稀释了强度，须如实写"""
    if not (f.lift and f.cohort_lift):
        return ""
    if f.cohort_lift < f.lift - 0.5 and f.cohort_lift >= 1.2:
        return (f"规则的独立客群校验只有 {f.cohort_lift:.2f} 倍（规则本身 {f.lift:.2f} 倍、客群 {f.cohort.get('size') or '—'} 户），"
                f"说明客群放宽后强度被稀释，小范围精准客群的差距远大于平均数")
    if f.cohort_lift > f.lift + 1.0:
        return (f"独立客群校验给到 {f.cohort_lift:.2f} 倍，高于本次钻取的 {f.lift:.2f} 倍，"
                f"本次只取了一部分命中客户，差距可能被低估")
    return ""


def build_caveats(f, idx):
    out = []
    cg = _cohort_gap(f)
    if cg:
        out.append(cg)
    elif f.cohort_src in ("signals_measured", "cohort_json"):
        out.append(f"客群倍数 {f.cohort_lift:.2f} 由多维度折算得到（下界估计），方向可信，精确幅度要等实际交集客群实测后才能定")
    elif f.cohort_src == "clue":
        out.append("客群倍数由线索级不良率推导，线索并非逐笔核实过的风险标记，方向可用、数值偏虚")
    else:
        out.append("本次没有独立的客群校验，机制链条只依赖钻取的命中／对照组差异，结论稳健性低于有校验的线索")

    nh = _noise_hits(f)
    for nm, p in nh[:2]:
        out.append(CAVEAT_REJECTED_NOISE.format(c=nm, p=f"{p:.1%}"))

    blind = next((x["blind"] for x in f.feats if x.get("blind")), "")
    if blind:
        out.append(blind)

    cont = (f.signals.get("continuation") or {})
    if "renewal" in f.acts:
        ch = cont.get("chain") or {}
        if ch.get("rolling"):
            rr = ch["rolling"].get("npl_rate")
            rs = (ch.get("resolving") or {}).get("npl_rate")
            out.append(f"接续链只有客户数与不良率（滚动接续 {rr:.2%}" +
                       (f"、以化解方式退出 {rs:.2%}" if rs is not None else "") +
                       "），看不到同一客户被接续了几轮，接续年限的判断只能算下限")
        elif any("continuation" in str(w) for w in (f.signals.get("warnings") or [])):
            out.append("接续工具逐类明细本期缺失，续贷类结论只能用均值口径，不同接续方式之间的优劣无法比较")

    if f.bucket == "cross" and not any("横跨" in x or "两端" in x for x in out):
        out.append("两端联动结论依据的是同一批客户在两个环节同时命中，不是逐笔跟踪过资金的流向；"
                   "两端因果先后顺序需要再用放款—检查—续贷的时间序列验证")
    # 至少 1 条、最多 3 条
    return out[:3] if out else ["本次样本结构未做区域校正，剔除头部机构后倍数可能回落，但方向不会反转"]


# ============================================================ 计算段

def build_evidence(f):
    hit = f"{f.hit_rate:.2%}" if f.hit_rate is not None else "—"
    non = f"{f.non_rate:.2%}" if f.non_rate is not None else "—"
    non_txt = f"对照组 {f.n_non} 户、不良率 {non}" if f.n_non else f"对照口径（全辖／同条件客群）不良率 {non}"
    s = (f"钻取对比：命中组 {f.n_hit} 户、不良率 {hit}；{non_txt}；"
         f"倍数 {f.lift:.2f}。") if f.lift is not None else \
        (f"钻取对比：命中组 {f.n_hit} 户、不良率 {hit}；{non_txt}；倍数未达可比口径。")
    if f.cohort_lift is not None:
        s += f"独立客群校验 lift {f.cohort_lift:.2f}（{f.cohort_src or '客群口径'}）。"
    verdict = f.plan.get("verdict")
    if verdict:
        s += f"判定：{verdict}"
    return s


def build_phenomenon(f, idx):
    hit = f"{f.hit_rate:.2%}" if f.hit_rate is not None else "—"
    non = f"{f.non_rate:.2%}" if f.non_rate is not None else "—"
    L = f.lift or 0
    bw = f.severity()
    tag = {"extreme": "差距极大", "high": "差距显著", "mid": "差距中等但方向明确", "low": "差距有限"}[bw]
    lead = {
        "manual": f"{f.cohort_word}客户的不良率",
        "mined": f"{f.cohort_word}{('叠加' + '/'.join(f.more_words)) if f.more_words else ''}这一交叉客群的不良率",
        "derived": f"{f.cohort_word}、但通过了流程审查的这批客户，不良率",
    }[f.source]
    # 对照组户数缺失时不能写成「对 None 户」——改口径说明，不编数
    if f.n_non:
        sample_txt = f"样本 {f.n_hit} 户对 {f.n_non} 户，已超出抽样波动能解释的范围。"
    elif f.n_hit:
        sample_txt = f"命中样本 {f.n_hit} 户；对照口径为全辖平均，未单列对照户数。"
    else:
        sample_txt = ""
    return (f"{lead}为 {hit}，同期条件相近的对照客户只有 {non}，"
            f"高出 {((f.hit_rate or 0) - (f.non_rate or 0)) * 100:.2f} 个百分点、{L:.1f} 倍——{tag}；"
            f"{sample_txt}")


def build_impact(f):
    total_bal = f.overall.get("bal") or 0
    per = (total_bal / (f.overall.get("cnt") or 1)) if total_bal else 0
    if f.hit_rate is not None and f.non_rate is not None and f.n_hit and per:
        boost = f.n_hit * (f.hit_rate - f.non_rate) * per
        return (f"命中组约 {f.n_hit:,} 户，按两组不良率差估算，贡献超额不良约 {boost:,.0f} 元"
                f"（以全辖户均余额近似，量级参考）；这部分是本期 {f.base_rate:.2%} 不良率里"
                f"本可在「{f.stage_word[0]}」环节拦下的部分。")
    return f"命中组 {f.n_hit} 户，规模测算受样本限制未做，仅按户数与倍数判断优先级。"
