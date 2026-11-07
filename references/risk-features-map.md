# 风险特征映射（risk-features-map）

被 `scripts/risk_features.py` 引用。将《已知风险特征范围.xls》的 45 项风险特征映射到可用数据表的命中判据。

**约定**：
- `data_missing` = 无数据文件的表，该特征**不能直接计算**，改用机构级分析表预聚合口径或标注缺失
- 阈值 N / N% 为可配置参数（脚本 `--thresholds` 传入），默认值见各判据
- 所有命中客户/合同须再关联凭证表按 A70 口径过滤（若判据表本身不含业务品种）

## 一、机构维度（13 项）

| # | 风险特征 | 数据表 | 命中判据 | 默认阈值 | 备注 |
|---|---|---|---|---|---|
| 1 | 零散获客（行政村N户及以下占比高） | S_00PF_PEAS_DIVR_RSK_C4 | DIVR_CTRT_RATE / DIVR_LN_BAL_RATE（零散客户/余额占比） | 查表直接取 | 机构级已预聚合 |
| 2 | 无抵押缓释（信用贷款占比过高） | S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4 | GRTE_TYP 维度下信用类余额占比 / 不良率 | 查表直接取 | 机构级已预聚合 |
| 3 | 低评分准入（低分段占比高） | S_00PF_PEAS_ACARD_SCRE_RSK_ORG_C4 / G_00PL_IDV_LN_CUST_ACARD_SCRE_DV | SCRE < 阈值（如 60）客户数/占比；机构级 ACARD_SCRE_ACTN_RSK_TYP 占比 | SCRE<60 | A卡评分表有数据 |
| 4 | 建档不规范（批量/失真） | S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4 | ARC_QLT_RSK_TYP 各类型合同/客户占比、不良率 | 查表直接取 | 机构级已预聚合；地址表无数据 |
| 5 | 欺诈风险敞口（拦截率不足） | S_00PF_PEAS_LN_RSK_ORG_C4 / S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4 | 风险线索类型触发占比、不属实占比 | 查表直接取 | 线索明细表无数据，用机构级 |
| 6 | 信用负债敞口（高负债/多头） | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing**，用 S_*_C4 线索口径替代 |
| 7 | 超额授信（免扣减/高估/收入不足） | S_00PF_PEAS_OVER_FL_AC_RSK_C4 | OVER_FL_AC_RSK_TYP 各类型占比、不良率 | 查表直接取 | 机构级已预聚合 |
| 8 | 审查质量（白名单通过率高） | G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO | APR_OPIN 通过率；放款后短期转不良 | 通过率>90% | 白名单流程表有数据 |
| 9 | 贷后管理不到位（任务超时） | B_00FT_PEAS_LN_DPSE_TASK_DTAL / B_00FT_PMC_P_DOORTASK_DTAL | LMT_DUE_DATE 超期未办结任务数/率；裸贷户（FAS资产=0） | 超时率>20% | 检查任务表无数据 |
| 10 | 接续不到位（换客户经理） | S_00PF_PEAS_CONT_QUAL_C4 / G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO | 接续不良率 CTNU_LN_BAD_RATE；CONTINUE_FLAG 分布 | 查表直接取 | 机构级已预聚合 |
| 11 | 高风险客户经理 | S_00PF_PEAS_MGR_LN_RISK_C4 / S_00PF_PEAS_HRZ_MGR_LN_ANL_C4 | CUR_RAT_NPL_PEAS > N% 或 CUR_BAL_NPL_PEAS > N万 | 不良率>5% 且余额>50万 | 机构级已预聚合 |
| 12 | 高风险产品/专项 | S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4 / S_00PF_PEAS_LN_SPC_ORG_ANL_C4 | BIZ_RAT_NPL_PEAS > N% 且不良余额大 | 不良率>5% | 机构级已预聚合 |
| 13 | 大额信用风险 | S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4 | 大额信用合同/余额占比、不良率 | 查表直接取 | 机构级已预聚合 |

## 二、客户经理维度（6 项）

| # | 风险特征 | 数据表 | 命中判据 | 默认阈值 | 备注 |
|---|---|---|---|---|---|
| 14 | 批量建档（同日≥N户） | S_00PF_PEAS_MGR_LN_RISK_C4（SAME_DAT_CUST_CNT） | SAME_DAT_CUST_CNT ≥ N | ≥5 | 客户经理风险表有该字段 |
| 15 | 调查造假（三地不一致） | G_00PL_PEAS_LN_ADDR_CHEK_DV（无数据） | — | — | **data_missing**，用 S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4 地址异常口径 |
| 16 | 信息录入失真（FAS虚增） | B_00DT_FAS_ANL_SITU_DOC_H / B_00DT_FAS_FMLY_SITU_DOC_H | FAS资产/收入与画像比对（如 TOT_AST 与农行金融资产偏差大） | 偏差>50% | FAS档案表有数据 |
| 17 | 与客户资金往来 | S_00PF_PEAS_MGR_LN_RISK_C4（FND_CLU_CNT_PEAS） | FND_CLU_CNT_PEAS（触发与客户资金往来模型累计线索量）≥1 | ≥1 | 客户经理风险表有该字段 |
| 18 | 贷后检查流于形式 | B_00FT_PEAS_LN_CHK_TASK_DTAL（无数据） | — | — | **data_missing**；用处置任务表 BUS_STS/结论字段近似 |
| 19 | 管户负担过重 | S_00PF_PEAS_MGR_LN_RISK_C4（CUR_CUST_PEAS_LN） | 管户户数 CUR_CUST_PEAS_LN > N | >200 | 客户经理风险表有该字段 |

## 三、客户维度（26 项）

| # | 风险特征 | 数据表 | 命中判据 | 默认阈值 | 备注 |
|---|---|---|---|---|---|
| 20 | 虚假经营流水 | S_00PF_SA_ACCT_TR_CUST_SUM + B_00DT_FAS_FMLY_SITU_DOC_H | 交易金额 vs FAS年收入偏差大（如 YEAR_TR_BAL_L1YER_ACLT >> FMLY_ANNL_INCM×N） | >3倍 | 交易汇总+家庭档案有数据 |
| 21 | 短期资金异常涌入 | S_00PF_SA_ACCT_TR_CUST_SUM | 放款前窗口流入笔数/金额异常（如当月流入/日均余额比高） | 流入/日均>5 | 需结合放款日期（凭证表） |
| 22 | 多个实体共用经营场所 | G_00PL_PEAS_LN_ADDR_CHEK_DV（无数据） | — | — | **data_missing** |
| 23 | 短期频繁试探申请 | G_00PL_IDV_LN_CUST_ACARD_SCRE_DV + G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO | 同客户近N个月申请次数/产品数 | 申请≥3次 | 评分表+白名单流程表 |
| 24 | 抵押物短持/高评高贷 | G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV | 押品持有时间短（EVAL基准早）、内外部评估差大 | 内/外评估差>30% | 抵押房产风险表有数据 |
| 25 | 买壳/新注册即贷 | B_00DT_FAS_IDV_BUS_INFO_H（CRT_DAT） | 成立日期距放款< N个月 | <6个月 | FAS个体经营表有数据 |
| 26 | AUM与存款不匹配 | S_00PF_IDV_CUST_FA_SUM + S_00PF_IDV_DP_CUST_SUM | AUM_BAL / RMB_DP_BAL 严重不匹配 | AUM<存款×20% | 两表均有数据 |
| 27 | 异地风险 | S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4 | ADDR_RSK_TYP 地址异常类型占比/不良率 | 查表直接取 | 地址明细无数据，用机构级 |
| 28 | 行业性风险 | S_00PF_PEAS_OCPRSK_ORG_C4 / G_00PF_PEAS_LN_VCH_DV（LN_IVDIR_NATECO_OCPCLS_CD） | 重点行业（KEY_OCP_COD）占比、不良率 | 查表直接取 | 机构级已预聚合 |
| 29 | 经营地址频繁变更 | B_00DT_CORP_GX_ALTER_DTAL（无数据） | — | — | **data_missing** |
| 30 | 经营年限不足 | B_00DT_FAS_IDV_BUS_INFO_H（CRT_DAT） | 成立日期距今< N年 | <1年 | FAS个体经营表 |
| 31 | 虚增面积/收入 | B_00DT_FAS_ANL_SITU_DOC_H（FARM_LAND等） | 农地/收入与配置参数偏差大 | 偏差>50% | FAS资产负债表 |
| 32 | 多头借贷 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 33 | 负债与规模不匹配 | B_00DT_FAS_ANL_SITU_DOC_H（TOT_DPS vs 收入） | 总负债/年收入 > N | >5 | FAS资产负债+家庭档案 |
| 34 | 征信查询次数过多 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 35 | 有被拒贷记录 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 36 | N年内不良记录 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 37 | 赌博嗜好（夜间交易） | S_00PF_SA_ACCT_TR_CUST_SUM | 夜间时段交易（需流水级，汇总表无时段） | — | 近似：流出笔数/金额异常；标注盲区 |
| 38 | 家庭劣变/重大疾病 | G_00PL_PEAS_DOC_INFO_DV（MRGE_STS/FMLY_MB_HLTH_STS） | 婚姻状态=离异/非婚 或 家庭成员健康异常 | 命中即算 | 客户档案表有数据 |
| 39 | 负债不一致/收入覆盖不足 | B_00DT_FAS_ANL_SITU_DOC_H + B_00DT_FAS_FMLY_SITU_DOC_H | FMLY_ANNL_INCM < FMLY_DPS_ANNL_RPAMT | 收入<还款额 | FAS档案 |
| 40 | 涉税涉诉 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 41 | 涉诉记录 | P_00CIE_CPS_INDECATE_*（无数据） | — | — | **data_missing** |
| 42 | 资金挪用（放款后转出） | S_00PF_SA_ACCT_TR_CUST_SUM + G_00PF_PEAS_LN_VCH_DV | 放款后区间流出金额/笔数显著（需流水级） | 流出/放款额>80% | 汇总表近似 |
| 43 | 多贷一用/户贷企用/执照注销 | S_00PF_PEAS_LN_RSK_ORG_C4 / S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4 | RSK_LINE_TYP 触发占比、不属实占比 | 查表直接取 | 机构级已预聚合；执照状态无企业表 |
| 44 | 还款行为恶化 | G_00PL_IDV_LN_BILL_AMT + G_00PL_IDV_LN_ARG_EXD_DV | BILL_EXD_DAT 转逾期、EXD_NON_SQUA_BILL_CNT>0；结息还本异常 | 命中即算 | 账单+逾期表有数据 |
| 45 | 裸贷户 | B_00DT_FAS_ANL_SITU_DOC_H + B_00DT_FAS_FMLY_SITU_DOC_H | TOT_AST≈0 且无经营收入 | TOT_AST=0 且 VARS_ADMI_INCM=0 | FAS档案 |

## 四、data_missing 特征的替代口径

| 原特征 | 替代口径 | 数据表 |
|---|---|---|
| 6 信用负债敞口 | 风险线索类型触发（RSK_LINE_TYP） | S_00PF_PEAS_LN_RSK_ORG_C4 |
| 15 调查造假 | 地址异常风险类型（ADDR_RSK_TYP） | S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4 |
| 22 共用场所 | 地址异常风险类型（ADDR_RSK_TYP） | S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4 |
| 29 经营地址频繁变更 | 行业风险（KEY_OCP_COD）+ 建档质量 | S_00PF_PEAS_OCPRSK_ORG_C4 / LN_ARC_QLT |
| 32/34/35/36/40/41 征信类 | 均无征信P表 → 整体标注「信用与负债维度数据缺失」 | — |

## 五、输出格式

```json
{
  "feature_id": 1,
  "name": "零散获客风险",
  "dimension": "机构",
  "stage": "营销获客",
  "status": "ok",               // ok | data_missing | approximate
  "table": "S_00PF_PEAS_DIVR_RSK_C4",
  "metric": {"客户数": 123, "余额": 4567890.12, "不良率": 0.0132},
  "evidence": "DIVR_CTRT_RATE=0.4615",
  "note": ""
}
```
