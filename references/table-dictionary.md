# 表结构字典（table-dictionary）

> 依据《赛题数据结构说明.xls》自动生成。62 张表结构，其中 **49 张有数据文件**（CSV），14 张无数据。

## 一、数据文件清单（49 张）

| 表名 | 中文名 | 数据范围 | 文件大小 |
|---|---|---|---|
| B_00DT_APLO_RNEW_CR_VCH_RLN_H | APLO续贷凭证关系历史 | 20260831切片 | 49MB |
| B_00DT_C4_ORG_TREE_H | C4机构树历史 | 20260831切片 | 108MB |
| B_00DT_CYC_QUOT_INFO_H | 循环额度信息历史 | 20260831切片 | 219MB |
| B_00DT_FAS_ANL_SITU_DOC_H | 资产负债情况档案历史 | 20260831切片 | 87MB |
| B_00DT_FAS_FMLY_SITU_DOC_H | 家庭情况档案历史 | 20260831切片 | 48MB |
| B_00DT_FAS_IDV_BUS_INFO_H | FAS个体经营信息历史 | 20260831切片 | 118MB |
| B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H | 押品产权人信息历史 | 20260831切片 | 1MB |
| B_00DT_LN_FORM_CLS_EVT_H | 借款凭证分类结果历史 | 20260831切片 | 1.1GB |
| B_00DT_PRLN_SCRE_EVT_H | 个人贷款评分结果历史 | 20260831切片 | 3.7GB |
| B_00DT_UHLTH_LN_AMT_CHG_H | 不良贷款金额变动信息历史 | 20260831切片 | 48MB |
| B_00FT_PEAS_LN_DPSE_TASK_DTAL | 农户贷款属地贷后处置任务明细 | 20260101-20260831 | 739MB |
| B_00FT_PMC_P_DOORTASK_DTAL | 个人属地上门催收任务明细 | 20260301-20260831 | 2.0GB |
| G_00PF_IDV_LN_CTRT_DV | 个人贷款合同全量拼接表 | 20260831切片 | 2.2GB |
| G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV | 个人贷款凭证核销清收证券化拼接表 | 20260831切片 | 18.2GB |
| G_00PF_IDV_LN_VCH_DV | 个人贷款凭证拼接表 | 以20260831有效凭证为基准，提供20260331-20260831 | 15.9GB |
| G_00PF_PEAS_LN_FMLY_SITU_INFO | 农户贷款客户家庭村居情况信息表 | 20260831切片 | 66MB |
| G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO | 农户贷款上年末凭证本年接续情况信息表 | 20260831切片 | 62MB |
| G_00PF_PEAS_LN_VCH_DV | 农户贷款凭证拼接表 | 以20260831有效凭证为基准，提供20260331-20260831 | 16.9GB |
| G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO | 农户贷款白名单审查审批流程信息表 | 20260331-20260831 | 22MB |
| G_00PL_IDV_CUST_RLN_INFO_H | 个人信贷客户亲属信息表（含信用卡） | 20260831切片 | 167MB |
| G_00PL_IDV_LN_ARG_EXD_DV | 个人贷款逾期拼接表 | 20260831切片 | 573MB |
| G_00PL_IDV_LN_BILL_AMT | 个人贷款还款账单金额拼接表 | 20260831切片 | 2.2GB |
| G_00PL_IDV_LN_CUST_ACARD_SCRE_DV | 个人贷款客户A卡评分信息表 | 20240902-20260802 | 156MB |
| G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV | 个人贷款抵押房产风险信息表 | 20260831、20251231切片 | 4MB |
| G_00PL_PEAS_DOC_INFO_DV | 建档农户档案信息拼接表 | 20260831切片 | 313MB |
| P_00FAS_GFAS_VAF_LOAN_MANAGE | 联村带户贷款信息状态明细 | 20260301-20260831 | 271MB |
| P_00RLDM_RL_LOAN_SCORE | 贷款评分结果表 | 20260831切片 | 314MB |
| S_00PF_IDV_CUST_FA_SUM | 个人客户金融资产汇总 | 20260228-20260831 | 5.3GB |
| S_00PF_IDV_CUST_HOLD_PD_BAL_SUM | 个人客户持有产品余额汇总表 | 20260228-20260831 | 7.8GB |
| S_00PF_IDV_DP_CUST_SUM | 个人存款客户级汇总 | 20260228-20260831 | 5.0GB |
| S_00PF_PEAS_ACARD_SCRE_RSK_ORG_C4 | 农户贷款A卡评分行为风险机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4 | 农户贷款客户地址异常风险机构级分析表(C4机构树) | 20260831.0 | 2MB |
| S_00PF_PEAS_CONT_QUAL_C4 | 农户贷款接续质量机构级分析表（C4机构树） | 20260831.0 | 0MB |
| S_00PF_PEAS_DIVR_RSK_C4 | 农户贷款零散获客风险机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_HRZ_MGR_LN_ANL_C4 | 农户贷款高风险客户经理办贷机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4 | 农户贷款建档质量风险机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4 | 农户贷款业务品种机构级分析表(C4机构树) | 20260831.0 | 1MB |
| S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4 | 农户贷款重点关注风险线索处置质量机构级分析表(C4机构树) | 20260831.0 | 1MB |
| S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4 | 农户贷款大额信用风险机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_LN_RSK_ORG_C4 | 农户贷款风险线索处置质量机构级分析表(C4机构树) | 20260831.0 | 4MB |
| S_00PF_PEAS_LN_SPC_ORG_ANL_C4 | 农户贷款专项产品机构级分析表(C4机构树) | 20260301-20260831（每日） | 52MB |
| S_00PF_PEAS_MGG_RSK_C4 | 农户贷款抵押物风险机构级分析表(C4机构树) | 20260831.0 | 0MB |
| S_00PF_PEAS_MGR_LN_RISK_C4 | 农户贷款客户经理办贷风险特征表(C4机构树) | 20260831.0 | 1MB |
| S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4 | 农户贷款无抵押缓释风险机构级分析表(C4机构树) | 20260831.0 | 1MB |
| S_00PF_PEAS_OCPRSK_ORG_C4 | 农户贷款行业风险机构级分析表(C4机构树) | 20260331-20260831（月末） | 111MB |
| S_00PF_PEAS_OVER_FL_AC_RSK_C4 | 农户贷款超额授信风险机构级分析表(C4机构树) | 20260831.0 | 1MB |
| S_00PF_SA_ACCT_TR_CUST_SUM | 活期账户交易客户级汇总 | 20260228-20260831 | 734MB |
| S_00PL_IDV_LN_GRTE_RLN | 个人贷款担保关系 | 20260831切片 | 4MB |

## 二、无数据文件（14 张，勿直接取数）

- `B_00DT_APLO_GOHV_ECR_WHT_NAM_FORM_H` 惠农e贷白名单历史（20260831切片）
- `B_00DT_CORP_GX_ALTER_DTAL` 国信企业历史变更明细表（20260831切片）
- `B_00DT_CORP_GX_BASIC_H` 国信企业基本信息历史表（20260831切片）
- `B_00DT_FNC_CUST_AST_CERT_PAPR_IN_H` 押品权证信息历史（20260831切片）
- `B_00DT_IDV_RULE_CLUE_H` 个人规则线索历史（20260831切片）
- `B_00DT_MNG_INFO_CLUE_H` 个人信贷客户规则线索管理历史（20260831切片）
- `B_00FT_PEAS_LN_CHK_TASK_DTAL` 农户贷款属地贷后检查任务明细（20260301-20260831）
- `G_00PF_COM_ORG_TREE_DV` 数据中台通用机构树拼接表（20260831切片）
- `G_00PF_PEAS_LN_RSK_LINE_DPSE_PROC_INFO` 农户贷款风险线索处置全过程信息表（20260331-20260831）
- `G_00PL_PEAS_LN_ADDR_CHEK_DV` 农户贷款客户地址交叉检验信息表（20260331-20260831）
- `P_00CIE_CPS_INDECATE_COMPLIATEPROCESS` 个人客户信用报告混合模型解析表-复杂加工P3开头的指标（20260601、20260602）
- `P_00CIE_CPS_INDECATE_DIRECTEXTRA` 个人客户信用报告混合模型解析表-直接提取-P1开头的指标（20260601、20260602）
- `P_00CIE_CPS_INDECATE_SIMPLEPROCESS` 个人客户信用报告混合模型解析表-简单加工-P2开头的指标（20260601、20260602）
- `P_00PMC_PMC_P_CALLTASK` 个人属地电话催收任务明细（20260301-20260831）

> 这些表对应的风险指标改用机构级分析表（S_00PF_PEAS_*_C4）预聚合口径，或标注 data_missing。

## 三、表清单（按主题域）

| 序号 | 表英文名 | 表中文名 | 数据范围 | 有数据 |
|---|---|---|---|---|
| 1 | `B_00DT_APLO_GOHV_ECR_WHT_NAM_FORM_H` | 惠农e贷白名单历史 | 20260831切片 | ❌ |
| 2 | `B_00DT_APLO_RNEW_CR_VCH_RLN_H` | APLO续贷凭证关系历史 | 20260831切片 | ✅ |
| 3 | `B_00DT_C4_ORG_TREE_H` | C4机构树历史 | 20260831切片 | ✅ |
| 4 | `B_00DT_CORP_GX_ALTER_DTAL` | 国信企业历史变更明细表 | 20260831切片 | ❌ |
| 5 | `B_00DT_CORP_GX_BASIC_H` | 国信企业基本信息历史表 | 20260831切片 | ❌ |
| 6 | `B_00DT_CYC_QUOT_INFO_H` | 循环额度信息历史 | 20260831切片 | ✅ |
| 7 | `B_00DT_FAS_ANL_SITU_DOC_H` | 资产负债情况档案历史 | 20260831切片 | ✅ |
| 8 | `B_00DT_FAS_FMLY_SITU_DOC_H` | 家庭情况档案历史 | 20260831切片 | ✅ |
| 9 | `B_00DT_FAS_IDV_BUS_INFO_H` | FAS个体经营信息历史 | 20260831切片 | ✅ |
| 10 | `B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H` | 押品产权人信息历史 | 20260831切片 | ✅ |
| 11 | `B_00DT_FNC_CUST_AST_CERT_PAPR_IN_H` | 押品权证信息历史 | 20260831切片 | ❌ |
| 12 | `B_00DT_IDV_RULE_CLUE_H` | 个人规则线索历史 | 20260831切片 | ❌ |
| 13 | `B_00DT_LN_FORM_CLS_EVT_H` | 借款凭证分类结果历史 | 20260831切片 | ✅ |
| 14 | `B_00DT_MNG_INFO_CLUE_H` | 个人信贷客户规则线索管理历史 | 20260831切片 | ❌ |
| 15 | `B_00DT_PRLN_SCRE_EVT_H` | 个人贷款评分结果历史 | 20260831切片 | ✅ |
| 16 | `B_00DT_UHLTH_LN_AMT_CHG_H` | 不良贷款金额变动信息历史 | 20260831切片 | ✅ |
| 17 | `B_00FT_PEAS_LN_CHK_TASK_DTAL` | 农户贷款属地贷后检查任务明细 | 20260301-20260831 | ❌ |
| 18 | `B_00FT_PEAS_LN_DPSE_TASK_DTAL` | 农户贷款属地贷后处置任务明细 | 20260101-20260831 | ✅ |
| 19 | `B_00FT_PMC_P_DOORTASK_DTAL` | 个人属地上门催收任务明细 | 20260301-20260831 | ✅ |
| 20 | `G_00PF_COM_ORG_TREE_DV` | 数据中台通用机构树拼接表 | 20260831切片 | ❌ |
| 21 | `G_00PF_IDV_LN_CTRT_DV` | 个人贷款合同全量拼接表 | 20260831切片 | ✅ |
| 22 | `G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV` | 个人贷款凭证核销清收证券化拼接表 | 20260831切片 | ✅ |
| 23 | `G_00PF_IDV_LN_VCH_DV` | 个人贷款凭证拼接表 | 以20260831有效凭证为基准，提供20260331-20260831 | ✅ |
| 24 | `G_00PF_PEAS_LN_FMLY_SITU_INFO` | 农户贷款客户家庭村居情况信息表 | 20260831切片 | ✅ |
| 25 | `G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO` | 农户贷款上年末凭证本年接续情况信息表 | 20260831切片 | ✅ |
| 26 | `G_00PF_PEAS_LN_RSK_LINE_DPSE_PROC_INFO` | 农户贷款风险线索处置全过程信息表 | 20260331-20260831 | ❌ |
| 27 | `G_00PF_PEAS_LN_VCH_DV` | 农户贷款凭证拼接表 | 以20260831有效凭证为基准，提供20260331-20260831 | ✅ |
| 28 | `G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO` | 农户贷款白名单审查审批流程信息表 | 20260331-20260831 | ✅ |
| 29 | `G_00PL_IDV_CUST_RLN_INFO_H` | 个人信贷客户亲属信息表（含信用卡） | 20260831切片 | ✅ |
| 30 | `G_00PL_IDV_LN_ARG_EXD_DV` | 个人贷款逾期拼接表 | 20260831切片 | ✅ |
| 31 | `G_00PL_IDV_LN_BILL_AMT` | 个人贷款还款账单金额拼接表 | 20260831切片 | ✅ |
| 32 | `G_00PL_IDV_LN_CUST_ACARD_SCRE_DV` | 个人贷款客户A卡评分信息表 | 20240902-20260802 | ✅ |
| 33 | `G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV` | 个人贷款抵押房产风险信息表 | 20260831、20251231切片 | ✅ |
| 34 | `G_00PL_PEAS_DOC_INFO_DV` | 建档农户档案信息拼接表 | 20260831切片 | ✅ |
| 35 | `G_00PL_PEAS_LN_ADDR_CHEK_DV` | 农户贷款客户地址交叉检验信息表 | 20260331-20260831 | ❌ |
| 36 | `P_00CIE_CPS_INDECATE_COMPLIATEPROCESS` | 个人客户信用报告混合模型解析表-复杂加工P3开头的指标 | 20260601、20260602 | ❌ |
| 37 | `P_00CIE_CPS_INDECATE_DIRECTEXTRA` | 个人客户信用报告混合模型解析表-直接提取-P1开头的指标 | 20260601、20260602 | ❌ |
| 38 | `P_00CIE_CPS_INDECATE_SIMPLEPROCESS` | 个人客户信用报告混合模型解析表-简单加工-P2开头的指标 | 20260601、20260602 | ❌ |
| 39 | `P_00FAS_GFAS_VAF_LOAN_MANAGE` | 联村带户贷款信息状态明细 | 20260301-20260831 | ✅ |
| 40 | `P_00PMC_PMC_P_CALLTASK` | 个人属地电话催收任务明细 | 20260301-20260831 | ❌ |
| 41 | `P_00RLDM_RL_LOAN_SCORE` | 贷款评分结果表 | 20260831切片 | ✅ |
| 42 | `S_00PF_IDV_CUST_FA_SUM` | 个人客户金融资产汇总 | 20260228-20260831 | ✅ |
| 43 | `S_00PF_IDV_CUST_HOLD_PD_BAL_SUM` | 个人客户持有产品余额汇总表 | 20260228-20260831 | ✅ |
| 44 | `S_00PF_IDV_DP_CUST_SUM` | 个人存款客户级汇总 | 20260228-20260831 | ✅ |
| 45 | `S_00PF_PEAS_ACARD_SCRE_RSK_ORG_C4` | 农户贷款A卡评分行为风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 46 | `S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4` | 农户贷款客户地址异常风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 47 | `S_00PF_PEAS_CONT_QUAL_C4` | 农户贷款接续质量机构级分析表（C4机构树） | 20260831.0 | ✅ |
| 48 | `S_00PF_PEAS_DIVR_RSK_C4` | 农户贷款零散获客风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 49 | `S_00PF_PEAS_HRZ_MGR_LN_ANL_C4` | 农户贷款高风险客户经理办贷机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 50 | `S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4` | 农户贷款建档质量风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 51 | `S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4` | 农户贷款业务品种机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 52 | `S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4` | 农户贷款重点关注风险线索处置质量机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 53 | `S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4` | 农户贷款大额信用风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 54 | `S_00PF_PEAS_LN_RSK_ORG_C4` | 农户贷款风险线索处置质量机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 55 | `S_00PF_PEAS_LN_SPC_ORG_ANL_C4` | 农户贷款专项产品机构级分析表(C4机构树) | 20260301-20260831（每日） | ✅ |
| 56 | `S_00PF_PEAS_MGG_RSK_C4` | 农户贷款抵押物风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 57 | `S_00PF_PEAS_MGR_LN_RISK_C4` | 农户贷款客户经理办贷风险特征表(C4机构树) | 20260831.0 | ✅ |
| 58 | `S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4` | 农户贷款无抵押缓释风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 59 | `S_00PF_PEAS_OCPRSK_ORG_C4` | 农户贷款行业风险机构级分析表(C4机构树) | 20260331-20260831（月末） | ✅ |
| 60 | `S_00PF_PEAS_OVER_FL_AC_RSK_C4` | 农户贷款超额授信风险机构级分析表(C4机构树) | 20260831.0 | ✅ |
| 61 | `S_00PF_SA_ACCT_TR_CUST_SUM` | 活期账户交易客户级汇总 | 20260228-20260831 | ✅ |
| 62 | `S_00PL_IDV_LN_GRTE_RLN` | 个人贷款担保关系 | 20260831切片 | ✅ |

## 四、关键表字段明细（脚本取数依据）

### `G_00PF_PEAS_LN_VCH_DV`（农户贷款凭证拼接表，98 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `LN_FORM_ORI_NO` | 借款凭证原始号码 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USE_CD` | 借款用途 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `GRTE_CTRT_NO` | 担保合同编号 | VARCHAR |  |  |
| `LN_USE_CLS_CD` | 借款用途分类 | VARCHAR |  |  |
| `LN_CMPHSV_CLS_CD` | 贷款综合分类 | VARCHAR |  |  |
| `LN_IVST_DIRE_OCPCLS_CD` | 贷款投向行业分类 | VARCHAR |  |  |
| `LN_IVDIR_NATECO_OCPCLS_CD` | 贷款投向国民经济行业分类 | VARCHAR |  |  |
| `PBC_ARGI_LN_CLS_CD` | 人行涉农贷款分类 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险业务 | VARCHAR |  |  |
| `RSK_BUS_CTG` | 低风险业务类别 | VARCHAR |  |  |
| `CYC_LN_IND` | 是否可循环贷款 | VARCHAR |  |  |
| `SUBSD_INTS_LN_IND` | 是否贴息贷款 | VARCHAR |  |  |
| `SUBSD_INTS_END_DAT` | 贴息截止日期 | VARCHAR |  |  |
| `SUBSD_INTS_RATE` | 贴息率 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `ADJ_MATU_DAT` | 调整后到期日 | VARCHAR |  |  |
| `ACTNG_ENT_ACCT_DAT` | 会计入账日期 | VARCHAR |  |  |
| `RNEW_APTMT_IND` | 展期约期标识 | VARCHAR |  |  |
| `RNEW_MATU_DAT` | 展期到期日 | VARCHAR |  |  |
| `RPAY_MOD_CD` | 还款方式 | VARCHAR |  |  |
| `CCY_CD` | 币种 | VARCHAR |  |  |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `LN_AMT` | 借款金额 | DECIMAL |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL` | 凭证余额 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `IN_BLNC_ARREA_INTS` | 表内欠息 | DECIMAL |  |  |
| `OFF_BLNC_ARREA_INTS` | 表外欠息 | DECIMAL |  |  |
| `TOT_CAN_CAP` | 累计核销本金 | DECIMAL |  |  |
| `TOT_CAN_INTS` | 累计核销利息 | DECIMAL |  |  |
| `TOT_DBT_OS_CAP` | 累计抵债本金 | DECIMAL |  |  |
| `TOT_DBT_OS_INTS` | 累计抵债利息 | DECIMAL |  |  |
| `CAP_CNTRC_DBT_IND` | 以资抵债标志 | VARCHAR |  |  |
| `RSK_CLS_CD` | 风险分类 | VARCHAR |  |  |
| `INTL_GRD_CLS_CD` | 内部评级分类 | VARCHAR |  |  |
| `FST_FORM_NO` | 首笔凭证编号 | VARCHAR |  |  |
| `FST_FORM_PRVD_DAT` | 首笔凭证发放日期 | VARCHAR |  |  |
| `ABIS_BRCH_NO` | ABIS机构编码 | VARCHAR |  |  |
| `ABIS_BUS_BREED` | ABIS业务品种 | VARCHAR |  |  |
| `LN_ACCT_NO` | 贷款账号 | VARCHAR |  |  |
| `RPAY_TYP_CD` | 还款类型 | VARCHAR |  |  |
| `WON_AUTO_DDCT_CAP` | 是否自动扣收本金 | VARCHAR |  |  |
| `AUTO_DDCT_CAP_STRT_AMT` | 自动扣收本金起点金额 | DECIMAL |  |  |
| `CLTN_ACCT_NO` | 收款账号 | VARCHAR |  |  |
| `RPAY_ACCT_NO_1` | 还款账号1 | VARCHAR |  |  |
| `RPAY_ACCT_NO_2` | 还款账号2 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO` | 自由还账号 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO_RETQUOT` | 自由还账号留存额度 | DECIMAL |  |  |
| `PRGS_TLMT_MSG_DAT` | 诉讼时效提示日期 | VARCHAR |  |  |
| `DISB_FLOW_STS_CD` | 放款流程状态标志 | VARCHAR |  |  |
| `FORM_STS_CD` | 凭证状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_ORG_COD` | 放款机构编码 | VARCHAR |  |  |
| `DISB_ORG_COD_STD` | 机构备用字段 | VARCHAR |  |  |
| `MAGR_CD` | 客户经理代码 | VARCHAR |  |  |
| `OPR_ORG_COD` | 操作机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `FST_OPR_DAT` | 首次操作日期 | VARCHAR |  |  |
| `FST_OPR_TIME` | 首次操作时间 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `AGENT_CTG_CD` | 委托人类别 | VARCHAR |  |  |
| `DPRT_FTR_CLS_CD` | 部门特色分类 | VARCHAR |  |  |
| `FRN_EXCH_PLGE_LN_CLS_CD` | 外汇保证贷款分类 | VARCHAR |  |  |
| `CLTN_PSN_ISBN` | 收款人代码 | VARCHAR |  |  |
| `MARG_CTRL_IND` | 是否控制保证金 | VARCHAR |  |  |
| `MARG_CTRL_MOD_CD` | 保证金控制方式 | VARCHAR |  |  |
| `MARG_CTRL_PPTN` | 保证金控制比例 | DECIMAL |  |  |
| `MARG_FIX_QUOT` | 保证金固定额度 | DECIMAL |  |  |
| `MARG_CCY_CD` | 保证金币种 | VARCHAR |  |  |
| `SELF_LOWT_RPAY_QUOT` | 自由还最低还款额度 | DECIMAL |  |  |
| `SELF_HGST_RPAY_QUOT` | 自由还最高还款额度 | DECIMAL |  |  |
| `FNC_PROD_CLS_CD` | 信贷产品分类 | VARCHAR |  |  |
| `PAY_MOD_CD` | 支付方式代码 | VARCHAR |  |  |
| `NTRL_DSTR_EFCT_CD` | 自然灾害影响代码 | VARCHAR |  |  |
| `EXD_DAT` | 逾期日期 | VARCHAR |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_TYP` | 逾期类型 | VARCHAR |  |  |
| `CAN_STS_CD` | 核销状态代码 | VARCHAR |  |  |
| `CAN_ACTNG_DAT` | 核销会计日期 | VARCHAR |  |  |
| `DAT_SOR_CD` | 数据来源代码 | VARCHAR | 是 |  |
| `LAST_UPD_DAT` | 最后更新日期 | DATE |  |  |
| `CONT_LN_IND` | 是否接续贷款 | VARCHAR |  |  |
| `CONTINUE_FLAG` | 从前手凭证接续方式 | VARCHAR |  |  |
| `RMOT_HLDR_CTRT_NO` | 前手合同号 | VARCHAR |  |  |
| `RMOT_HLDR_FORM_NO` | 前手凭证号 | VARCHAR |  |  |
| `RMOT_HLDR_LN_ARG_NO` | 前手贷款合约号 | VARCHAR |  |  |

### `G_00PF_IDV_LN_VCH_DV`（个人贷款凭证拼接表，94 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `LN_FORM_ORI_NO` | 借款凭证原始号码 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USE_CD` | 借款用途 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `GRTE_CTRT_NO` | 担保合同编号 | VARCHAR |  |  |
| `LN_USE_CLS_CD` | 借款用途分类 | VARCHAR |  |  |
| `LN_CMPHSV_CLS_CD` | 贷款综合分类 | VARCHAR |  |  |
| `LN_IVST_DIRE_OCPCLS_CD` | 贷款投向行业分类 | VARCHAR |  |  |
| `LN_IVDIR_NATECO_OCPCLS_CD` | 贷款投向国民经济行业分类 | VARCHAR |  |  |
| `PBC_ARGI_LN_CLS_CD` | 人行涉农贷款分类 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险业务 | VARCHAR |  |  |
| `RSK_BUS_CTG` | 低风险业务类别 | VARCHAR |  |  |
| `CYC_LN_IND` | 是否可循环贷款 | VARCHAR |  |  |
| `SUBSD_INTS_LN_IND` | 是否贴息贷款 | VARCHAR |  |  |
| `SUBSD_INTS_END_DAT` | 贴息截止日期 | VARCHAR |  |  |
| `SUBSD_INTS_RATE` | 贴息率 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `ADJ_MATU_DAT` | 调整后到期日 | VARCHAR |  |  |
| `ACTNG_ENT_ACCT_DAT` | 会计入账日期 | VARCHAR |  |  |
| `RNEW_APTMT_IND` | 展期约期标识 | VARCHAR |  |  |
| `RNEW_MATU_DAT` | 展期到期日 | VARCHAR |  |  |
| `RPAY_MOD_CD` | 还款方式 | VARCHAR |  | 1-一次性利随本清还款
2-一次性还本按约还息
3-自订计划分期还款
4-等额本 |
| `CCY_CD` | 币种 | VARCHAR |  |  |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `LN_AMT` | 借款金额 | DECIMAL |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL` | 凭证余额 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `IN_BLNC_ARREA_INTS` | 表内欠息 | DECIMAL |  |  |
| `OFF_BLNC_ARREA_INTS` | 表外欠息 | DECIMAL |  |  |
| `TOT_CAN_CAP` | 累计核销本金 | DECIMAL |  |  |
| `TOT_CAN_INTS` | 累计核销利息 | DECIMAL |  |  |
| `TOT_DBT_OS_CAP` | 累计抵债本金 | DECIMAL |  |  |
| `TOT_DBT_OS_INTS` | 累计抵债利息 | DECIMAL |  |  |
| `CAP_CNTRC_DBT_IND` | 以资抵债标志 | VARCHAR |  |  |
| `RSK_CLS_CD` | 风险分类 | VARCHAR |  |  |
| `INTL_GRD_CLS_CD` | 内部评级分类 | VARCHAR |  |  |
| `FST_FORM_NO` | 首笔凭证编号 | VARCHAR |  |  |
| `FST_FORM_PRVD_DAT` | 首笔凭证发放日期 | VARCHAR |  |  |
| `ABIS_BRCH_NO` | ABIS机构编码 | VARCHAR |  |  |
| `ABIS_BUS_BREED` | ABIS业务品种 | VARCHAR |  |  |
| `LN_ACCT_NO` | 贷款账号 | VARCHAR |  |  |
| `RPAY_TYP_CD` | 还款类型 | VARCHAR |  |  |
| `WON_AUTO_DDCT_CAP` | 是否自动扣收本金 | VARCHAR |  |  |
| `AUTO_DDCT_CAP_STRT_AMT` | 自动扣收本金起点金额 | DECIMAL |  |  |
| `CLTN_ACCT_NO` | 收款账号 | VARCHAR |  |  |
| `RPAY_ACCT_NO_1` | 还款账号1 | VARCHAR |  |  |
| `RPAY_ACCT_NO_2` | 还款账号2 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO` | 自由还账号 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO_RETQUOT` | 自由还账号留存额度 | DECIMAL |  |  |
| `PRGS_TLMT_MSG_DAT` | 诉讼时效提示日期 | VARCHAR |  |  |
| `DISB_FLOW_STS_CD` | 放款流程状态标志 | VARCHAR |  |  |
| `FORM_STS_CD` | 凭证状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_ORG_COD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_ORG_COD_STD` | 放款EIMO机构编码 | VARCHAR |  |  |
| `MAGR_CD` | 首贷客户经理代码 | VARCHAR |  |  |
| `OPR_ORG_COD` | 操作机构C4机构编码 | VARCHAR |  |  |
| `OPR_EIMO_ORG_COD` | 操作机构EIMO机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `FST_OPR_DAT` | 首次操作日期 | VARCHAR |  |  |
| `FST_OPR_TIME` | 首次操作时间 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `AGENT_CTG_CD` | 委托人类别 | VARCHAR |  |  |
| `DPRT_FTR_CLS_CD` | 部门特色分类 | VARCHAR |  |  |
| `FRN_EXCH_PLGE_LN_CLS_CD` | 外汇保证贷款分类 | VARCHAR |  |  |
| `CLTN_PSN_ISBN` | 收款人代码 | VARCHAR |  |  |
| `MARG_CTRL_IND` | 是否控制保证金 | VARCHAR |  |  |
| `MARG_CTRL_MOD_CD` | 保证金控制方式 | VARCHAR |  |  |
| `MARG_CTRL_PPTN` | 保证金控制比例 | DECIMAL |  |  |
| `MARG_FIX_QUOT` | 保证金固定额度 | DECIMAL |  |  |
| `MARG_CCY_CD` | 保证金币种 | VARCHAR |  |  |
| `SELF_LOWT_RPAY_QUOT` | 自由还最低还款额度 | DECIMAL |  |  |
| `SELF_HGST_RPAY_QUOT` | 自由还最高还款额度 | DECIMAL |  |  |
| `FNC_PROD_CLS_CD` | 信贷产品分类 | VARCHAR |  |  |
| `PAY_MOD_CD` | 支付方式代码 | VARCHAR |  |  |
| `NTRL_DSTR_EFCT_CD` | 自然灾害影响代码 | VARCHAR |  |  |
| `EXD_DAT` | 逾期日期 | VARCHAR |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_TYP` | 逾期类型 | VARCHAR |  |  |
| `CAN_STS_CD` | 核销状态代码 | VARCHAR |  |  |
| `CAN_ACTNG_DAT` | 核销会计日期 | VARCHAR |  |  |
| `DAT_SOR_CD` | 数据来源代码 | VARCHAR | 是 |  |
| `LAST_UPD_DAT` | 最后更新日期 | DATE |  |  |

### `G_00PL_IDV_LN_ARG_EXD_DV`（个人贷款逾期拼接表，21 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FNCL_ENT_NO` | 金融实体代码 | VARCHAR | 是 |  |
| `ARG_NO` | 合约号 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证号 | VARCHAR |  |  |
| `AR_LCS_CD` | 合约生命周期状态码 | VARCHAR |  |  |
| `LN_CAN_STS_IND` | 核销状态标识 | VARCHAR |  |  |
| `ALR_PRVD_AMT` | 贷款发放额 | DECIMAL |  |  |
| `BOE_CAP_BAL` | 本金余额 | DECIMAL |  |  |
| `EXD_CAP` | 逾期本金 | DECIMAL |  |  |
| `REV_NONPAY_NML_INTS` | 逾期正常息 | DECIMAL |  |  |
| `REV_NONPAY_DEF_INTS` | 逾期罚息 | DECIMAL |  |  |
| `REV_NONPAY_COM_INTS` | 逾期复利 | DECIMAL |  |  |
| `BILL_EXD_DAT` | 逾期日期 | VARCHAR |  |  |
| `BILL_EXD_DAYS` | 逾期天数 | INT |  |  |
| `ALR_CLTN_CAP` | 本金还款 | DECIMAL |  |  |
| `ALR_CLTN_NML_INTS` | 正常息还款 | DECIMAL |  |  |
| `ALR_CLTN_DEF_INTS` | 罚息还款 | DECIMAL |  |  |
| `ALR_CLTN_COM_INTS` | 复利还款 | DECIMAL |  |  |
| `ALR_SQUA_BILL_CNT` | 已结清账单数 | INT |  |  |
| `EXD_NON_SQUA_BILL_CNT` | 逾期未结清账单数 | INT |  |  |
| `H_TOT_EXD_BILL_CNT` | 历史上累计逾期账单数 | INT |  |  |

### `G_00PL_IDV_LN_BILL_AMT`（个人贷款还款账单金额拼接表，49 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR | 是 |  |
| `ARG_NO` | 合约号 | VARCHAR | 是 |  |
| `BILL_NO` | 账单号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户ID | VARCHAR |  |  |
| `FORM_NO` | 凭证编号 | VARCHAR |  |  |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `BUS_BREED` | 业务品种代码 | VARCHAR |  |  |
| `LN_IVDIR_NATECO_OCPCLS` | 贷款投向国民经济行业分类 | VARCHAR |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `BILL_TYP` | 账单类型 | VARCHAR |  |  |
| `RPAY_DAY_SER_NO` | 还款期顺序号 | INT |  |  |
| `BILL_RPAY_TYP_CD` | 账单还款类型代码 | VARCHAR |  | 00-不结息
01-定期结息 |
| `BILL_CRT_DAT` | 账单生成日期 | VARCHAR |  |  |
| `BILL_RPAY_DAT` | 账单还款日期 | VARCHAR |  |  |
| `BILL_EXD_DAT` | 账单转逾期日期 | VARCHAR |  |  |
| `BILL_SQUA_DAT` | 账单结清日期 | VARCHAR |  |  |
| `TOLE_DAY_MATU_DAT` | 宽限期到期日期 | VARCHAR |  |  |
| `CUTPD_SHD_REPAY_DP_DAY` | 本期应还款日 | VARCHAR |  |  |
| `SUBSD_DCLR_DAT` | 补贴申报日期 | VARCHAR |  |  |
| `CLAM_DCLR_DAT` | 理赔申报日期 | VARCHAR |  |  |
| `BILL_ATTR_INFO` | 账单属性信息 | VARCHAR |  |  |
| `BILL_STS_CD` | 账单状态代码 | VARCHAR |  |  |
| `BILL_FORM_CD` | 账单形态代码 | VARCHAR |  |  |
| `BILL_RSK_FORM_IND` | 账单风险形态标识 | VARCHAR |  |  |
| `BILL_CAP_SQUA_STS_IND` | 账单本金结清状态标识 | VARCHAR |  |  |
| `BILL_INTS_SQUA_STS_IND` | 账单利息结清状态标识 | VARCHAR |  |  |
| `SUBSD_STS_IND` | 补贴状态标识 | VARCHAR |  |  |
| `ADRPY_IND` | 提前还款标识 | VARCHAR |  |  |
| `ALR_CAP` | 已收本金 | DECIMAL |  |  |
| `REV_NONPAY_CAP` | 应收未收本金 | DECIMAL |  |  |
| `ADRPY_CAP` | 提前还款本金 | DECIMAL |  |  |
| `ALR_CLTN_NML_INTS` | 已收正常息 | DECIMAL |  |  |
| `NML_INTS_ARREA_INTS` | 正常息欠息 | DECIMAL |  |  |
| `REV_NONPAY_NML_INTS` | 应收未收正常息 | DECIMAL |  |  |
| `ALR_CLTN_DEF_INTS` | 已收罚息 | DECIMAL |  |  |
| `DEF_INTS_ARREA_INTS` | 罚息欠息 | DECIMAL |  |  |
| `REV_NONPAY_DEF_INTS` | 应收未收罚息 | DECIMAL |  |  |
| `ALR_CLTN_COM_INTS` | 已收复利 | DECIMAL |  |  |
| `COM_INTS_ARREA_INTS` | 复利欠息 | DECIMAL |  |  |
| `REV_NONPAY_COM_INTS` | 应收未收复利 | DECIMAL |  |  |
| `CUTPD_SHD_REPAY_CAP` | 本期应还本金 | DECIMAL |  |  |
| `CUTPD_SHD_REPAY_NML_INTS` | 本期应还正常息 | DECIMAL |  |  |
| `CUTPD_SHD_REPAY_DEF_INTS` | 本期应还罚息 | DECIMAL |  |  |
| `CUTPD_SHD_REPAY_COM_INTS` | 本期应还复利 | DECIMAL |  |  |
| `StartDt` | 开始日期 | DATE | 是 |  |
| `EndDt` | 结束日期 | DATE |  |  |
| `ValidDt` | 有效时间 | DATE |  |  |
| `Timestamp` | 时间戳 | DATETIME |  |  |

### `G_00PL_PEAS_DOC_INFO_DV`（建档农户档案信息拼接表，53 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `ID_CARD_NO` | 身份证号码 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR |  |  |
| `BUS_DPRT` | C4营业部门 | VARCHAR |  |  |
| `BUS_DPRT_STD` | C4营业部门备用字段 | VARCHAR |  |  |
| `FSBRH_ORG` | C4一级分行机构号 | VARCHAR |  |  |
| `FSBRH_ORG_STD` | 一级分行机构备用字段 | VARCHAR |  |  |
| `SCBRH_ORG` | C4二级分行机构号 | VARCHAR |  |  |
| `SCBRH_ORG_STD` | 二级分行机构备用字段 | VARCHAR |  |  |
| `SBRH_ORG` | C4支行机构号 | VARCHAR |  |  |
| `SBRH_ORG_STD` | 支行机构备用字段 | VARCHAR |  |  |
| `NAM` | 姓名 | VARCHAR |  |  |
| `SEX` | 性别 | VARCHAR |  |  |
| `MP_NO` | 手机号码 | VARCHAR |  |  |
| `CERT_VALD_END_DAT` | 证件有效截止日期 | VARCHAR |  |  |
| `PERM_ADDR` | 常住地址 | VARCHAR |  |  |
| `LOCAL_PERM_ADDR` | 本地常住 | VARCHAR |  |  |
| `CUR_PLCE_RES_YEAR` | 本地居住年限 | DECIMAL |  |  |
| `RES_STS` | 居住状况 | VARCHAR |  |  |
| `ADMI_SUBJ_TYP` | 经营主体类型 | VARCHAR |  |  |
| `MEMBER_SHIP_STATU` | 农民专业合作社社员身份 | VARCHAR |  |  |
| `IDV_OCP` | 个人职业 | VARCHAR |  |  |
| `FMLY_MB_HLTH_STS` | 家庭成员健康状况 | VARCHAR |  |  |
| `EVAL_CHARACTER` | 个人品质 | VARCHAR |  |  |
| `MRGE_STS` | 婚姻状况 | VARCHAR |  |  |
| `PLC_STS` | 政治面貌 | VARCHAR |  |  |
| `WON_HNT_SRV_PONT` | 是否惠农通服务点 | VARCHAR |  |  |
| `CULT_DGR` | 文化程度 | VARCHAR |  |  |
| `EN_PSN` | 录入人 | VARCHAR |  |  |
| `EN_TIME` | 录入时间 | VARCHAR |  |  |
| `MNG_MAGR` | 管户经理 | VARCHAR |  |  |
| `CLAIM_TIME` | 认领时间 | VARCHAR |  |  |
| `ARCHIVE_TIME` | 建档时间 | VARCHAR |  |  |
| `STS` | 状态 | VARCHAR |  | 00-已失效
01-导入未提交
02-导入已提交
03-未认领
04-已认领
0 |
| `OWN_RURA_ID` | 所属村编号 | VARCHAR |  |  |
| `OWN_RURA_NAME` | 所属村名称 | VARCHAR |  |  |
| `DATA_SOR` | 数据来源 | VARCHAR |  |  |
| `COLLECT_CHANL` | 采集渠道 | VARCHAR |  |  |
| `COLLECT_PLACE` | 采集地 | VARCHAR |  |  |
| `IS_CREDIT_CHEK` | 是否已查征信 | VARCHAR |  |  |
| `BUS_DPRT_ORG_NAM` | 营业部门机构名称 | VARCHAR |  |  |
| `REM` | 备注 | VARCHAR |  |  |
| `IS_FACE_RECOG` | 是否人脸识别 | VARCHAR |  |  |
| `PROV_NO` | 省号 | VARCHAR |  |  |
| `EN_PSN_NAM` | 录入人姓名 | VARCHAR |  |  |
| `MNG_MAGR_NAM` | 管户经理姓名 | VARCHAR |  |  |
| `IMP_ORG` | C4导入机构编码 | VARCHAR |  |  |
| `IMP_ORG_NAM` | 导入机构名称 | VARCHAR |  |  |
| `IMP_SBRH_ORG` | C4导入支行机构编码 | VARCHAR |  |  |
| `IMP_SBRH_ORG_NAM` | 导入支行机构名称 | VARCHAR |  |  |
| `DOC_TYP` | 建档方式 | VARCHAR |  | 01-行政村建档
02-合作方建档 |
| `MOV_TN_DOC_IND` | 移动端建档标识 | VARCHAR |  |  |
| `TYPE_YX` | 精准营销客群分类 | VARCHAR |  |  |

### `G_00PL_IDV_LN_CUST_ACARD_SCRE_DV`（个人贷款客户A卡评分信息表，15 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `APLY_SER_NO` | 申请单序号 | VARCHAR | 是 |  |
| `FNC_PROD_NAM` | 信贷产品名称 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编码 | VARCHAR | 是 |  |
| `ORG_NO_C4` | 申请机构C4机构编码 | VARCHAR |  |  |
| `ORG_NO_C4_EIMO` | 申请机构EIMO机构编码 | VARCHAR |  |  |
| `SCRE_MDL_NO` | 评分卡模型编码 | VARCHAR |  |  |
| `SCRE_MDL_NAM` | 评分卡名称 | VARCHAR |  |  |
| `GRD_DAT` | 评级日期 | VARCHAR |  |  |
| `GRD_TIME` | 评级时间 | VARCHAR |  |  |
| `SCRE` | 分值 | DECIMAL |  |  |
| `WON_OLD_CUST` | 是否老客户 | VARCHAR |  |  |
| `WON_GOV_OR_PEAS_GRTE` | 是否政府增信或农担公司担保 | VARCHAR |  |  |
| `SCRE_APRIN_TRHD` | 评分卡准入阈值 | DECIMAL |  |  |
| `WON_SCRE_PASS` | 评分是否通过 | VARCHAR |  |  |

### `B_00DT_FAS_ANL_SITU_DOC_H`（资产负债情况档案历史，46 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR | 是 |  |
| `ID_CARD_NO` | 身份证号码 | VARCHAR | 是 |  |
| `TOT_AST` | 总资产 ( 万元 ) | DECIMAL |  |  |
| `FARM_LAND` | 农地 ( 亩 ) | DECIMAL |  |  |
| `FARM_VALUE` | 农地价值 | DECIMAL |  |  |
| `CONTRACTED` | 承包经营 ( 亩 ) | DECIMAL |  |  |
| `FLOW2OBTAIN` | 流转取得 ( 亩 ) | DECIMAL |  |  |
| `ALPAY_FLOW_TFRNT_MATU_DAT` | 已支付流转租金到期日 | VARCHAR |  |  |
| `LND_FLOW_TF_PRIC` | 土地流转价格 | DECIMAL |  |  |
| `COMM_HOUSE_QUANT` | 商品房数量 ( 套/幢 ) | DECIMAL |  |  |
| `COMM_HOUSE_AREA` | 商品房面积 ( m2 ) | DECIMAL |  |  |
| `COMM_HOUSE_VALUE` | 商品房价值 ( 万元 ) | DECIMAL |  |  |
| `FARM_HOUSE_QUANT` | 农房数量 ( 套/幢 ) | DECIMAL |  |  |
| `FARM_HOUSE_AREA` | 农房面积 ( m2 ) | DECIMAL |  |  |
| `FARM_HOUSE_VALUE` | 农房价值 ( 万元 ) | DECIMAL |  |  |
| `CAR_QUANT` | 汽车数量 ( 辆 ) | DECIMAL |  |  |
| `AUTO_MBL_VLU` | 汽车价值 ( 万元 ) | DECIMAL |  |  |
| `FARM_MACHIN_QUANT` | 农用机械数量 ( 台 ) | DECIMAL |  |  |
| `FARM_MACHIN_VALUE` | 农用机械价值 ( 万元 ) | DECIMAL |  |  |
| `PRIT_ERP_NAME` | 私人企业名称 | VARCHAR |  |  |
| `PRIT_ERP_VALUE` | 私人企业价值 | DECIMAL |  |  |
| `IDV_ADMI_NAM` | 个体经营名称 | VARCHAR |  |  |
| `IDV_ADMI_VLU` | 个体经营价值 ( 万元 ) | DECIMAL |  |  |
| `BIO_AST_VLU` | 生物资产价值 ( 万元 ) | DECIMAL |  |  |
| `ABC_FNCL_AST` | 农行金融资产 ( 万元 ) | DECIMAL |  |  |
| `OTH_BANK_FNCL_AST` | 他行金融资产 ( 万元 ) | DECIMAL |  |  |
| `OTH_AST` | 其他资产 | DECIMAL |  |  |
| `TOT_DPS` | 总负债 ( 万元 ) | DECIMAL |  |  |
| `FMLY_DPS_ANNL_RPAMT` | 家庭负债年还款额 ( 万元 ) | DECIMAL |  |  |
| `ABC_LN` | 农行贷款 ( 万元 ) | DECIMAL |  |  |
| `OTH_BANK_LN` | 他行贷款 ( 万元 ) | DECIMAL |  |  |
| `FOLK_LOAN` | 民间借款 ( 万元 ) | DECIMAL |  |  |
| `EXT_GRTE` | 对外担保 ( 万元 ) | DECIMAL |  |  |
| `OTH_DPS` | 其他负债 ( 万元 ) | DECIMAL |  |  |
| `PROV_NO` | 省号 | VARCHAR | 是 |  |
| `MSME_UNIT_SOCL_CR_CD` | 社会统一信用代码 ( 小微企业 ) | VARCHAR |  |  |
| `IDV_UNIT_SOCL_CR_CD` | 统一社会信用代码 ( 个体工商户 ) | VARCHAR |  |  |
| `PEAS_FNCL_AST_QRY_DAT` | 农户金融资产查询日期 | VARCHAR |  |  |
| `PRIT_ERP_NUM` | 私人企业数量 | DECIMAL |  |  |
| `IDV_ADMI_NUM` | 个体经营数量 | DECIMAL |  |  |
| `DPS_QRY_EVT` | 负债查询事件 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `STARTDT` | 开始日期 | DATE | 是 |  |
| `ENDDT` | 结束日期 | DATE |  |  |
| `VALIDDT` | 有效日期 | DATE |  |  |
| `TIMESTAMP` | 时间戳 | DATETIME |  |  |

### `B_00DT_FAS_FMLY_SITU_DOC_H`（家庭情况档案历史，17 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR | 是 |  |
| `ID_CARD_NO` | 身份证号码 | VARCHAR | 是 |  |
| `FMLY_NUM_PPL` | 家庭人数 | DECIMAL |  |  |
| `LAB_PSN` | 劳动人口 | DECIMAL |  |  |
| `SUP_PSN` | 供养人口 | DECIMAL |  |  |
| `FMLY_ANNL_INCM` | 家庭年收入 ( 万元 ) | DECIMAL |  |  |
| `VARS_ADMI_INCM` | 各项经营收入 ( 万元 ) | DECIMAL |  |  |
| `OTH_INCM` | 其他收入 ( 万元 ) | DECIMAL |  |  |
| `FMLY_ANNL_DISB` | 家庭年支出 ( 万元 ) | DECIMAL |  |  |
| `VARS_ADMI_FEE_DISB` | 各项经营成本、税费支出 ( 万元 ) | DECIMAL |  |  |
| `LIV_DISB` | 生活支出 ( 万元 ) | DECIMAL |  |  |
| `PROV_NO` | 省号 | VARCHAR | 是 |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `STARTDT` | 开始日期 | DATE | 是 |  |
| `ENDDT` | 结束日期 | DATE |  |  |
| `VALIDDT` | 有效日期 | DATE |  |  |
| `TIMESTAMP` | 时间戳 | DATETIME |  |  |

### `B_00DT_FAS_IDV_BUS_INFO_H`（FAS个体经营信息历史，27 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `SEQ_NO` | 序列号 | VARCHAR | 是 |  |
| `ID_CARD_NO` | 身份证号 | VARCHAR |  |  |
| `WON_HAVE_BULS` | 是否有营业执照 | VARCHAR |  |  |
| `UNIT_SOCL_CR_CD` | 统一社会信用代码 | VARCHAR |  |  |
| `ETRP_NAM` | 企业名称 | VARCHAR |  |  |
| `ETRP_REG_NO` | 企业注册号 | VARCHAR |  |  |
| `ORG_CODE` | 组织机构代码 | VARCHAR |  |  |
| `ADMI_RGE` | 经营范围 | VARCHAR |  |  |
| `CRT_DAT` | 成立日期 | VARCHAR |  |  |
| `ADMI_SCN_ADDR` | 经营场所地址 | VARCHAR |  |  |
| `PROP_OWNR` | 产权人 | VARCHAR |  |  |
| `FMLY_CAP_CNTRB_PPTN` | 家庭出资比例 | DECIMAL |  |  |
| `INV_ACQ_COST` | 存货购置成本/自制成本 | DECIMAL |  |  |
| `SAVE_STS` | 保存状态 | VARCHAR |  |  |
| `MACH_PURC_CFG_CST` | 机器设备购置成本 | DECIMAL |  |  |
| `PURC_CFG_TIME` | 购置时间 | VARCHAR |  |  |
| `ETRP_RENT_BULD_PPTN` | 企业租赁房屋建筑面积 | DECIMAL |  |  |
| `MKT_ANNL_RENT` | 市场年租金 | DECIMAL |  |  |
| `ALR_DISB_RENT_MATU_DAT` | 已支付租金的到期日 | VARCHAR |  |  |
| `ETRP_TOT_DPS` | 企业总负债 | DECIMAL |  |  |
| `ITGT_PMT` | 智能提示 | VARCHAR |  |  |
| `PROV_NO` | 省号 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `StartDt` | 开始日期 | DATE | 是 |  |
| `EndDt` | 结束日期 | DATE |  |  |
| `ValidDt` | 有效日期 | DATE |  |  |
| `Timestamp` | 时间戳 | DATETIME |  |  |

### `G_00PF_PEAS_LN_WHT_CHK_FLOW_INFO`（农户贷款白名单审查审批流程信息表，58 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FLOW_NO` | 流程编号 | VARCHAR | 是 |  |
| `SERNO` | 细项流水 | VARCHAR | 是 |  |
| `TYPE` | 细项类型 | VARCHAR | 是 |  |
| `WHT_NO` | 白名单编号 | VARCHAR |  |  |
| `FLOW_TYP` | 流程类型 | VARCHAR |  |  |
| `SPSR_CARD_NO` | 发起人员身份证号 | VARCHAR |  |  |
| `SPSR_ATCH_C4_ORG_NO` | 发起人员归属机构C4机构编码 | VARCHAR |  |  |
| `SPSR_ATCH_EIMO_ORG_NO` | 发起人员归属机构EIMO机构编码 | VARCHAR |  |  |
| `SPSR_OPR_TIME` | 发起人员操作时间 | VARCHAR |  |  |
| `SPSR_OPR_NAM` | 发起操作人名称 | VARCHAR |  |  |
| `SPSR_C4_ORG_NO` | 发起机构C4机构编码 | VARCHAR |  |  |
| `SPSR_EIMO_ORG_NO` | 发起机构EIMO机构编码 | VARCHAR |  |  |
| `SPSR_ORG_NAM` | 发起机构名称 | VARCHAR |  |  |
| `AUDT_CARD_NO` | 审核人员身份证号 | VARCHAR |  |  |
| `AUDT_ATCH_C4_ORG_NO` | 审核人员归属机构C4机构编码 | VARCHAR |  |  |
| `AUDT_ATCH_EIMO_ORG_NO` | 审核人员归属机构EIMO机构编码 | VARCHAR |  |  |
| `AUDT_OPR_TIME` | 审核人员操作时间 | VARCHAR |  |  |
| `AUDT_OPR_NAM` | 审核操作人名称 | VARCHAR |  |  |
| `AUDT_C4_ORG_NO` | 审核机构C4机构编码 | VARCHAR |  |  |
| `AUDT_EIMO_ORG_NO` | 审核机构EIMO机构编码 | VARCHAR |  |  |
| `AUDT_ORG_NAM` | 审核机构名称 | VARCHAR |  |  |
| `EXMN_CARD_NO` | 审查人员身份证号 | VARCHAR |  |  |
| `EXMN_ATCH_C4_ORG_NO` | 审查人员归属机构C4机构编码 | VARCHAR |  |  |
| `EXMN_ATCH_EIMO_ORG_NO` | 审查人员归属机构EIMO机构编码 | VARCHAR |  |  |
| `EXMN_OPR_TIME` | 审查人员操作时间 | VARCHAR |  |  |
| `EXMN_OPR_NAM` | 审查操作人名称 | VARCHAR |  |  |
| `EXMN_C4_ORG_NO` | 审查机构C4机构编码 | VARCHAR |  |  |
| `EXMN_EIMO_ORG_NO` | 审查机构EIMO机构编码 | VARCHAR |  |  |
| `EXMN_ORG_NAM` | 审查机构名称 | VARCHAR |  |  |
| `CTEN_APR_OPIN` | 审查意见 | VARCHAR |  |  |
| `EXMN_TIME` | 审查时间 | DECIMAL |  |  |
| `APR_CARD_NO` | 审批人员身份证号 | VARCHAR |  |  |
| `APR_ATCH_C4_ORG_NO` | 审批人员归属机构C4机构编码 | VARCHAR |  |  |
| `APR_ATCH_EIMO_ORG_NO` | 审批人员归属机构EIMO机构编码 | VARCHAR |  |  |
| `APR_OPR_TIME` | 审批人员操作时间 | VARCHAR |  |  |
| `APR_OPR_NAM` | 审批操作人名称 | VARCHAR |  |  |
| `APR_C4_ORG_NO` | 审批机构C4机构编码 | VARCHAR |  |  |
| `APR_EIMO_ORG_NO` | 审批机构EIMO机构编码 | VARCHAR |  |  |
| `APR_ORG_NAM` | 审批机构名称 | VARCHAR |  |  |
| `APR_OPIN` | 审批意见 | VARCHAR |  |  |
| `LN_CTRT_NO` | 合同编号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `CTRT_AMT` | 借款金额 | DECIMAL |  |  |
| `CTRT_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `USG_AMT` | 已用金额 | DECIMAL |  |  |
| `AVL_AMT` | 可用金额 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `PRVD_TRMN_DAT` | 发放终止日期 | VARCHAR |  |  |
| `SIGD_DAT` | 签约日期 | VARCHAR |  |  |
| `CTRT_STS_CD` | 合同状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_ORG_NO` | 经营机构编码 | VARCHAR |  |  |
| `DISB_ORG_NO_STD` | 经营机构编码_标准化 | VARCHAR |  |  |

### `B_00FT_PEAS_LN_DPSE_TASK_DTAL`（农户贷款属地贷后处置任务明细，42 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `DPSE_TASK_ID` | 处置任务ID | VARCHAR | 是 |  |
| `CENT_CHK_TASK_ID` | 集中检查任务ID | VARCHAR |  |  |
| `POST_LEND_CHK_TASK_ID` | 贷后检查任务ID | VARCHAR |  |  |
| `DPSE_SOR` | 处置来源 | VARCHAR |  |  |
| `DPSE_MOD` | 处置方式 | VARCHAR |  |  |
| `DPSE_SITU_DSC` | 处置情况详述 | VARCHAR |  |  |
| `CENT_CHK_RST` | 集中检查结论 | VARCHAR |  |  |
| `POST_LEND_CHK_RST` | 贷后检查结论 | VARCHAR |  |  |
| `WON_OVR_THRW_CENT_POST_CHK_RST` | 是否推翻集中贷后检查结论 | VARCHAR |  |  |
| `BUS_TYP` | 业务类型 | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `CTRT_BUS_BREED` | 合同业务品种 | VARCHAR |  |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CTRT_LN_AMT` | 合同借款金额 | DECIMAL |  |  |
| `CTRT_LN_DAT` | 合同借款日期 | VARCHAR |  |  |
| `CTRT_MATU_DAT` | 合同到期日期 | VARCHAR |  |  |
| `CTRT_RPAY_MOD` | 合同还款方式 | VARCHAR |  |  |
| `CTRT_GRTE` | 合同担保方式 | VARCHAR |  |  |
| `CTRT_WON_LOW_RSK` | 合同是否低风险 | VARCHAR |  |  |
| `VCH_VCH_NO` | 凭证编号 | VARCHAR |  |  |
| `VCH_LN_AMT` | 凭证借款金额 | DECIMAL |  |  |
| `VCH_VCH_BAL` | 凭证余额 | DECIMAL |  |  |
| `VCH_LN_DAT` | 凭证借款日期 | VARCHAR |  |  |
| `VCH_MATU_DAT` | 凭证到期日期 | VARCHAR |  |  |
| `VCH_BUS_PROC_CHANL` | 凭证业务办理渠道 | VARCHAR |  |  |
| `VCH_RSK_CLS` | 凭证风险分类 | VARCHAR |  |  |
| `VCH_AC_MDL` | 凭证授信模型 | VARCHAR |  |  |
| `CRT_TIME` | 创建时间 | VARCHAR |  |  |
| `CRT_PER_ORG_COD` | 创建者机构C4机构编码 | VARCHAR |  |  |
| `CRT_PER_EIMO_ORG_COD` | 创建者机构EIMO机构编码 | VARCHAR |  |  |
| `CRT_PER_ORG_NAM` | 创建者机构C4机构名称 | VARCHAR |  |  |
| `CRT_PER_CENTER_CITY` | 创建者所属城市 | VARCHAR |  |  |
| `CRT_DAT` | 创建日期 | VARCHAR |  |  |
| `BUS_STS` | 业务状态 | VARCHAR |  |  |
| `FLOW_TF_SER_NO` | 流转序号 | DECIMAL |  |  |
| `DPSE_CMPL_DAT` | 处置完成日期 | VARCHAR |  |  |
| `DPSE_CMPL_TIME` | 处置完成时间 | VARCHAR |  |  |
| `LNK_NAM` | 环节名称 | VARCHAR |  |  |
| `RGLR_BUS_NO` | 规则业务编号 | VARCHAR |  |  |
| `LMT_DUE_DATE` | 限办结时间 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |

### `B_00FT_PMC_P_DOORTASK_DTAL`（个人属地上门催收任务明细，140 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CLTN_TASK_NO` | 催收任务编号 | VARCHAR |  |  |
| `CLTN_FLOW_NO` | 催收流程编号 | VARCHAR |  |  |
| `ARG_NO` | 合约编号 | VARCHAR |  |  |
| `VCH_NO` | 凭证编号 | VARCHAR |  |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `LN_ARG_NOBOEING` | 贷款合约编号BOEING | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `CUST_NAM` | 客户名称 | VARCHAR |  |  |
| `CERT_TYP` | 证件类型 | VARCHAR |  |  |
| `CERT_NO` | 证件号码 | VARCHAR |  |  |
| `CUST_SEX` | 客户性别 | VARCHAR |  |  |
| `CUST_MP_NO` | 客户手机号 | VARCHAR |  |  |
| `CUST_PHO` | 客户固定电话 | VARCHAR |  |  |
| `PDT_CONTADDR` | 客户常用通讯地址 | VARCHAR |  |  |
| `CUST_UNIT_ADDR` | 客户单位地址 | VARCHAR |  |  |
| `CUST_LNG_RES` | 客户长期居住地址 | VARCHAR |  |  |
| `PRLN_TYP` | 个贷类型 | VARCHAR |  |  |
| `BUS_BREED` | 业务品种 | VARCHAR |  |  |
| `DISB_C4_ORG_CD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_EMIO_ORG_CD` | 放款机构EMIO机构编码 | VARCHAR |  |  |
| `DISB_ORG_NAM` | 放款机构名称 | VARCHAR |  |  |
| `OGU_CD` | 组织单元代码 | VARCHAR |  |  |
| `MNG_MAGR_ID` | 管户经理编码 | VARCHAR |  |  |
| `MNG_MAGR_NAM` | 管户经理名称 | VARCHAR |  |  |
| `MNG_C4_ORG_CD` | 管户机构C4机构编码 | VARCHAR |  |  |
| `MNG_EMIO_ORG_CD` | 管户机构EMIO机构编码 | VARCHAR |  |  |
| `MNG_ORG_NAM` | 管户机构名称 | VARCHAR |  |  |
| `DISB_ORG_ATCH_ROW_CD` | 放款机构所属行编码 | VARCHAR |  |  |
| `DISB_ORG_ATCH_NAM` | 放款机构所属行名称 | VARCHAR |  |  |
| `LN_DAT` | 贷款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `AADJ_MATU_DAT` | 调整后到期日期 | VARCHAR |  |  |
| `CCY` | 币种 | VARCHAR |  |  |
| `LN_AMT` | 贷款金额 | DECIMAL |  |  |
| `LN_BAL` | 贷款余额 | DECIMAL |  |  |
| `EXD_TMS` | 逾期期数 | INT |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_CAP` | 逾期本金 | DECIMAL |  |  |
| `EXD_INTS` | 逾期利息 | DECIMAL |  |  |
| `EXD_COM_INTS` | 逾期复利 | DECIMAL |  |  |
| `DEF_INTS` | 罚息 | DECIMAL |  |  |
| `TOT_ARREA` | 累计欠款 | DECIMAL |  |  |
| `PDT_RECOVERAMT` | 催回金额 | DECIMAL |  |  |
| `RSK_CLS` | 风险分类 | VARCHAR |  |  |
| `LAST_EXD_DAT` | 最近逾期日期 | VARCHAR |  |  |
| `PDT_EARLYODUE` | 最远逾期日期 | VARCHAR |  |  |
| `PDT_TASKDATE` | 入催日期 | VARCHAR |  |  |
| `PDT_TASKTIME` | 入催时间 | VARCHAR |  |  |
| `TASK_LOCT_ORG_NAM` | 任务所在机构名称 | VARCHAR |  |  |
| `TASK_LOCT_ORG_C4_ORG_CD` | 任务所在机构C4机构编码 | VARCHAR |  |  |
| `TASK_LOCT_ORG_EMIO_ORG_CD` | 任务所在机构EMIO机构编码 | VARCHAR |  |  |
| `TASK_PROC_PSN_CD` | 任务处理人员编码 | VARCHAR |  |  |
| `TASK_PROC_PSN_NAM` | 任务处理人员姓名 | VARCHAR |  |  |
| `CLTN_TASK_STS` | 催收任务状态 | VARCHAR |  |  |
| `PDT_NEXTWORK` | 下一步催收建议 | VARCHAR |  |  |
| `PDT_DEADDATE` | 限时办结日期 | VARCHAR |  |  |
| `GRTE` | 担保方式 | VARCHAR |  |  |
| `PENY_DIVY_IND` | 分派标志 | VARCHAR |  |  |
| `TASK_GNRT_TYP` | 任务生成方式 | VARCHAR |  |  |
| `TASK_CD` | 任务分发人编码 | VARCHAR |  |  |
| `TASK_NAM` | 任务分发人名称 | VARCHAR |  |  |
| `TASK_C4_ORG_ID` | 任务分发人所在机构C4机构编码 | VARCHAR |  |  |
| `TASK_EMIO_ORG_ID` | 任务分发人所在机构EMIO机构编码 | VARCHAR |  |  |
| `TASK_NAME` | 任务分发人所在机构名称 | VARCHAR |  |  |
| `PRVD_SPC` | 分发说明 | VARCHAR |  |  |
| `TASK_DATE` | 任务分发日期 | VARCHAR |  |  |
| `TASK_TIME` | 任务分发时间 | VARCHAR |  |  |
| `VALIDDT` | 有效日期 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CLTN_TASK_NO` | 催收任务编号 | VARCHAR |  |  |
| `CLTN_FLOW_NO` | 催收流程编号 | VARCHAR |  |  |
| `ARG_NO` | 合约编号 | VARCHAR |  |  |
| `VCH_NO` | 凭证编号 | VARCHAR |  |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `LN_ARG_NOBOEING` | 贷款合约编号BOEING | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `CUST_NAM` | 客户名称 | VARCHAR |  |  |
| `CERT_TYP` | 证件类型 | VARCHAR |  |  |
| `CERT_NO` | 证件号码 | VARCHAR |  |  |
| `CUST_SEX` | 客户性别 | VARCHAR |  |  |
| `CUST_MP_NO` | 客户手机号 | VARCHAR |  |  |
| `CUST_PHO` | 客户固定电话 | VARCHAR |  |  |
| `PDT_CONTADDR` | 客户常用通讯地址 | VARCHAR |  |  |
| `CUST_UNIT_ADDR` | 客户单位地址 | VARCHAR |  |  |
| `CUST_LNG_RES` | 客户长期居住地址 | VARCHAR |  |  |
| `PRLN_TYP` | 个贷类型 | VARCHAR |  |  |
| `BUS_BREED` | 业务品种 | VARCHAR |  |  |
| `DISB_C4_ORG_CD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_EMIO_ORG_CD` | 放款机构EMIO机构编码 | VARCHAR |  |  |
| `DISB_ORG_NAM` | 放款机构名称 | VARCHAR |  |  |
| `OGU_CD` | 组织单元代码 | VARCHAR |  |  |
| `MNG_MAGR_ID` | 管户经理编码 | VARCHAR |  |  |
| `MNG_MAGR_NAM` | 管户经理名称 | VARCHAR |  |  |
| `MNG_C4_ORG_CD` | 管户机构C4机构编码 | VARCHAR |  |  |
| `MNG_EMIO_ORG_CD` | 管户机构EMIO机构编码 | VARCHAR |  |  |
| `MNG_ORG_NAM` | 管户机构名称 | VARCHAR |  |  |
| `DISB_ORG_ATCH_ROW_CD` | 放款机构所属行编码 | VARCHAR |  |  |
| `DISB_ORG_ATCH_NAM` | 放款机构所属行名称 | VARCHAR |  |  |
| `LN_DAT` | 贷款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `AADJ_MATU_DAT` | 调整后到期日期 | VARCHAR |  |  |
| `CCY` | 币种 | VARCHAR |  |  |
| `LN_AMT` | 贷款金额 | DECIMAL |  |  |
| `LN_BAL` | 贷款余额 | DECIMAL |  |  |
| `EXD_TMS` | 逾期期数 | INT |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_CAP` | 逾期本金 | DECIMAL |  |  |
| `EXD_INTS` | 逾期利息 | DECIMAL |  |  |
| `EXD_COM_INTS` | 逾期复利 | DECIMAL |  |  |
| `DEF_INTS` | 罚息 | DECIMAL |  |  |
| `TOT_ARREA` | 累计欠款 | DECIMAL |  |  |
| `PDT_RECOVERAMT` | 催回金额 | DECIMAL |  |  |
| `RSK_CLS` | 风险分类 | VARCHAR |  |  |
| `LAST_EXD_DAT` | 最近逾期日期 | VARCHAR |  |  |
| `PDT_EARLYODUE` | 最远逾期日期 | VARCHAR |  |  |
| `PDT_TASKDATE` | 入催日期 | VARCHAR |  |  |
| `PDT_TASKTIME` | 入催时间 | VARCHAR |  |  |
| `TASK_LOCT_ORG_NAM` | 任务所在机构名称 | VARCHAR |  |  |
| `TASK_LOCT_ORG_C4_ORG_CD` | 任务所在机构C4机构编码 | VARCHAR |  |  |
| `TASK_LOCT_ORG_EMIO_ORG_CD` | 任务所在机构EMIO机构编码 | VARCHAR |  |  |
| `TASK_PROC_PSN_CD` | 任务处理人员编码 | VARCHAR |  |  |
| `TASK_PROC_PSN_NAM` | 任务处理人员姓名 | VARCHAR |  |  |
| `CLTN_TASK_STS` | 催收任务状态 | VARCHAR |  |  |
| `PDT_NEXTWORK` | 下一步催收建议 | VARCHAR |  |  |
| `PDT_DEADDATE` | 限时办结日期 | VARCHAR |  |  |
| `GRTE` | 担保方式 | VARCHAR |  |  |
| `PENY_DIVY_IND` | 分派标志 | VARCHAR |  |  |
| `TASK_GNRT_TYP` | 任务生成方式 | VARCHAR |  |  |
| `TASK_CD` | 任务分发人编码 | VARCHAR |  |  |
| `TASK_NAM` | 任务分发人名称 | VARCHAR |  |  |
| `TASK_C4_ORG_ID` | 任务分发人所在机构C4机构编码 | VARCHAR |  |  |
| `TASK_EMIO_ORG_ID` | 任务分发人所在机构EMIO机构编码 | VARCHAR |  |  |
| `TASK_NAME` | 任务分发人所在机构名称 | VARCHAR |  |  |
| `PRVD_SPC` | 分发说明 | VARCHAR |  |  |
| `TASK_DATE` | 任务分发日期 | VARCHAR |  |  |
| `TASK_TIME` | 任务分发时间 | VARCHAR |  |  |
| `VALIDDT` | 有效日期 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |

### `S_00PF_PEAS_MGR_LN_RISK_C4`（农户贷款客户经理办贷风险特征表(C4机构树)，39 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CUST_ID_NO` | 客户经理身份证号 | VARCHAR | 是 |  |
| `BLG_C4_ORG_CD` | 客户经理归属机构C4机构编码 | VARCHAR |  |  |
| `BLG_EIMO_ORG_CD` | 客户经理归属机构EIMO机构编码 | VARCHAR |  |  |
| `HDL_PEAS_LN_YRS` | 客户经理办理农户贷款年限 | VARCHAR |  |  |
| `CUR_IND_PEAS_LN` | 客户经理当前是否还在办理农户贷款 | VARCHAR |  |  |
| `TOT_CNT_PEAS_LN` | 客户经理累计办理农户贷款合同数 | INT |  |  |
| `TOT_CNT_UNM_PEAS_LN` | 客户经理累计办理非婚客户农户贷款合同数 | INT |  |  |
| `TOT_CUST_PEAS_LN` | 客户经理累计办理农户贷款客户数 | INT |  |  |
| `TOT_CUST_UNM_PEAS_LN` | 客户经理累计办理非婚客户农户贷款客户数 | INT |  |  |
| `TOT_LMT_PEAS_LN` | 客户经理累计办理农户贷款授信额度 | DECIMAL |  |  |
| `TOT_LMT_UNM_PEAS_LN` | 客户经理累计办理非婚客户农户贷款授信额度 | DECIMAL |  |  |
| `CUR_CNT_PEAS_LN` | 客户经理已办理农户贷款当前有贷合同数 | INT |  |  |
| `CUR_CNT_UNM_PEAS_LN` | 客户经理累计办理非婚客户农户贷款当前有贷合同数 | INT |  |  |
| `CUR_CUST_PEAS_LN` | 客户经理已办理农户贷款当前有贷客户数 | INT |  |  |
| `CUR_CUST_UNM_PEAS_LN` | 客户经理已办理非婚客户农户贷款当前有贷客户数 | INT |  |  |
| `CUR_BAL_PEAS_LN` | 客户经理已办理农户贷款当前余额 | DECIMAL |  |  |
| `CUR_BAL_UNM_PEAS_LN` | 客户经理已办理非婚客户农户贷款当前余额 | DECIMAL |  |  |
| `CUR_CNT_NPL_PEAS` | 客户经理已办理农户贷款当前不良合同数 | INT |  |  |
| `CUR_CNT_NPL_UNM` | 客户经理已办理非婚客户农户贷款当前不良合同数 | INT |  |  |
| `CUR_CUST_NPL_PEAS` | 客户经理已办理农户贷款当前不良客户数 | INT |  |  |
| `CUR_CUST_NPL_UNM` | 客户经理已办理非婚客户农户贷款当前不良客户数 | INT |  |  |
| `CUR_BAL_NPL_PEAS` | 客户经理已办理农户贷款当前不良余额 | DECIMAL |  |  |
| `CUR_BAL_NPL_UNM` | 客户经理已办理非婚客户农户贷款当前不良余额 | DECIMAL |  |  |
| `CUR_RAT_NPL_PEAS` | 客户经理已办理农户贷款当前不良率 | DECIMAL |  |  |
| `CUR_RAT_NPL_UNM` | 客户经理已办理非婚客户农户贷款当前不良率 | DECIMAL |  |  |
| `ADJ_RAT_NPL_CAN_CUR` | 客户经理已办理农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ADJ_RAT_NPL_CAN_UNM` | 客户经理已办理非婚客户农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ADJ_RAT_NPL_CAN_4YR` | 客户经理已办理农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `ADJ_RAT_NPL_CAN_U4Y` | 客户经理已办理非婚客户农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `GEN_RAT_NPL_CAN_CUR` | 客户经理已办理农户贷款当年不良生成率 | DECIMAL |  |  |
| `GEN_RAT_NPL_EXC_COL` | 客户经理已办理农户贷款当年剔除清收后不良生成率 | DECIMAL |  |  |
| `GEN_RAT_NPL_12M_RT` | 客户经理已办理农户贷款近12个月不良生成率 | DECIMAL |  |  |
| `GEN_RAT_NPL_EXC_12M` | 客户经理已办理农户贷款近12个月剔除清收后不良生成率 | DECIMAL |  |  |
| `CUR_BAL_OD_PEAS` | 客户经理已办理农户贷款当前逾期余额 | DECIMAL |  |  |
| `CUR_RAT_OD_PEAS` | 客户经理已办理农户贷款当前逾期率 | DECIMAL |  |  |
| `MAX_YEA_NPL_CON_PEA` | 客户经理已办理农户贷款不良发生最多的合同签约年份 | VARCHAR |  |  |
| `FND_CLU_CNT_PEAS` | 客户经理已办理农户贷款触发与客户资金往来模型累计线索量 | INT |  |  |
| `SAME_DAT_CUST_CNT` | 客户经理当年建立数据雷同的客户档案数 | INT |  |  |

### `S_00PF_PEAS_DIVR_RSK_C4`（农户贷款零散获客风险机构级分析表(C4机构树)，35 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `RGN_NUM` | 辖内有农户贷款行政村数 | INT |  |  |
| `RGN_BLO_5_NUM` | 辖内有5户及以下农户贷款行政村数 | INT |  |  |
| `RGN_BLO_5_RATE` | 辖内5户及以下农户贷款行政村占比 | DECIMAL |  |  |
| `CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `DIVR_CTRT_NUM` | 辖内零散获客农户贷款合同数 | INT |  |  |
| `DIVR_CTRT_RATE` | 辖内零散获客农户贷款合同占比 | DECIMAL |  |  |
| `CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `DIVR_CUST_NUM` | 辖内零散获客农户贷款客户数 | INT |  |  |
| `DIVR_CUST_RATE` | 辖内零散获客农户贷款客户占比 | DECIMAL |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `DIVR_LN_BAL` | 辖内零散获客农户贷款余额 | DECIMAL |  |  |
| `DIVR_LN_BAL_RATE` | 辖内零散获客农户贷款余额占比 | DECIMAL |  |  |
| `UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `DIVR_UHLTH_CTRT_NUM` | 辖内零散获客农户贷款不良合同数 | INT |  |  |
| `DIVR_UHLTH_CTRT_RATE` | 辖内零散获客农户贷款不良合同占比 | DECIMAL |  |  |
| `UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `DIVR_UHLTH_CUST_NUM` | 辖内零散获客农户贷款不良客户数 | INT |  |  |
| `DIVR_UHLTH_CUST_RATE` | 辖内零散获客农户贷款不良客户占比 | DECIMAL |  |  |
| `UHLTH_LN_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `DIVR_UHLTH_LN_BAL` | 辖内零散获客农户贷款不良余额 | DECIMAL |  |  |
| `DIVR_UHLTH_LN_BAL_RATE` | 辖内零散获客农户贷款不良余额占比 | DECIMAL |  |  |
| `UHLTH_LN_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `DIVR_UHLTH_LN_RATE` | 辖内零散获客农户贷款不良率 | DECIMAL |  |  |
| `CAN_UP_UHLTH_RATE_YEAR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `DIVR_CAN_UP_UHLTH_RATE_YEAR` | 辖内零散获客农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `CAN_UP_UHLTH_RATE_LST_4Y` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `DIVR_CAN_UP_UHLTH_RATE_LST_4Y` | 辖内零散获客农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_NMGG_RLSE_RSK_ORG_C4`（农户贷款无抵押缓释风险机构级分析表(C4机构树)，35 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EMIO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `GRTE_TYP` | 担保方式 ( 自定义 ) | VARCHAR | 是 |  |
| `ALL_CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `GRTE_CTRT_NUM` | 辖内此类担保方式农户贷款合同数 | INT |  |  |
| `GRTE_CTRT_PPTN` | 辖内此类担保方式农户贷款合同占比 | DECIMAL |  |  |
| `ALL_CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `GRTE_CUST_NUM` | 辖内此类担保方式农户贷款客户数 | INT |  |  |
| `GRTE_CUST_PPTN` | 辖内此类担保方式农户贷款客户占比 | DECIMAL |  |  |
| `ALL_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `GRTE_BAL` | 辖内此类担保方式农户贷款余额 | DECIMAL |  |  |
| `GRTE_BAL_PPTN` | 辖内此类担保方式农户贷款余额占比 | DECIMAL |  |  |
| `ALL_UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `GRTE_UHLTH_CTRT_NUM` | 辖内此类担保方式农户贷款不良合同数 | INT |  |  |
| `GRTE_UHLTH_CTRT_PPTN` | 辖内此类担保方式农户贷款不良合同占比 | DECIMAL |  |  |
| `ALL_UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `GRTE_UHLTH_CUST_NUM` | 辖内此类担保方式农户贷款不良客户数 | INT |  |  |
| `GRTE_UHLTH_CUST_PPTN` | 辖内此类担保方式农户贷款不良客户占比 | DECIMAL |  |  |
| `ALL_UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `GRTE_UHLTH_BAL` | 辖内此类担保方式农户贷款不良余额 | DECIMAL |  |  |
| `GRTE_UHLTH_BAL_PPTN` | 辖内此类担保方式农户贷款不良余额占比 | DECIMAL |  |  |
| `ALL_UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `GRTE_UHLTH_RATE` | 辖内此类担保方式农户贷款不良率 | DECIMAL |  |  |
| `ALL_REST_CAN_UHLTH_RATE_YEAR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `GRTE_REST_CAN_UHLTH_RATE_YEAR` | 辖内此类担保方式农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ALL_REST_CAN_UHLTH_RATE_LST_4_YEAR` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `GRTE_REST_CAN_UHLTH_RATE_LST_4_YEAR` | 辖内此类担保方式农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `ALL_ANNL_UHLTH_GNRT_RATE_YEAR` | 辖内全部农户贷款当年年化不良生成率 | DECIMAL |  |  |
| `GRTE_ANNL_UHLTH_GNRT_RATE_YEAR` | 辖内此类担保方式农户贷款当年年化不良生成率 | DECIMAL |  |  |

### `S_00PF_PEAS_ACARD_SCRE_RSK_ORG_C4`（农户贷款A卡评分行为风险机构级分析表(C4机构树)，38 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `ACARD_SCRE_ACTN_RSK_TYP` | A卡评分行为风险类型 | VARCHAR | 是 |  |
| `ALL_ACARD_SCRE_AVER_VLU` | 辖内全部农户贷款A卡评分均值 | DECIMAL |  |  |
| `ALL_CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `RSK_CTRT_NUM` | 辖内此类风险类型农户贷款合同数 | INT |  |  |
| `RSK_CTRT_PPTN` | 辖内此类风险类型农户贷款合同占比 | DECIMAL |  |  |
| `ALL_CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `RSK_CUST_NUM` | 辖内此类风险类型农户贷款客户数 | INT |  |  |
| `RSK_CUST_PPTN` | 辖内此类风险类型农户贷款客户占比 | DECIMAL |  |  |
| `ALL_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `RSK_BAL` | 辖内此类风险类型农户贷款余额 | DECIMAL |  |  |
| `RSK_BAL_PPTN` | 辖内此类风险类型农户贷款余额占比 | DECIMAL |  |  |
| `RSK_CR_BAL` | 辖内此类风险类型信用类农户贷款余额 | DECIMAL |  |  |
| `RSK_CR_BAL_PPTN` | 辖内此类风险类型信用类农户贷款余额占比 | DECIMAL |  |  |
| `ALL_UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_NUM` | 辖内此类风险类型农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_PPTN` | 辖内此类风险类型农户贷款不良合同占比 | DECIMAL |  |  |
| `ALL_UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_NUM` | 辖内此类风险类型农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_PPTN` | 辖内此类风险类型农户贷款不良客户占比 | DECIMAL |  |  |
| `ALL_UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_BAL` | 辖内此类风险类型农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_BAL_PPTN` | 辖内此类风险类型农户贷款不良余额占比 | DECIMAL |  |  |
| `ALL_UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `RSK_UHLTH_RATE` | 辖内此类风险类型农户贷款不良率 | DECIMAL |  |  |
| `ALL_REST_CAN_UHLTH_RATE_YEAR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `RSK_REST_CAN_UHLTH_RATE_YEAR` | 辖内此类风险类型农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ALL_REST_CAN_UHLTH_RATE_LST_4_YEAR` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `RSK_REST_CAN_UHLTH_RATE_LST_4_YEAR` | 辖内此类风险类型农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `ALL_CTRT_AVER_AC_QUOT_LST_4_YEAR` | 辖内全部农户贷款近4个自然年合同平均授信额度 | DECIMAL |  |  |
| `RSK_CTRT_AVER_AC_QUOT_LST_4_YEAR` | 辖内此类风险类型农户贷款近4个自然年合同平均授信额度 | DECIMAL |  |  |

### `S_00PF_PEAS_LN_ARC_QLT_RSK_ORG_ANL_C4`（农户贷款建档质量风险机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR |  |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `ARC_QLT_RSK_TYP` | 建档质量风险类型 | VARCHAR | 是 |  |
| `TTL_CNT_PEAS_LN` | 辖内全部农户贷款合同数 | INT |  |  |
| `TRS_CNT_PEAS_LN` | 辖内此类风险类型农户贷款合同数 | INT |  |  |
| `TRS_RAT_CNT_PEAS` | 辖内此类风险类型农户贷款合同占比 | DECIMAL |  |  |
| `TTL_CUST_PEAS_LN` | 辖内全部农户贷款客户数 | INT |  |  |
| `TRS_CUST_PEAS_LN` | 辖内此类风险类型农户贷款客户数 | INT |  |  |
| `TRS_RAT_CUST_PEA` | 辖内此类风险类型农户贷款客户占比 | DECIMAL |  |  |
| `TTL_BAL_PEAS_LN` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `TRS_BAL_PEAS_LN` | 辖内此类风险类型农户贷款余额 | DECIMAL |  |  |
| `TRS_RAT_BAL_PEAS` | 辖内此类风险类型农户贷款余额占比 | DECIMAL |  |  |
| `TTL_CNT_NPL_PEAS` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `TRS_CNT_NPL_PEAS` | 辖内此类风险类型农户贷款不良合同数 | INT |  |  |
| `TRS_RAT_NPL_CNT` | 辖内此类风险类型农户贷款不良合同占比 | DECIMAL |  |  |
| `TTL_CUST_NPL_PEA` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `TRS_CUST_NPL_PEA` | 辖内此类风险类型农户贷款不良客户数 | INT |  |  |
| `TRS_RAT_NPL_CST` | 辖内此类风险类型农户贷款不良客户占比 | DECIMAL |  |  |
| `TTL_BAL_NPL_PEAS` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `TRS_BAL_NPL_PEAS` | 辖内此类风险类型农户贷款不良余额 | DECIMAL |  |  |
| `TRS_RAT_NPL_BAL` | 辖内此类风险类型农户贷款不良余额占比 | DECIMAL |  |  |
| `TTL_RAT_NPL_PEAS` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `TRS_RAT_NPL_PEAS` | 辖内此类风险类型农户贷款不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_CAN_CUR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `TRS_ADJ_RAT_CAN_CUR` | 辖内此类风险类型农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_NPL_CAN` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `TRS_ADJ_RAT_NPL_CAN` | 辖内此类风险类型农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_OVER_FL_AC_RSK_C4`（农户贷款超额授信风险机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `OVER_FL_AC_RSK_TYP` | 超额授信风险类型 | VARCHAR | 是 |  |
| `CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `RSK_CTRT_NUM` | 辖内此类风险类型农户贷款合同数 | INT |  |  |
| `RSK_CTRT_PPTN` | 辖内此类风险类型农户贷款合同数占比 | DECIMAL |  |  |
| `CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `RSK_CUST_NUM` | 辖内此类风险类型农户贷款客户数 | INT |  |  |
| `RSK_CUST_PPTN` | 辖内此类风险类型农户贷款客户数占比 | DECIMAL |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `RSK_LN_BAL` | 辖内此类风险类型农户贷款余额 | DECIMAL |  |  |
| `RSK_LN_BAL_PPTN` | 辖内此类风险类型农户贷款余额占比 | DECIMAL |  |  |
| `UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_NUM` | 辖内此类风险类型农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_PPTN` | 辖内此类风险类型农户贷款不良合同占比 | DECIMAL |  |  |
| `UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_NUM` | 辖内此类风险类型农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_PPTN` | 辖内此类风险类型农户贷款不良客户占比 | DECIMAL |  |  |
| `UHLTH_LN_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_LN_BAL` | 辖内此类风险类型农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_LN_BAL_PPTN` | 辖内此类风险类型农户贷款不良余额占比 | DECIMAL |  |  |
| `UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `RSK_UHLTH_RATE` | 辖内此类风险类型农户贷款不良率 | DECIMAL |  |  |
| `UP_UHLTH_RATE_1Y` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `RSK_UP_UHLTH_RATE_1Y` | 辖内此类风险类型农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `UP_UHLTH_RATE_4Y` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `RSK_UP_UHLTH_RATE_4Y` | 辖内此类风险类型农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_LN_LRG_CR_ORG_ANL_C4`（农户贷款大额信用风险机构级分析表(C4机构树)，32 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `TTL_CNT_PEAS_LN` | 辖内全部农户贷款合同数 | INT |  |  |
| `LRG_CNT_PEAS_LN` | 辖内大额农户贷款合同数 | INT |  |  |
| `LRG_RAT_CNT_PEAS` | 辖内大额农户贷款合同数占比 | DECIMAL |  |  |
| `TTL_CUST_PEAS_LN` | 辖内全部农户贷款客户数 | INT |  |  |
| `LRG_CUST_PEAS_LN` | 辖内大额农户贷款客户数 | INT |  |  |
| `LRG_RAT_CUST_PEA` | 辖内大额农户贷款客户数占比 | DECIMAL |  |  |
| `TTL_BAL_PEAS_LN` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `LRG_BAL_PEAS_LN` | 辖内大额农户贷款余额 | DECIMAL |  |  |
| `LRG_RAT_BAL_PEAS` | 辖内大额农户贷款余额占比 | DECIMAL |  |  |
| `TTL_CNT_NPL_PEAS` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `LRG_CNT_NPL_PEAS` | 辖内大额农户贷款不良合同数 | INT |  |  |
| `LRG_RAT_NPL_CNT` | 辖内大额农户贷款不良合同占比 | DECIMAL |  |  |
| `TTL_CUST_NPL_PEA` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `LRG_CUST_NPL_PEA` | 辖内大额农户贷款不良客户数 | INT |  |  |
| `LRG_RAT_NPL_CST` | 辖内大额农户贷款不良客户占比 | DECIMAL |  |  |
| `TTL_BAL_NPL_PEAS` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `LRG_BAL_NPL_PEAS` | 辖内大额农户贷款不良余额 | DECIMAL |  |  |
| `LRG_RAT_NPL_BAL` | 辖内大额农户贷款不良余额占比 | DECIMAL |  |  |
| `TTL_RAT_NPL_PEAS` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `LRG_RAT_NPL_PEAS` | 辖内大额农户贷款不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_CAN_CUR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `LRG_ADJ_RAT_CAN_CUR` | 辖内大额农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_NPL_CAN` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `LRG_ADJ_RAT_NPL_CAN` | 辖内大额农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_LN_BIZ_TYP_ORG_ANL_C4`（农户贷款业务品种机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `PEAS_LN_C4_BIZ` | 农户贷款C4业务品种 | VARCHAR | 是 |  |
| `TTL_CNT_PEAS_LN` | 辖内全部农户贷款合同数 | INT |  |  |
| `BIZ_CNT_PEAS_LN` | 辖内此类业务品种农户贷款合同数 | INT |  |  |
| `BIZ_RAT_CNT_PEAS` | 辖内此类业务品种农户贷款合同数占比 | DECIMAL |  |  |
| `TTL_CUST_PEAS_LN` | 辖内全部农户贷款客户数 | INT |  |  |
| `BIZ_CUST_PEAS_LN` | 辖内此类业务品种农户贷款客户数 | INT |  |  |
| `BIZ_RAT_CUST_PEA` | 辖内此类业务品种农户贷款客户数占比 | DECIMAL |  |  |
| `TTL_BAL_PEAS_LN` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `BIZ_BAL_PEAS_LN` | 辖内此类业务品种农户贷款余额 | DECIMAL |  |  |
| `BIZ_RAT_BAL_PEAS` | 辖内此类业务品种农户贷款余额占比 | DECIMAL |  |  |
| `TTL_CNT_NPL_PEAS` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `BIZ_CNT_NPL_PEAS` | 辖内此类业务品种农户贷款不良合同数 | INT |  |  |
| `BIZ_RAT_NPL_CNT` | 辖内此类业务品种农户贷款不良合同占比 | DECIMAL |  |  |
| `TTL_CUST_NPL_PEA` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `BIZ_CUST_NPL_PEA` | 辖内此类业务品种农户贷款不良客户数 | INT |  |  |
| `BIZ_RAT_NPL_CST` | 辖内此类业务品种农户贷款不良客户占比 | DECIMAL |  |  |
| `TTL_BAL_NPL_PEAS` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `BIZ_BAL_NPL_PEAS` | 辖内此类业务品种农户贷款不良余额 | DECIMAL |  |  |
| `BIZ_RAT_NPL_BAL` | 辖内此类业务品种农户贷款不良余额占比 | DECIMAL |  |  |
| `TTL_RAT_NPL_PEAS` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `BIZ_RAT_NPL_PEAS` | 辖内此类业务品种农户贷款不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_CAN_CUR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `BIZ_ADJ_RAT_CAN_CUR` | 辖内此类业务品种农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_NPL_CAN` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `BIZ_ADJ_RAT_NPL_CAN` | 辖内此类业务品种农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_OCPRSK_ORG_C4`（农户贷款行业风险机构级分析表(C4机构树)，47 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAME` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `KEY_OCP_COD` | 重点行业分类代码 | VARCHAR | 是 |  |
| `KEY_OCP_NAME` | 重点行业分类名称 | VARCHAR |  |  |
| `CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `KEY_OCP_CTRT_NUM` | 辖内重点行业农户贷款合同数 | INT |  |  |
| `KEY_OCP_CTRT_PPTN` | 辖内重点行业农户贷款合同占比 | DECIMAL |  |  |
| `CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `KEY_OCP_CUST_NUM` | 辖内重点行业农户贷款客户数 | INT |  |  |
| `KEY_OCP_CUST_PPTN` | 辖内重点行业农户贷款客户占比 | DECIMAL |  |  |
| `BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `KEY_OCP_BAL` | 辖内重点行业农户贷款余额 | DECIMAL |  |  |
| `KEY_OCP_BAL_PPTN` | 辖内重点行业农户贷款余额占比 | DECIMAL |  |  |
| `CR_BAL` | 辖内全部信用类农户贷款余额 | DECIMAL |  |  |
| `KEY_OCP_CR_BAL` | 辖内重点行业信用类农户贷款余额 | DECIMAL |  |  |
| `KEY_OCP_CR_BAL_PPTN` | 辖内重点行业信用类农户贷款余额占比 | DECIMAL |  |  |
| `UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `KEY_OCP_UHLTH_CTRT_NUM` | 辖内重点行业农户贷款不良合同数 | INT |  |  |
| `KEY_OCP_UHLTH_CTRT_PPTN` | 辖内重点行业农户贷款不良合同占比 | DECIMAL |  |  |
| `UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `KEY_OCP_UHLTH_CUST_NUM` | 辖内重点行业农户贷款不良客户数 | INT |  |  |
| `KEY_OCP_UHLTH_CUST_PPTN` | 辖内重点行业农户贷款不良客户占比 | DECIMAL |  |  |
| `UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `KEY_OCP_UHLTH_BAL` | 辖内重点行业农户贷款不良余额 | DECIMAL |  |  |
| `KEY_OCP_UHLTH_BAL_PPTN` | 辖内重点行业农户贷款不良余额占比 | DECIMAL |  |  |
| `UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `KEY_OCP_UHLTH_RATE` | 辖内重点行业农户贷款不良率 | DECIMAL |  |  |
| `REST_YEAR_CAN_UHLTH_RATE` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `KEY_OCP_REST_YEAR_CAN_UHLTH_RATE` | 辖内重点行业农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `REST_L4YEAR_CAN_UHLTH_RATE` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `KEY_OCP_REST_L4YEAR_CAN_UHLTH_RATE` | 辖内重点行业农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `YEAR_UHLTH_CRT_RATE` | 辖内全部农户贷款当年年化不良生成率 | DECIMAL |  |  |
| `KEY_OCP_YEAR_UHLTH_CRT_RATE` | 辖内重点行业农户贷款当年年化不良生成率 | DECIMAL |  |  |
| `CLR_LQDT_YEAR_UHLTH_CRT_RATE` | 辖内全部农户贷款当年剔除清收后年化不良生成率 | DECIMAL |  |  |
| `KEY_OCP_CLR_LQDT_YEAR_UHLTH_CRT_RATE` | 辖内重点行业农户贷款当年剔除清收后年化不良生成率 | DECIMAL |  |  |
| `L12MTH_UHLTH_CRT_RATE` | 辖内全部农户贷款近12个月不良生成率 | DECIMAL |  |  |
| `KEY_OCP_L12MTH_UHLTH_CRT_RATE` | 辖内重点行业农户贷款近12个月不良生成率 | DECIMAL |  |  |
| `L12MTH_CLR_LQDT_UHLTH_CRT_RATE` | 辖内全部农户贷款近12个月剔除清收后不良生成率 | DECIMAL |  |  |
| `KEY_OCP_L12MTH_CLR_LQDT_UHLTH_CRT_RATE` | 辖内重点行业农户贷款近12个月剔除清收后不良生成率 | DECIMAL |  |  |
| `L4YEAR_CTRT_AVER_AC_QUOT` | 辖内全部农户贷款近4个自然年合同平均授信额度 | DECIMAL |  |  |
| `KEY_OCP_L4YEAR_CTRT_AVER_AC_QUOT` | 辖内重点行业农户贷款近4个自然年合同平均授信额度 | DECIMAL |  |  |

### `S_00PF_PEAS_LN_RSK_ORG_C4`（农户贷款风险线索处置质量机构级分析表(C4机构树)，48 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EMIO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `RSK_LINE_TYP` | 风险线索类型 | VARCHAR | 是 |  |
| `LN_CTRT_CNT` | 辖内全部农户贷款合同数 | INT |  |  |
| `PEAS_LN_CTRT_CNT` | 辖内触发此类风险线索农户贷款合同数 | INT |  |  |
| `PEAS_LN_CTRT_PPTN` | 辖内触发此类风险线索农户贷款合同占比 | DECIMAL |  |  |
| `NO_LN_CTRT_CNT` | 辖内此类风险线索核查不属实农户贷款合同数 | INT |  |  |
| `NO_LN_CTRT_PPTN` | 辖内此类风险线索核查不属实农户贷款合同占比 | DECIMAL |  |  |
| `LN_CNT` | 辖内全部农户贷款客户数 | INT |  |  |
| `PEAS_LN_CNT` | 辖内触发此类风险线索农户贷款客户数 | INT |  |  |
| `PEAS_LN_CUST_PPTN` | 辖内触发此类风险线索农户贷款客户占比 | DECIMAL |  |  |
| `NO_LN_CNT` | 辖内此类风险线索核查不属实农户贷款客户数 | INT |  |  |
| `NO_LN_CUST_PPTN` | 辖内此类风险线索核查不属实农户贷款客户占比 | DECIMAL |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `PEAS_LN_BAL` | 辖内触发此类风险线索农户贷款余额 | DECIMAL |  |  |
| `PEAS_LN_BAL_PPTN` | 辖内触发此类风险线索农户贷款余额占比 | DECIMAL |  |  |
| `NO_LN_BAL` | 辖内此类风险线索核查不属实农户贷款余额 | DECIMAL |  |  |
| `NO_LN_BAL_PPTN` | 辖内此类风险线索核查不属实农户贷款余额占比 | DECIMAL |  |  |
| `LN_UHLTH_CTRT_CNT` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `PEAS_LN_UHLTH_CTRT_CNT` | 辖内触发此类风险线索农户贷款不良合同数 | INT |  |  |
| `PEAS_LN_UHLTH_CTRT_PPTN` | 辖内触发此类风险线索农户贷款不良合同占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_CTRT_CNT` | 辖内此类风险线索核查不属实农户贷款不良合同数 | INT |  |  |
| `NO_LN_UHLTH_CTRT_PPTN` | 辖内此类风险线索核查不属实农户贷款不良合同占比 | DECIMAL |  |  |
| `LN_UHLTH_CNT` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `PEAS_LN_UHLTH_CUST_CNT` | 辖内触发此类风险线索农户贷款不良客户数 | INT |  |  |
| `PEAS_LN_UHLTH_CUST_PPTN` | 辖内触发此类风险线索农户贷款不良客户占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_CNT` | 辖内此类风险线索核查不属实农户贷款不良客户数 | INT |  |  |
| `NO_LN_UHLTH_CUST_PPTN` | 辖内此类风险线索核查不属实农户贷款不良客户占比 | DECIMAL |  |  |
| `LN_UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_BAL` | 辖内触发此类风险线索农户贷款不良余额 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_BAL_PPTN` | 辖内触发此类风险线索农户贷款不良余额占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_BAL` | 辖内此类风险线索核查不属实农户贷款不良余额 | DECIMAL |  |  |
| `NO_LN_UHLTH_BAL_PPTN` | 辖内此类风险线索核查不属实农户贷款不良余额占比 | DECIMAL |  |  |
| `LN_UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_RATE` | 辖内触发此类风险线索农户贷款不良率 | DECIMAL |  |  |
| `NO_LN_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款不良率 | DECIMAL |  |  |
| `YEAR_CAN_POST_UHLTH_RATE` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `Y_CAN_POST_UHLTH_RATE` | 辖内触发此类风险线索农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `NO_YEAR_CAN_POST_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ALL_4YEAR_CAN_POST_UHLTH_RATE` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `Y4_CAN_POST_UHLTH_RATE` | 辖内触发此类风险线索农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `NO_4YEAR_CAN_POST_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_LN_CCE_RSK_PSE_ORG_C4`（农户贷款重点关注风险线索处置质量机构级分析表(C4机构树)，48 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EMIO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `RSK_LINE_TYP` | 风险线索类型 | VARCHAR | 是 |  |
| `LN_CTRT_CNT` | 辖内全部农户贷款合同数 | INT |  |  |
| `PEAS_LN_CTRT_CNT` | 辖内触发此类风险线索农户贷款合同数 | INT |  |  |
| `PEAS_LN_CTRT_PPTN` | 辖内触发此类风险线索农户贷款合同占比 | DECIMAL |  |  |
| `NO_LN_CTRT_CNT` | 辖内此类风险线索核查不属实农户贷款合同数 | INT |  |  |
| `NO_LN_CTRT_PPTN` | 辖内此类风险线索核查不属实农户贷款合同占比 | DECIMAL |  |  |
| `LN_CNT` | 辖内全部农户贷款客户数 | INT |  |  |
| `PEAS_LN_CNT` | 辖内触发此类风险线索农户贷款客户数 | INT |  |  |
| `PEAS_LN_CUST_PPTN` | 辖内触发此类风险线索农户贷款客户占比 | DECIMAL |  |  |
| `NO_LN_CNT` | 辖内此类风险线索核查不属实农户贷款客户数 | INT |  |  |
| `NO_LN_CUST_PPTN` | 辖内此类风险线索核查不属实农户贷款客户占比 | DECIMAL |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `PEAS_LN_BAL` | 辖内触发此类风险线索农户贷款余额 | DECIMAL |  |  |
| `PEAS_LN_BAL_PPTN` | 辖内触发此类风险线索农户贷款余额占比 | DECIMAL |  |  |
| `NO_LN_BAL` | 辖内此类风险线索核查不属实农户贷款余额 | DECIMAL |  |  |
| `NO_LN_BAL_PPTN` | 辖内此类风险线索核查不属实农户贷款余额占比 | DECIMAL |  |  |
| `LN_UHLTH_CTRT_CNT` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `PEAS_LN_UHLTH_CTRT_CNT` | 辖内触发此类风险线索农户贷款不良合同数 | INT |  |  |
| `PEAS_LN_UHLTH_CTRT_PPTN` | 辖内触发此类风险线索农户贷款不良合同占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_CTRT_CNT` | 辖内此类风险线索核查不属实农户贷款不良合同数 | INT |  |  |
| `NO_LN_UHLTH_CTRT_PPTN` | 辖内此类风险线索核查不属实农户贷款不良合同占比 | DECIMAL |  |  |
| `LN_UHLTH_CNT` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `PEAS_LN_UHLTH_CUST_CNT` | 辖内触发此类风险线索农户贷款不良客户数 | INT |  |  |
| `PEAS_LN_UHLTH_CUST_PPTN` | 辖内触发此类风险线索农户贷款不良客户占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_CNT` | 辖内此类风险线索核查不属实农户贷款不良客户数 | INT |  |  |
| `NO_LN_UHLTH_CUST_PPTN` | 辖内此类风险线索核查不属实农户贷款不良客户占比 | DECIMAL |  |  |
| `LN_UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_BAL` | 辖内触发此类风险线索农户贷款不良余额 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_BAL_PPTN` | 辖内触发此类风险线索农户贷款不良余额占比 | DECIMAL |  |  |
| `NO_LN_UHLTH_BAL` | 辖内此类风险线索核查不属实农户贷款不良余额 | DECIMAL |  |  |
| `NO_LN_UHLTH_BAL_PPTN` | 辖内此类风险线索核查不属实农户贷款不良余额占比 | DECIMAL |  |  |
| `LN_UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `PEAS_LN_UHLTH_RATE` | 辖内触发此类风险线索农户贷款不良率 | DECIMAL |  |  |
| `NO_LN_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款不良率 | DECIMAL |  |  |
| `YEAR_CAN_POST_UHLTH_RATE` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `Y_CAN_POST_UHLTH_RATE` | 辖内触发此类风险线索农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `NO_YEAR_CAN_POST_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ALL_4YEAR_CAN_POST_UHLTH_RATE` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `Y4_CAN_POST_UHLTH_RATE` | 辖内触发此类风险线索农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `NO_4YEAR_CAN_POST_UHLTH_RATE` | 辖内此类风险线索核查不属实农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_MGG_RSK_C4`（农户贷款抵押物风险机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `MGG_RSK_TYP` | 抵押物风险类型 | VARCHAR | 是 |  |
| `CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `RSK_CTRT_NUM` | 辖内此类风险类型农户贷款合同数 | INT |  |  |
| `RSK_CTRT_PPTN` | 辖内此类风险类型农户贷款合同占比 | DECIMAL |  |  |
| `CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `RSK_CUST_NUM` | 辖内此类风险类型农户贷款客户数 | INT |  |  |
| `RSK_CUST_PPTN` | 辖内此类风险类型农户贷款客户占比 | DECIMAL |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `RSK_LN_BAL` | 辖内此类风险类型农户贷款余额 | DECIMAL |  |  |
| `RSK_LN_BAL_PPTN` | 辖内此类风险类型农户贷款余额占比 | DECIMAL |  |  |
| `UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_NUM` | 辖内此类风险类型农户贷款不良合同数 | INT |  |  |
| `RSK_UHLTH_CTRT_PPTN` | 辖内此类风险类型农户贷款不良合同占比 | DECIMAL |  |  |
| `UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_NUM` | 辖内此类风险类型农户贷款不良客户数 | INT |  |  |
| `RSK_UHLTH_CUST_PPTN` | 辖内此类风险类型农户贷款不良客户占比 | DECIMAL |  |  |
| `UHLTH_LN_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_LN_BAL` | 辖内此类风险类型农户贷款不良余额 | DECIMAL |  |  |
| `RSK_UHLTH_LN_BAL_PPTN` | 辖内此类风险类型农户贷款不良余额占比 | DECIMAL |  |  |
| `UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `RSK_UHLTH_RATE` | 辖内此类风险类型农户贷款不良率 | DECIMAL |  |  |
| `UP_UHLTH_RATE_1Y` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `RSK_UP_UHLTH_RATE_1Y` | 辖内此类风险类型农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `UP_UHLTH_RATE_4Y` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `RSK_UP_UHLTH_RATE_4Y` | 辖内此类风险类型农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_ADDR_RSK_ORG_SUM_C4`（农户贷款客户地址异常风险机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAME` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `ADDR_RSK_TYP` | 地址异常风险类型 | VARCHAR | 是 |  |
| `CTRT_NUM` | 辖内全部农户贷款合同数 | INT |  |  |
| `ADDR_RSK_CTRT_NUM` | 辖内此类风险类型农户贷款合同数 | INT |  |  |
| `ADDR_RSK_CTRT_PPTN` | 辖内此类风险类型农户贷款合同占比 | DECIMAL |  |  |
| `CUST_NUM` | 辖内全部农户贷款客户数 | INT |  |  |
| `ADDR_RSK_CUST_NUM` | 辖内此类风险类型农户贷款客户数 | INT |  |  |
| `ADDR_RSK_CUST_PPTN` | 辖内此类风险类型农户贷款客户占比 | DECIMAL |  |  |
| `BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `ADDR_RSK_BAL` | 辖内此类风险类型农户贷款余额 | DECIMAL |  |  |
| `ADDR_RSK_BAL_PPTN` | 辖内此类风险类型农户贷款余额占比 | DECIMAL |  |  |
| `UHLTH_CTRT_NUM` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `ADDR_RSK_UHLTH_CTRT_NUM` | 辖内此类风险类型农户贷款不良合同数 | INT |  |  |
| `ADDR_RSK_UHLTH_CTRT_PPTN` | 辖内此类风险类型农户贷款不良合同占比 | DECIMAL |  |  |
| `UHLTH_CUST_NUM` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `ADDR_RSK_UHLTH_CUST_NUM` | 辖内此类风险类型农户贷款不良客户数 | INT |  |  |
| `ADDR_RSK_UHLTH_CUST_PPTN` | 辖内此类风险类型农户贷款不良客户占比 | DECIMAL |  |  |
| `UHLTH_BAL` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `ADDR_RSK_UHLTH_BAL` | 辖内此类风险类型农户贷款不良余额 | DECIMAL |  |  |
| `ADDR_RSK_UHLTH_BAL_PPTN` | 辖内此类风险类型农户贷款不良余额占比 | DECIMAL |  |  |
| `UHLTH_RATE` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `ADDR_RSK_UHLTH_RATE` | 辖内此类风险类型农户贷款不良率 | DECIMAL |  |  |
| `REST_YEAR_CAN_UHLTH_RATE` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `ADDR_RSK_REST_YEAR_CAN_UHLTH_RATE` | 辖内此类风险类型农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `REST_L4YEAR_CAN_UHLTH_RATE` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `ADDR_RSK_REST_L4YEAR_CAN_UHLTH_RATE` | 辖内此类风险类型农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_PEAS_HRZ_MGR_LN_ANL_C4`（农户贷款高风险客户经理办贷机构级分析表(C4机构树)，43 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `HRZ_CUST_MGR_CNT` | 辖内高风险客户经理数 | INT |  |  |
| `HRZ_TOT_CNT_PEAS_LN` | 辖内高风险客户经理累计办理农户贷款合同数 | INT |  |  |
| `HRZ_TOT_CNT_UNM_PEAS_LN` | 辖内高风险客户经理累计办理非婚客户农户贷款合同数 | INT |  |  |
| `HRZ_TOT_CUST_PEAS_LN` | 辖内高风险客户经理累计办理农户贷款客户数 | INT |  |  |
| `HRZ_TOT_CUST_UNM_PEAS` | 辖内高风险客户经理累计办理农户非婚客户贷款客户数 | INT |  |  |
| `HRZ_TOT_LMT_PEAS_LN` | 辖内高风险客户经理累计办理农户贷款授信额度 | DECIMAL |  |  |
| `HRZ_TOT_LMT_UNM_PEAS` | 辖内高风险客户经理累计办理农户非婚客户贷款授信额度 | DECIMAL |  |  |
| `HRZ_CUR_CNT_PEAS_LN` | 辖内高风险客户经理已办理农户贷款当前有贷合同数 | INT |  |  |
| `HRZ_CUR_CNT_UNM_PEAS_LN` | 辖内高风险客户经理已办理非婚客户农户贷款当前有贷合同数 | INT |  |  |
| `HRZ_CUR_CUST_PEAS_LN` | 辖内高风险客户经理已办理农户贷款当前有贷客户数 | INT |  |  |
| `HRZ_CUR_CUST_UNM_PEAS_LN` | 辖内高风险客户经理已办理非婚客户农户贷款当前有贷客户数 | INT |  |  |
| `HRZ_CUR_BAL_PEAS_LN` | 辖内高风险客户经理已办理农户贷款当前余额 | DECIMAL |  |  |
| `HRZ_CUR_BAL_UNM_PEAS_LN` | 辖内高风险客户经理已办理非婚客户农户贷款当前余额 | DECIMAL |  |  |
| `HRZ_CUR_CNT_NPL_PEAS` | 辖内高风险客户经理已办理农户贷款当前不良合同数 | INT |  |  |
| `HRZ_CUR_CNT_NPL_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款当前不良合同数 | INT |  |  |
| `HRZ_CUR_CUST_NPL_PEAS` | 辖内高风险客户经理已办理农户贷款当前不良客户数 | INT |  |  |
| `HRZ_CUR_CUST_NPL_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款当前不良客户数 | INT |  |  |
| `TOT_CUR_BAL_NPL_PEAS` | 辖内全部农户贷款当前不良余额 | DECIMAL |  |  |
| `HRZ_CUR_BAL_NPL_PEAS` | 辖内高风险客户经理已办理农户贷款当前不良余额 | DECIMAL |  |  |
| `HRZ_RAT_NPL_PEAS` | 辖内高风险客户经理已办理农户贷款当前不良余额占比 | DECIMAL |  |  |
| `HRZ_CUR_BAL_NPL_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款当前不良余额 | DECIMAL |  |  |
| `HRZ_RAT_NPL_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款当前不良余额占比 | DECIMAL |  |  |
| `HRZ_CUR_RAT_NPL_PEAS` | 辖内高风险客户经理已办理农户贷款当前不良率 | DECIMAL |  |  |
| `HRZ_CUR_RAT_NPL_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款当前不良率 | DECIMAL |  |  |
| `HRZ_ADJ_RAT_NPL_CAN_CUR` | 辖内高风险客户经理已办理农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `HRZ_ADJ_RAT_NPL_CAN_UNM` | 辖内高风险客户经理已办理非婚客户农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `HRZ_ADJ_RAT_NPL_CAN_4YR` | 辖内高风险客户经理已办理农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `HRZ_ADJ_RAT_NPL_CAN_U4Y` | 辖内高风险客户经理已办理非婚客户农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `HRZ_GEN_RAT_NPL_CAN_CUR` | 辖内高风险客户经理已办理农户贷款当年年化不良生成率 | DECIMAL |  |  |
| `HRZ_GEN_RAT_NPL_EXC_COL` | 辖内高风险客户经理已办理农户贷款当年剔除清收后年化不良生成率 | DECIMAL |  |  |
| `HRZ_GEN_RAT_NPL_12M_RT` | 辖内高风险客户经理已办理农户贷款近12个月不良生成率 | DECIMAL |  |  |
| `HRZ_GEN_RAT_NPL_EXC_12M` | 辖内高风险客户经理已办理农户贷款近12个月剔除清收后不良生成率 | DECIMAL |  |  |
| `HRZ_CUR_BAL_OD_PEAS` | 辖内高风险客户经理已办理农户贷款当前逾期余额 | DECIMAL |  |  |
| `HRZ_CUR_RAT_OD_PEAS` | 辖内高风险客户经理已办理农户贷款当前逾期率 | DECIMAL |  |  |
| `HRZ_MAX_YEA_NPL_CON_PEA` | 辖内高风险客户经理已办理农户贷款不良发生最多的合同签约年份 | VARCHAR |  |  |

### `S_00PF_PEAS_CONT_QUAL_C4`（农户贷款接续质量机构级分析表（C4机构树），28 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `LN_BAL` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `CTNU_LN_BAL` | 辖内无还本续贷农户贷款余额 | DECIMAL |  |  |
| `CTNU_LN_BAD_BAL` | 辖内无还本续贷农户贷款不良余额 | DECIMAL |  |  |
| `CTNU_LN_BAD_RATE` | 辖内无还本续贷农户贷款不良率 | DECIMAL |  |  |
| `ONE_CTNU_LN_BAL` | 辖内一键续贷农户贷款余额 | DECIMAL |  |  |
| `ONE_CTNU_LN_BAD_BAL` | 辖内一键续贷农户贷款不良余额 | DECIMAL |  |  |
| `ONE_CTNU_LN_BAD_RATE` | 辖内一键续贷农户贷款不良率 | DECIMAL |  |  |
| `RNEW_LN_BAL` | 辖内展期农户贷款余额 | DECIMAL |  |  |
| `RNEW_LN_BAD_BAL` | 辖内展期农户贷款不良余额 | DECIMAL |  |  |
| `RNEW_LN_BAD_RATE` | 辖内展期农户贷款不良率 | DECIMAL |  |  |
| `NOT_BAD_AGN_LN_BAL` | 辖内非不良重组农户贷款余额 | DECIMAL |  |  |
| `NOT_BAD_AGN_LN_BAD_BAL` | 辖内非不良重组农户贷款不良余额 | DECIMAL |  |  |
| `NOT_BAD_AGN_LN_BAD_RATE` | 辖内非不良重组农户贷款不良率 | DECIMAL |  |  |
| `BAD_AGN_LN_BAL` | 辖内不良重组农户贷款余额 | DECIMAL |  |  |
| `BAD_AGN_LN_BAD_BAL` | 辖内不良重组农户贷款不良余额 | DECIMAL |  |  |
| `BAD_AGN_LN_BAD_RATE` | 辖内不良重组农户贷款不良率 | DECIMAL |  |  |
| `BAL_SUM` | 辖内以上各类接续工具农户贷款余额合计 | DECIMAL |  |  |
| `BAD_BAL_SUM` | 辖内以上各类接续工具农户贷款不良余额合计 | DECIMAL |  |  |
| `BAD_RATE_SUM` | 辖内以上各类接续工具农户贷款不良率合计 | DECIMAL |  |  |
| `BAL_SUM_NOT_BAD_AGN` | 辖内以上各类接续工具农户贷款余额合计 ( 除不良重组 ) | DECIMAL |  |  |
| `BAD_BAL_SUM_NOT_BAD_AGN` | 辖内以上各类接续工具农户贷款不良余额合计 ( 除不良重组 ) | DECIMAL |  |  |
| `BAD_RATE_SUM_NOT_BAD_AGN` | 辖内以上各类接续工具农户贷款不良率合计 ( 除不良重组 ) | DECIMAL |  |  |

### `S_00PF_PEAS_LN_SPC_ORG_ANL_C4`（农户贷款专项产品机构级分析表(C4机构树)，33 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR |  |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM` | C4机构名称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域标识 | VARCHAR |  |  |
| `SUPE_C4_ORG_NO` | 上一级C4机构编码 | VARCHAR |  |  |
| `SUPE_C4_ORG_NAME` | 上一级C4机构名称 | VARCHAR |  |  |
| `PEAS_LN_C4_SPC` | 农户贷款C4专项产品 | VARCHAR | 是 |  |
| `TTL_CNT_PEAS_LN` | 辖内全部农户贷款合同数 | INT |  |  |
| `SPC_CNT_PEAS_LN` | 辖内此类专项产品农户贷款合同数 | INT |  |  |
| `SPC_RAT_CNT_PEAS` | 辖内此类专项产品农户贷款合同数占比 | DECIMAL |  |  |
| `TTL_CUST_PEAS_LN` | 辖内全部农户贷款客户数 | INT |  |  |
| `SPC_CUST_PEAS_LN` | 辖内此类专项产品农户贷款客户数 | INT |  |  |
| `SPC_RAT_CUST_PEA` | 辖内此类专项产品农户贷款客户数占比 | DECIMAL |  |  |
| `TTL_BAL_PEAS_LN` | 辖内全部农户贷款余额 | DECIMAL |  |  |
| `SPC_BAL_PEAS_LN` | 辖内此类专项产品农户贷款余额 | DECIMAL |  |  |
| `SPC_RAT_BAL_PEAS` | 辖内此类专项产品农户贷款余额占比 | DECIMAL |  |  |
| `TTL_CNT_NPL_PEAS` | 辖内全部农户贷款不良合同数 | INT |  |  |
| `SPC_CNT_NPL_PEAS` | 辖内此类专项产品农户贷款不良合同数 | INT |  |  |
| `SPC_RAT_NPL_CNT` | 辖内此类专项产品农户贷款不良合同占比 | DECIMAL |  |  |
| `TTL_CUST_NPL_PEA` | 辖内全部农户贷款不良客户数 | INT |  |  |
| `SPC_CUST_NPL_PEA` | 辖内此类专项产品农户贷款不良客户数 | INT |  |  |
| `SPC_RAT_NPL_CST` | 辖内此类专项产品农户贷款不良客户占比 | DECIMAL |  |  |
| `TTL_BAL_NPL_PEAS` | 辖内全部农户贷款不良余额 | DECIMAL |  |  |
| `SPC_BAL_NPL_PEAS` | 辖内此类专项产品农户贷款不良余额 | DECIMAL |  |  |
| `SPC_RAT_NPL_BAL` | 辖内此类专项产品农户贷款不良余额占比 | DECIMAL |  |  |
| `TTL_RAT_NPL_PEAS` | 辖内全部农户贷款不良率 | DECIMAL |  |  |
| `SPC_RAT_NPL_PEAS` | 辖内此类专项产品农户贷款不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_CAN_CUR` | 辖内全部农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `SPC_ADJ_RAT_CAN_CUR` | 辖内此类专项产品农户贷款还原当年核销后不良率 | DECIMAL |  |  |
| `TTL_ADJ_RAT_NPL_CAN` | 辖内全部农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |
| `SPC_ADJ_RAT_NPL_CAN` | 辖内此类专项产品农户贷款还原近4个自然年核销后不良率 | DECIMAL |  |  |

### `S_00PF_IDV_CUST_FA_SUM`（个人客户金融资产汇总，40 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR | 是 |  |
| `ORG_NO` | 机构编号 | VARCHAR | 是 |  |
| `ORG_LVL` | 农行组织机构层级 | VARCHAR |  |  |
| `FST_BRCH_IND` | 是否一级分行标识 | VARCHAR |  |  |
| `EXT_BUS_ORG_IND` | 是否对外营业机构标识 | VARCHAR |  |  |
| `ARP_SHARE_IND` | 组织机构三农分摊标识（财务会计部） | VARCHAR |  |  |
| `SPE_SUBD_ORG_IND` | 特殊下级对外营业机构标识 | VARCHAR |  |  |
| `SPE_SUPE_ORG_IND` | 特殊上级对外营业机构标识 | VARCHAR |  |  |
| `FA_BAL` | 金融资产余额 | DECIMAL |  |  |
| `FA_MTH_ACLT` | 金融资产余额月积数 | DECIMAL |  |  |
| `FA_MAVER_BAL` | 月日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_LST_3_MTH` | 近3个月日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_LST_6_MTH` | 近6个月日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_LST_12_MTH` | 近12个月日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_SAVER` | 当季季日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_HAVER` | 半年日均金融资产余额 | DECIMAL |  |  |
| `FA_BAL_YAVER` | 当年年日均金融资产余额 | DECIMAL |  |  |
| `AUM_BAL` | AUM余额 | DECIMAL |  |  |
| `AUM_MTH_ACLT` | AUM月积数 | DECIMAL |  |  |
| `AUM_MAVER_BAL` | 月日均AUM | DECIMAL |  |  |
| `AUM_BAL_LST_3_MTH` | 近3个月日均AUM | DECIMAL |  |  |
| `AUM_BAL_LST_6_MTH` | 近6个月日均AUM | DECIMAL |  |  |
| `AUM_BAL_LST_12_MTH` | 近12个月日均AUM | DECIMAL |  |  |
| `AUM_BAL_SAVER` | 当季季日均AUM | DECIMAL |  |  |
| `AUM_BAL_HAVER` | 半年日均AUM | DECIMAL |  |  |
| `AUM_BAL_YAVER` | 当年年日均AUM | DECIMAL |  |  |
| `TOT_IVST_BAL` | 总投资余额 | DECIMAL |  |  |
| `TOT_IVST_MTH_ACLT` | 总投资余额月积数 | DECIMAL |  |  |
| `TOT_IVST_MAVER_BAL` | 月日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_LST_3_MTH` | 近3个月日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_LST_6_MTH` | 近6个月日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_LST_12_MTH` | 近12个月日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_SAVER` | 当季季日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_HAVER` | 半年日均总投资余额 | DECIMAL |  |  |
| `TOT_IVST_BAL_YAVER` | 当年年日均总投资余额 | DECIMAL |  |  |
| `FA_BAL_MAX` | 金融资产余额最大值 | DECIMAL |  |  |
| `FA_BAL_MAX_DATE` | 金融资产余额最大值日期 | VARCHAR |  |  |
| `AUM_BAL_MAX` | AUM最大值 | DECIMAL |  |  |
| `AUM_BAL_MAX_DATE` | AUM最大值日期 | VARCHAR |  |  |

### `S_00PF_IDV_DP_CUST_SUM`（个人存款客户级汇总，107 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CUST_NO` | 客户ID | VARCHAR | 是 |  |
| `ORG_NO` | 机构编号 | VARCHAR | 是 |  |
| `ORG_LVL` | 机构层级 | VARCHAR |  |  |
| `FST_BRCH_IND` | 是否一级分行标识 | VARCHAR |  |  |
| `EXT_BUS_ORG_IND` | 是否对外营业机构标识 | VARCHAR |  |  |
| `RMB_REG_CAP` | 开户本金折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL` | 存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_MTH` | 当月日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_SEAN` | 近三月日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_HYEAR` | 近半年日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_YEAR` | 近一年日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_SAVER` | 当季日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_HAVER` | 当半年日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DP_BAL_YAVER` | 当年日均存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL` | 活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_MTH` | 当月日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_SEAN` | 近三月日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_HYEAR` | 近半年日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_YEAR` | 近一年日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_SAVER` | 当季日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_HAVER` | 当半年日均活期存款余额折人民币 | DECIMAL |  |  |
| `RMB_DPSA_BAL_YAVER` | 当年日均活期存款余额折人民币 | DECIMAL |  |  |
| `DPSA_LAC_DAT` | 活期存款最后动账日期 | VARCHAR |  |  |
| `RMB_DCARD_SA_BAL` | 借记卡活期余额折人民币 | DECIMAL |  |  |
| `RMB_DCCARD_SA_BAL` | 准贷记卡活期余额折人民币 | DECIMAL |  |  |
| `RMB_CCARD_SA_BAL` | 贷记卡活期余额折人民币 | DECIMAL |  |  |
| `RMB_SA_PSBK_BAL` | 活期存折余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL` | 定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_MTH` | 当月日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_SEAN` | 近三月日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_HYEAR` | 近半年日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_YEAR` | 近一年日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_SAVER` | 当季日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_HAVER` | 当半年日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TD_BAL_YAVER` | 当年日均定期存款余额折人民币 | DECIMAL |  |  |
| `RMB_TMDP_BAL` | 整存整取余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_MTH` | 当月日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_SEAN` | 近三月日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_HYEAR` | 近半年日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_YEAR` | 近一年日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_SAVER` | 当季日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_HAVER` | 当半年日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_YAVER` | 当年日均通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_DCARD_NTDP_BAL` | 借记卡通知存款活期余额折人民币 | DECIMAL |  |  |
| `RMB_DCCARD_NTDP_BAL` | 准贷记卡存款余额折人民币 | DECIMAL |  |  |
| `TMDP_LAC_DAT` | 整存整取最后动账日期 | VARCHAR |  |  |
| `RMB_NTDP_BAL` | 通知存款余额折人民币 | DECIMAL |  |  |
| `NTDP_LAC_DAT` | 通知存款最后动账日期 | VARCHAR |  |  |
| `RMB_FXDI_BAL` | 零存整取余额折人民币 | DECIMAL |  |  |
| `FXDI_LAC_DAT` | 零存整取最后动账日期 | VARCHAR |  |  |
| `RMB_TDOP_BAL` | 定活两便余额折人民币 | DECIMAL |  |  |
| `TDOP_LAC_DAT` | 定活两便最后动账日期 | VARCHAR |  |  |
| `RMB_IWDP_BAL` | 存本取息余额折人民币 | DECIMAL |  |  |
| `IWDP_LAC_DAT` | 存本取息最后动账日期 | VARCHAR |  |  |
| `RMB_DCARD_TD_BAL` | 借记卡定期余额折人民币 | DECIMAL |  |  |
| `RMB_DCCARD_TD_BAL` | 准贷记卡定期余额折人民币 | DECIMAL |  |  |
| `RMB_TD_PSBK_BAL` | 定期一本通余额折人民币 | DECIMAL |  |  |
| `RMB_LSSW_BAL` | 整存零取余额折人民币 | DECIMAL |  |  |
| `LSSW_LAC_DAT` | 整存零取最后动账日期 | VARCHAR |  |  |
| `RMB_LAMT_BAL` | 大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_MTH` | 当月日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_SEAN` | 近三月日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_HYEAR` | 近半年日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_YEAR` | 近一年日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_SAVER` | 当季日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_HAVER` | 当半年日均大额存单余额折人民币 | DECIMAL |  |  |
| `RMB_LAMT_BAL_YAVER` | 当年日均大额存单余额折人民币 | DECIMAL |  |  |
| `LAMT_BAL_DAT` | 大额存单最后动账日期 | VARCHAR |  |  |
| `RMB_MARG_BAL` | 保证金余额折人民币 | DECIMAL |  |  |
| `MARG_BAL_DAT` | 保证金最后动账日期 | VARCHAR |  |  |
| `RMB_STRD_BAL` | 结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_MTH` | 当月日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_SEAN` | 近三月日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_HYEAR` | 近半年日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_YEAR` | 近一年日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_SAVER` | 当季日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_HAVER` | 当半年日均结构性存款余额折人民币 | DECIMAL |  |  |
| `RMB_STRD_BAL_YAVER` | 当年日均结构性存款余额折人民币 | DECIMAL |  |  |
| `STRD_BAL_DAT` | 结构性存款最后动账日期 | VARCHAR |  |  |
| `RMB_GENR_BAL` | 银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_MTH` | 当月日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_SEAN` | 近三月日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_HYEAR` | 近半年日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_YEAR` | 近一年日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_SAVER` | 当季日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_HAVER` | 当半年日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_GENR_BAL_YAVER` | 当年日均银利多余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_1D` | 一天通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_NTDP_BAL_7D` | 七天通知存款余额折人民币 | DECIMAL |  |  |
| `RMB_PSBK_BAL` | 存折余额折人民币 | DECIMAL |  |  |
| `RMB_RCPT_BAL` | 存单余额折人民币 | DECIMAL |  |  |
| `RMB_DEP_BAL` | 存款余额(人民币) | DECIMAL |  |  |
| `FCCY_DP_BAL` | 外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_MTH` | 当月日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_SEAN` | 近三月日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_HYEAR` | 近半年日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_YEAR` | 近一年日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_SAVER` | 当季日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_HAVER` | 半年日均外币存款余额折人民币 | DECIMAL |  |  |
| `RMB_FCCY_DP_BAL_YAVER` | 当年日均外币存款余额折人民币 | DECIMAL |  |  |
| `FCCY_DPSA_BAL` | 外币活期存款余额折人民币 | DECIMAL |  |  |
| `FCCY_TD_BAL` | 外币定期存款余额折人民币 | DECIMAL |  |  |
| `FCCY_NTDP_BAL` | 外币通知存款余额折人民币 | DECIMAL |  |  |
| `FCCY_DP_BAL_HYEAR` | 近6个月持有外币存款 | DECIMAL |  |  |
| `DP_BAL_MAX` | 当月存款余额最大值 | DECIMAL |  |  |
| `DP_BAL_MAX_DATE` | 当月存款余额最大值日期 | VARCHAR |  |  |

### `S_00PF_SA_ACCT_TR_CUST_SUM`（活期账户交易客户级汇总，42 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` |  | VARCHAR | 是 |  |
| `CUST_NO` |  | VARCHAR | 是 |  |
| `TR_CNT` | '当日交易笔数', | INT |  |  |
| `TR_BAL` | '当日交易金额', | DECIMAL |  |  |
| `MOTH_TR_CNT` | '当月交易笔数', | INT |  |  |
| `MOTH_TR_BAL` | '当月交易金额', | DECIMAL |  |  |
| `SEAN_TR_CNT` | '当季交易笔数', | INT |  |  |
| `SEAN_TR_BAL` | '当季交易金额', | DECIMAL |  |  |
| `HYEAR_TR_CNT` | '半年交易笔数', | INT |  |  |
| `HYEAR_TR_BAL` | '半年交易金额', | DECIMAL |  |  |
| `YEAR_TR_CNT` | '当年交易笔数', | INT |  |  |
| `YEAR_TR_BAL` | '当年交易金额', | DECIMAL |  |  |
| `YEAR_TR_CNT_L1YER_ACLT` | '近12个月交易笔数', | INT |  |  |
| `YEAR_TR_BAL_L1YER_ACLT` | '近12个月交易金额', | DECIMAL |  |  |
| `DAY_TR_CNT_IN` | '当日流入笔数', | INT |  |  |
| `DAY_TR_BAL_IN` | '当日流入金额', | DECIMAL |  |  |
| `MOTH_TR_CNT_IN` | '当月流入笔数', | INT |  |  |
| `MOTH_TR_BAL_IN` | '当月流入金额', | DECIMAL |  |  |
| `SEAN_TR_CNT_IN` | '当季流入笔数', | INT |  |  |
| `SEAN_TR_BAL_IN` | '当季流入金额', | DECIMAL |  |  |
| `HYEAR_TR_CNT_IN` | '半年流入笔数', | INT |  |  |
| `HYEAR_TR_BAL_IN` | '半年流入金额', | DECIMAL |  |  |
| `YEAR_TR_CNT_IN` | '当年流入笔数', | INT |  |  |
| `YEAR_TR_BAL_IN` | '当年流入金额', | DECIMAL |  |  |
| `YEAR_TR_CNT_IN_L1YER_ACLT` | '近12个月流入笔数', | INT |  |  |
| `YEAR_TR_BAL_IN_L1YER_ACLT` | '近12个月流入金额', | DECIMAL |  |  |
| `DAY_TR_CNT_OUT` | '当日流出笔数', | INT |  |  |
| `DAY_TR_BAL_OUT` | '当日流出金额', | DECIMAL |  |  |
| `MOTH_TR_CNT_OUT` | '当月流出笔数', | INT |  |  |
| `MOTH_TR_BAL_OUT` | '当月流出金额', | DECIMAL |  |  |
| `SEAN_TR_CNT_OUT` | '当季流出笔数', | INT |  |  |
| `SEAN_TR_BAL_OUT` | '当季流出金额', | DECIMAL |  |  |
| `HYEAR_TR_CNT_OUT` | '半年流出笔数', | INT |  |  |
| `HYEAR_TR_BAL_OUT` | '半年流出金额', | DECIMAL |  |  |
| `YEAR_TR_CNT_OUT` | '当年流出笔数', | INT |  |  |
| `YEAR_TR_BAL_OUT` | '当年流出金额', | DECIMAL |  |  |
| `YEAR_TR_CNT_OUT_L1YER_ACLT` | '近12个月流出笔数', | INT |  |  |
| `YEAR_TR_BAL_OUT_L1YER_ACLT` | '近12个月流出金额', | DECIMAL |  |  |
| `MAX_DAY_TR_BAL_IN` | '当日单笔最大流入交易金额', | DECIMAL |  |  |
| `MAX_DAY_TR_BAL_OUT` | '当日单笔最大流出交易金额', | DECIMAL |  |  |
| `MAX_MOTH_TR_BAL_IN` | '当月单笔最大流入交易金额', | DECIMAL |  |  |
| `MAX_MOTH_TR_BAL_OUT` | '当月单笔最大流出交易金额' | DECIMAL |  |  |

### `B_00DT_C4_ORG_TREE_H`（C4机构树历史，59 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR |  |  |
| `C4_ORG_NO` | C4机构编码 | VARCHAR | 是 |  |
| `C4_ORG_NAM` | C4机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_NO` | EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_CN_NAM` | EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_CN_SHT_NAM` | EIMO机构中文简称 | VARCHAR |  |  |
| `EIMO_ORG_EN_NAM` | EIMO机构英文名称 | VARCHAR |  |  |
| `EIMO_ORG_EN_SHT_NAM` | EIMO机构英文简称 | VARCHAR |  |  |
| `C4_ORG_LVL` | C4机构层级 | VARCHAR |  |  |
| `C4_ORG_STS_CD` | C4机构状态 | VARCHAR |  |  |
| `C4_CTRY_RGN_CTG_CD` | C4机构县域分类 | VARCHAR |  |  |
| `EIMO_ORG_CTG` | EIMO机构类别 | VARCHAR |  |  |
| `EIMO_ORG_LVL` | EIMO机构层级 | VARCHAR |  |  |
| `EIMO_ORG_TYP_CD` | EIMO机构类型码 | VARCHAR |  |  |
| `EIMO_ORG_ARP_IND` | EIMO机构三农标识 | VARCHAR |  |  |
| `EIMO_ORG_CLS_IND` | EIMO机构分类标识 | VARCHAR |  |  |
| `EIMO_ORG_STS` | EIMO机构状态 | VARCHAR |  |  |
| `C4_DIRE_SUPE_NO` | 直接上级机构C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NO_1` | 第1层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_1` | 第1层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_1` | 第1层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_1` | 第1层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_1` | 第1层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_2` | 第2层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_2` | 第2层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_2` | 第2层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_2` | 第2层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_2` | 第2层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_3` | 第3层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_3` | 第3层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_3` | 第3层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_3` | 第3层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_3` | 第3层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_4` | 第4层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_4` | 第4层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_4` | 第4层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_4` | 第4层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_4` | 第4层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_5` | 第5层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_5` | 第5层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_5` | 第5层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_5` | 第5层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_5` | 第5层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_6` | 第6层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_6` | 第6层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_6` | 第6层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_6` | 第6层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_6` | 第6层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_NO_7` | 第7层C4机构编码 | VARCHAR |  |  |
| `C4_ORG_NAM_7` | 第7层C4机构名称 | VARCHAR |  |  |
| `EIMO_ORG_NO_7` | 第7层EIMO机构编码 | VARCHAR |  |  |
| `EIMO_ORG_NAM_7` | 第7层EIMO机构中文名称 | VARCHAR |  |  |
| `EIMO_ORG_SHT_NAM_7` | 第7层EIMO机构中文简称 | VARCHAR |  |  |
| `C4_ORG_TREE_LVL` | C4机构树层级 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `STARTDT` | 开始日期 | DATE | 是 |  |
| `ENDDT` | 结束日期 | DATE |  |  |
| `VALIDDT` | 有效日期 | DATE |  |  |
| `TIMESTAMP` | 时间戳 | DATETIME |  |  |

### `B_00DT_UHLTH_LN_AMT_CHG_H`（不良贷款金额变动信息历史，41 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR | 是 |  |
| `VCH_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CHG_DAT` | 变动日期 | VARCHAR | 是 |  |
| `CHG_CLS` | 变动种类 | VARCHAR |  | 01-清收变动
02-呆账核销
03-形态调整
04-资产划转
05-新增抵债资 |
| `CHG_SER_NO` | 变动序号 | DECIMAL | 是 |  |
| `SPLT_SER_NO` | 拆分序号 | DECIMAL | 是 |  |
| `WON_ALR_CAN` | 是否已核销 | VARCHAR |  |  |
| `CHG_ORG` | 变动机构编码 | VARCHAR |  |  |
| `CHG_ORG_EIMO` | 经营EIMO机构编码 | VARCHAR |  |  |
| `CUST_CD` | 客户ID | VARCHAR |  |  |
| `FTH_LVL_CLS` | 五级分类 | VARCHAR |  | 10-正常
11-正常一
12-正常二
13-正常三
14-正常四
20-关注
 |
| `CCY` | 币种 | VARCHAR |  |  |
| `CHG_CAP` | 变动本金 | DECIMAL |  |  |
| `CHG_NML_INTS` | 变动正常息 | DECIMAL |  |  |
| `CHG_DEF_INTS` | 变动罚息 | DECIMAL |  |  |
| `CHG_COM_INTS` | 变动复利 | DECIMAL |  |  |
| `CHG_POST_CAP_BAL` | 变动后本金余额 | DECIMAL |  |  |
| `CHG_POST_IN_INTS_BAL` | 变动后表内息余额 | DECIMAL |  |  |
| `CHG_POST_OFF_INTS_BAL` | 变动后表外息余额 | DECIMAL |  |  |
| `REVK_MOD` | 收回方式 | VARCHAR |  | 1-现金清收
2-非现金清收
3-减免不计清收
4-不纳入统计范围(已被冲正/账 |
| `DPSE_MOD` | 处置方式 | VARCHAR |  | 01-直接追偿
02-诉讼追偿
03-委外清收
04-减免息
05-抵债资产处置 |
| `RPAY_SOR` | 还款来源 | VARCHAR |  | 0-第一还款来源
1-第二还款来源(押品)
2-第二还款来源(保证人)
9-其他 |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `REM` | 备注 | VARCHAR |  |  |
| `SPLT_STS` | 拆分状态 | VARCHAR |  |  |
| `DATA_SOR` | 数据来源 | VARCHAR |  |  |
| `ADT_REC_STS` | 补录状态 | VARCHAR |  | 00-未补录
01-已补录
02-不需补录
03-冲正不需补录
04-待登记
0 |
| `OPR_ORG_CD` | 操作机构编码 | VARCHAR |  |  |
| `OPR_ORG_CD_EIMO` | 操作EIMO机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `CRDR_DBT_FINAL_IND` | 债权债务关系终结标识 | VARCHAR |  |  |
| `CAN_SUB_TYP_IND` | 核销子类型标识 | VARCHAR |  | 1-列入国家兼并破产计划核销，并且了结全部债权与债务关系的贷款
2-经国务院专案 |
| `AUX_FLD_1` | 备用字段1 | VARCHAR |  |  |
| `AUX_FLD_2` | 备用字段2 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `STARTDT` | 开始日期 | DATE | 是 |  |
| `ENDDT` | 结束日期 | DATE |  |  |
| `VALIDDT` | 有效日期 | DATE |  |  |
| `TIMESTAMP` | 时间戳 | DATETIME |  |  |

### `B_00DT_PRLN_SCRE_EVT_H`（个人贷款评分结果历史，16 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `LN_VCH_NO` | 借款凭证编号 | VARCHAR | 是 |  |
| `SCRE_DAT` | 评分日期 | VARCHAR | 是 |  |
| `CUST_COD` | 客户编码 | VARCHAR |  |  |
| `DISB_C4_ORG_COD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_EMIO_ORG_COD` | 放款机构EMIO机构编码 | VARCHAR |  |  |
| `MDL_COD` | 模型编码 | VARCHAR |  |  |
| `MDL_BASIC_PENY` | 模型基础分 | DECIMAL |  |  |
| `TRFM_SCRE` | 转换得分 | DECIMAL |  |  |
| `TRFM_FMUL` | 转换公式 | VARCHAR |  |  |
| `AUX_FLD_1` | 备用字段1 | VARCHAR |  |  |
| `AUX_FLD_2` | 备用字段2 | DECIMAL |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `STARTDT` | 开始日期 | DATE | 是 |  |
| `ENDDT` | 结束日期 | DATE |  |  |
| `VALIDDT` | 有效日期 | DATE |  |  |
| `TIMESTAMP` | 时间戳 | DATETIME |  |  |

### `P_00RLDM_RL_LOAN_SCORE`（贷款评分结果表，15 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `RLS_VCHNO` | 借款凭证编号 | VARCHAR |  |  |
| `RLS_RATE_DATE` | 评分日期 | VARCHAR |  |  |
| `RLS_CLICODE` | 客户编号 | VARCHAR |  |  |
| `RLS_INSTCODE` | 放款机构 | VARCHAR |  |  |
| `RLS_MODELCODE` | 模型编码 | VARCHAR |  |  |
| `RLS_BASESCORE` | 模型基础分 | DECIMAL |  |  |
| `RLS_SCORE` | 转换得分 | DECIMAL |  |  |
| `RLS_FORMULA` | 转换公式 | VARCHAR |  |  |
| `RLS_RES1` | 备用字段1 | VARCHAR |  |  |
| `RLS_RES2` | 备用字段2 | DECIMAL |  |  |
| `startdate` | 开始日期 | varchar |  |  |
| `enddate` | 结束日期 | varchar |  |  |
| `validdate` | 有效日期 | varchar |  |  |
| `SUBPRIKEY` | 次主键标记 | varchar |  |  |
| `TIMESTAMPE` | 时间戳 | datetime |  |  |

### `G_00PL_IDV_LN_MGG_HPROP_RSK_INFO_DV`（个人贷款抵押房产风险信息表，134 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `AST_NO` | 资产编号 | VARCHAR | 是 |  |
| `PROP_OWNR_CUST_NO` | 产权人客户编号 | VARCHAR | 是 |  |
| `LN_CTRT_NO` | 合同编号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `APR_BAT_NO` | 审批批次号 | INT |  |  |
| `CORE_LN_CTRT_NO` | 合同正本编号 | VARCHAR |  |  |
| `COPRT_BREED_NO` | 合作品种编号 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USG` | 借款用途 | VARCHAR |  |  |
| `COPRT_ITEM_NO` | 合作项目编号 | VARCHAR |  |  |
| `COPRT_ITEM_NAM` | 合作项目名称 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `BUS_ATCH_BAR_LINE_CD` | 部门归属 | VARCHAR |  |  |
| `CTRT_CLS_CD` | 合同种类 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `TGTR_APR_IND` | 是否一并审批 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险 | VARCHAR |  |  |
| `LOW_RSK_BUS_CTG_CD` | 低风险业务类别 | VARCHAR |  |  |
| `CTRT_AMT` | 借款金额 | DECIMAL |  |  |
| `CTRT_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `PRVD_TRMN_DAT` | 发放终止日期 | VARCHAR |  |  |
| `SIGD_DAT` | 签约日期 | VARCHAR |  |  |
| `CTRT_STS_CD` | 合同状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_FLOW_STS_IND` | 放款流程状态标志 | VARCHAR |  |  |
| `CUST_REG_BNK` | 申请人开户银行 | VARCHAR |  |  |
| `DISB_ORG_NO` | 经营机构C4机构编码 | VARCHAR |  |  |
| `DISB_ORG_NO_STD` | 经营机构EIMO机构编码 | VARCHAR |  |  |
| `PROP_OWNR_STARTDT` | 产权开始日期 | VARCHAR |  |  |
| `SIGD_CTRT_PROP_HODG_DAYS` | 签约合同时产权持有天数 | INT |  |  |
| `PROP_OWNR_ENDDT` | 产权结束日期 | VARCHAR |  |  |
| `PROP_OWNR_AVA_CD` | 产权有效性代码 | VARCHAR |  |  |
| `PROP_OWNR_TYP_CD` | 产权类型代码 | VARCHAR |  |  |
| `PROP_OWNR_SHR` | 产权份额（%） | DECIMAL |  |  |
| `COMP_PROJ_DAT` | 竣工日期 | VARCHAR |  |  |
| `COMP_PROJ_DAT_SIGD_CTRT_DAYS` | 竣工日期距合同签约日期天数 | INT |  |  |
| `BULD_OVRGRD_LVL` | 建筑物地上层数 | INT |  |  |
| `BULD_UNDGRD_LVL` | 建筑物地下层数 | INT |  |  |
| `HOUSE_LOCT_ACT_FLR` | 房屋所在实际楼层 | INT |  |  |
| `HOUSE_LOCT_NOM_FLR` | 房屋所在名义楼层 | INT |  |  |
| `TOP_LVL_IND` | 是否顶层 | VARCHAR |  |  |
| `NEXT_TOP_LVL_IND` | 是否次顶层 | VARCHAR |  |  |
| `EVAL_VLU` | 评估价值 | DECIMAL |  |  |
| `EVAL_BASE_DAT` | 评估基准日期 | VARCHAR |  |  |
| `EVAL_VALD_MATU_DAT` | 评估有效到期日期 | VARCHAR |  |  |
| `MGG_BGN_EVAL_TIME` | 抵押物初始评估时间 | VARCHAR |  |  |
| `MGG_BGN_EVAL_VLU` | 抵押物初始评估价值 ( 元 ) | DECIMAL |  |  |
| `MGG_BGN_LTST_TIME` | 抵押物最新评估时间 | VARCHAR |  |  |
| `MGG_BGN_LTST_VLU` | 抵押物最新评估价值 ( 元 ) | DECIMAL |  |  |
| `MGG_BGN_EXT_QRY_TIME` | 抵押物初始外部查询时间 | VARCHAR |  |  |
| `MGG_BGN_EXT_QRY_VLU` | 抵押物初始外部查询价值 ( 元 ) | DECIMAL |  |  |
| `MGG_LTST_EXT_QRY_TIME` | 抵押物最新外部查询时间 | VARCHAR |  |  |
| `MGG_LTST_EXT_QRY_VLU` | 抵押物最新外部查询价值 ( 元 ) | DECIMAL |  |  |
| `MGG_VLU_REF_NO_IND` | 抵押物价值高评参考标识 | VARCHAR |  |  |
| `EVAL_MTHD_1_CD` | 评估方法1代码 | VARCHAR |  |  |
| `EVAL_MTHD_2_CD` | 评估方法2代码 | VARCHAR |  |  |
| `EVAL_MOD_CD` | 评估方式代码 | VARCHAR |  |  |
| `EVAL_EVT_SOR_CD` | 评估结果来源代码 | VARCHAR |  |  |
| `EXT_EVAL_ORG_ORG_CD` | 外部评估机构组织机构代码 | VARCHAR |  |  |
| `EXT_EVAL_ORG_NAM` | 外部评估机构名称 | VARCHAR |  |  |
| `EVAL_OPR_ORG_NO` | 评估操作机构编号 | VARCHAR |  |  |
| `EVAL_OPR_DAT` | 评估操作日期 | VARCHAR |  |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `AST_NO` | 资产编号 | VARCHAR | 是 |  |
| `PROP_OWNR_CUST_NO` | 产权人客户编号 | VARCHAR | 是 |  |
| `LN_CTRT_NO` | 合同编号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `APR_BAT_NO` | 审批批次号 | INT |  |  |
| `CORE_LN_CTRT_NO` | 合同正本编号 | VARCHAR |  |  |
| `COPRT_BREED_NO` | 合作品种编号 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USG` | 借款用途 | VARCHAR |  |  |
| `COPRT_ITEM_NO` | 合作项目编号 | VARCHAR |  |  |
| `COPRT_ITEM_NAM` | 合作项目名称 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `BUS_ATCH_BAR_LINE_CD` | 部门归属 | VARCHAR |  |  |
| `CTRT_CLS_CD` | 合同种类 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `TGTR_APR_IND` | 是否一并审批 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险 | VARCHAR |  |  |
| `LOW_RSK_BUS_CTG_CD` | 低风险业务类别 | VARCHAR |  |  |
| `CTRT_AMT` | 借款金额 | DECIMAL |  |  |
| `CTRT_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `PRVD_TRMN_DAT` | 发放终止日期 | VARCHAR |  |  |
| `SIGD_DAT` | 签约日期 | VARCHAR |  |  |
| `CTRT_STS_CD` | 合同状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_FLOW_STS_IND` | 放款流程状态标志 | VARCHAR |  |  |
| `CUST_REG_BNK` | 申请人开户银行 | VARCHAR |  |  |
| `DISB_ORG_NO` | 经营机构C4机构编码 | VARCHAR |  |  |
| `DISB_ORG_NO_STD` | 经营机构EIMO机构编码 | VARCHAR |  |  |
| `PROP_OWNR_STARTDT` | 产权开始日期 | VARCHAR |  |  |
| `SIGD_CTRT_PROP_HODG_DAYS` | 签约合同时产权持有天数 | INT |  |  |
| `PROP_OWNR_ENDDT` | 产权结束日期 | VARCHAR |  |  |
| `PROP_OWNR_AVA_CD` | 产权有效性代码 | VARCHAR |  |  |
| `PROP_OWNR_TYP_CD` | 产权类型代码 | VARCHAR |  |  |
| `PROP_OWNR_SHR` | 产权份额（%） | DECIMAL |  |  |
| `COMP_PROJ_DAT` | 竣工日期 | VARCHAR |  |  |
| `COMP_PROJ_DAT_SIGD_CTRT_DAYS` | 竣工日期距合同签约日期天数 | INT |  |  |
| `BULD_OVRGRD_LVL` | 建筑物地上层数 | INT |  |  |
| `BULD_UNDGRD_LVL` | 建筑物地下层数 | INT |  |  |
| `HOUSE_LOCT_ACT_FLR` | 房屋所在实际楼层 | INT |  |  |
| `HOUSE_LOCT_NOM_FLR` | 房屋所在名义楼层 | INT |  |  |
| `TOP_LVL_IND` | 是否顶层 | VARCHAR |  |  |
| `NEXT_TOP_LVL_IND` | 是否次顶层 | VARCHAR |  |  |
| `EVAL_VLU` | 评估价值 | DECIMAL |  |  |
| `EVAL_BASE_DAT` | 评估基准日期 | VARCHAR |  |  |
| `EVAL_VALD_MATU_DAT` | 评估有效到期日期 | VARCHAR |  |  |
| `MGG_BGN_EVAL_TIME` | 抵押物初始评估时间 | VARCHAR |  |  |
| `MGG_BGN_EVAL_VLU` | 抵押物初始评估价值 ( 元 ) | DECIMAL |  |  |
| `MGG_BGN_LTST_TIME` | 抵押物最新评估时间 | VARCHAR |  |  |
| `MGG_BGN_LTST_VLU` | 抵押物最新评估价值 ( 元 ) | DECIMAL |  |  |
| `MGG_BGN_EXT_QRY_TIME` | 抵押物初始外部查询时间 | VARCHAR |  |  |
| `MGG_BGN_EXT_QRY_VLU` | 抵押物初始外部查询价值 ( 元 ) | DECIMAL |  |  |
| `MGG_LTST_EXT_QRY_TIME` | 抵押物最新外部查询时间 | VARCHAR |  |  |
| `MGG_LTST_EXT_QRY_VLU` | 抵押物最新外部查询价值 ( 元 ) | DECIMAL |  |  |
| `MGG_VLU_REF_NO_IND` | 抵押物价值高评参考标识 | VARCHAR |  |  |
| `EVAL_MTHD_1_CD` | 评估方法1代码 | VARCHAR |  |  |
| `EVAL_MTHD_2_CD` | 评估方法2代码 | VARCHAR |  |  |
| `EVAL_MOD_CD` | 评估方式代码 | VARCHAR |  |  |
| `EVAL_EVT_SOR_CD` | 评估结果来源代码 | VARCHAR |  |  |
| `EXT_EVAL_ORG_ORG_CD` | 外部评估机构组织机构代码 | VARCHAR |  |  |
| `EXT_EVAL_ORG_NAM` | 外部评估机构名称 | VARCHAR |  |  |
| `EVAL_OPR_ORG_NO` | 评估操作机构编号 | VARCHAR |  |  |
| `EVAL_OPR_DAT` | 评估操作日期 | VARCHAR |  |  |

### `S_00PL_IDV_LN_GRTE_RLN`（个人贷款担保关系，19 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `MAIN_CTRT_NO` | 主合同编号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR |  |  |
| `LN_AMT_COV_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `MAIN_CTRT_GRTE` | 主合同担保方式 | VARCHAR |  |  |
| `GRTE_CTRT_NO` | 担保合同编号 | VARCHAR | 是 |  |
| `GRTE_CTRT_AMT_COV_RMB` | 担保合同金额折人民币 | DECIMAL |  |  |
| `GRTE_CTRT_GRTE` | 担保合同担保方式 | VARCHAR |  |  |
| `GRTR_CD` | 保证人代码 | VARCHAR | 是 |  |
| `GRTR_GRTE` | 保证人担保方式 | VARCHAR |  |  |
| `GRTR_GRTE_AMT_COV_RMB` | 保证人担保金额折人民币 | DECIMAL |  |  |
| `MGG_AST_NO` | 担保物资产编号 | VARCHAR | 是 |  |
| `MGG_GRTE` | 担保物担保方式 | VARCHAR |  |  |
| `MGG_INSE_AMT` | 担保物参保金额 | DECIMAL |  |  |
| `PLGE_PROP_OWNR_CUST_CD` | 押品产权人客户代码 | VARCHAR | 是 |  |
| `PLGE_PROP_OWNR_NAM` | 押品产权人名称 | VARCHAR |  |  |
| `PLGE_PROP_TYP` | 押品产权类型 | VARCHAR |  |  |
| `PLGE_PROP_SHR` | 押品产权份额 | DECIMAL |  |  |

### `G_00PF_PEAS_LN_LSTY_VCH_CONT_SITU_INFO`（农户贷款上年末凭证本年接续情况信息表，13 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CUST_NO` | 客户编号 | VARCHAR |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `ADJ_MATU_DAT` | 调整后到期日 | VARCHAR |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `CAN_STS_CD` | 核销状态代码 | VARCHAR |  |  |
| `CONTINUE_FLAG` | 后手凭证接续方式 | VARCHAR |  |  |
| `VCH_DISB_ORG_NO` | 凭证放款机构C4机构编码 | VARCHAR |  |  |
| `CTRT_ADMI_ORG_NO` | 合同经营机构C4机构编码 | VARCHAR |  |  |

### `G_00PF_IDV_LN_VCH_CAN_LQDT_SECS_DV`（个人贷款凭证核销清收证券化拼接表，236 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `LN_FORM_ORI_NO` | 借款凭证原始号码 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USE_CD` | 借款用途 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `GRTE_CTRT_NO` | 担保合同编号 | VARCHAR |  |  |
| `LN_USE_CLS_CD` | 借款用途分类 | VARCHAR |  |  |
| `LN_CMPHSV_CLS_CD` | 贷款综合分类 | VARCHAR |  |  |
| `LN_IVST_DIRE_OCPCLS_CD` | 贷款投向行业分类 | VARCHAR |  |  |
| `LN_IVDIR_NATECO_OCPCLS_CD` | 贷款投向国民经济行业分类 | VARCHAR |  |  |
| `PBC_ARGI_LN_CLS_CD` | 人行涉农贷款分类 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险业务 | VARCHAR |  |  |
| `RSK_BUS_CTG` | 低风险业务类别 | VARCHAR |  |  |
| `CYC_LN_IND` | 是否可循环贷款 | VARCHAR |  |  |
| `SUBSD_INTS_LN_IND` | 是否贴息贷款 | VARCHAR |  |  |
| `SUBSD_INTS_END_DAT` | 贴息截止日期 | VARCHAR |  |  |
| `SUBSD_INTS_RATE` | 贴息率 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `ADJ_MATU_DAT` | 调整后到期日 | VARCHAR |  |  |
| `ACTNG_ENT_ACCT_DAT` | 会计入账日期 | VARCHAR |  |  |
| `RNEW_APTMT_IND` | 展期约期标识 | VARCHAR |  |  |
| `RNEW_MATU_DAT` | 展期到期日 | VARCHAR |  |  |
| `RPAY_MOD_CD` | 还款方式 | VARCHAR |  |  |
| `CCY_CD` | 币种 | VARCHAR |  |  |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `LN_AMT` | 借款金额 | DECIMAL |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL` | 凭证余额 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `IN_BLNC_ARREA_INTS` | 表内欠息 | DECIMAL |  |  |
| `OFF_BLNC_ARREA_INTS` | 表外欠息 | DECIMAL |  |  |
| `RSK_CLS_CD` | 风险分类 | VARCHAR |  |  |
| `INTL_GRD_CLS_CD` | 内部评级分类 | VARCHAR |  |  |
| `YEAR_AVER_RPAMT` | 年化平均还款额 | DECIMAL |  |  |
| `FST_FORM_NO` | 首笔凭证编号 | VARCHAR |  |  |
| `FST_FORM_PRVD_DAT` | 首笔凭证发放日期 | VARCHAR |  |  |
| `ABIS_BRCH_NO` | ABIS机构编码 | VARCHAR |  |  |
| `ABIS_BUS_BREED` | ABIS业务品种 | VARCHAR |  |  |
| `LN_ACCT_NO` | 贷款账号 | VARCHAR |  |  |
| `RPAY_TYP_CD` | 还款类型 | VARCHAR |  |  |
| `WON_AUTO_DDCT_CAP` | 是否自动扣收本金 | VARCHAR |  |  |
| `AUTO_DDCT_CAP_STRT_AMT` | 自动扣收本金起点金额 | DECIMAL |  |  |
| `CLTN_ACCT_NO` | 收款账号 | VARCHAR |  |  |
| `RPAY_ACCT_NO_1` | 还款账号1 | VARCHAR |  |  |
| `RPAY_ACCT_NO_2` | 还款账号2 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO` | 自由还账号 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO_RETQUOT` | 自由还账号留存额度 | DECIMAL |  |  |
| `PRGS_TLMT_MSG_DAT` | 诉讼时效提示日期 | VARCHAR |  |  |
| `DISB_FLOW_STS_CD` | 放款流程状态标志 | VARCHAR |  |  |
| `FORM_STS_CD` | 凭证状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_ORG_COD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_ORG_COD_STD` | 放款机构EIMO机构编码 | VARCHAR |  |  |
| `REG_MAGR_CD` | 建档客户经理代码 | VARCHAR |  |  |
| `MAGR_CD` | 首贷客户经理代码 | VARCHAR |  |  |
| `OPR_ORG_COD` | 操作机构C4机构编码 | VARCHAR |  |  |
| `OPR_EIMO_ORG_COD` | 操作机构EIMO机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `FST_OPR_DAT` | 首次操作日期 | VARCHAR |  |  |
| `FST_OPR_TIME` | 首次操作时间 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `AGENT_CTG_CD` | 委托人类别 | VARCHAR |  |  |
| `DPRT_FTR_CLS_CD` | 部门特色分类 | VARCHAR |  |  |
| `FRN_EXCH_PLGE_LN_CLS_CD` | 外汇保证贷款分类 | VARCHAR |  |  |
| `CLTN_PSN_ISBN` | 收款人代码 | VARCHAR |  |  |
| `MARG_CTRL_IND` | 是否控制保证金 | VARCHAR |  |  |
| `MARG_CTRL_MOD_CD` | 保证金控制方式 | VARCHAR |  |  |
| `MARG_CTRL_PPTN` | 保证金控制比例 | DECIMAL |  |  |
| `MARG_FIX_QUOT` | 保证金固定额度 | DECIMAL |  |  |
| `MARG_CCY_CD` | 保证金币种 | VARCHAR |  |  |
| `SELF_LOWT_RPAY_QUOT` | 自由还最低还款额度 | DECIMAL |  |  |
| `SELF_HGST_RPAY_QUOT` | 自由还最高还款额度 | DECIMAL |  |  |
| `FNC_PROD_CLS_CD` | 信贷产品分类 | VARCHAR |  |  |
| `PAY_MOD_CD` | 支付方式代码 | VARCHAR |  |  |
| `NTRL_DSTR_EFCT_CD` | 自然灾害影响代码 | VARCHAR |  |  |
| `EXD_DAT` | 逾期日期 | VARCHAR |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_TYP` | 逾期类型 | VARCHAR |  |  |
| `BASE_DAY_DAT` | 证券化基准日日期 | VARCHAR |  |  |
| `BASE_JP_GOLD_BAL_RMB` | 证券化本金 | DECIMAL |  |  |
| `BASE_DAY_INTS_RMB` | 证券化利息 | DECIMAL |  |  |
| `CAN_ACTNG_DAT` | 核销会计日期 | VARCHAR |  |  |
| `CAN_STS_CD` | 核销状态代码 | VARCHAR |  |  |
| `CAN_CAP` | 核销本金 | DECIMAL |  |  |
| `CAN_INTS` | 核销利息 | DECIMAL |  |  |
| `CHG_CAP_1_YAVER` | 当年表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_1_YAVER` | 当年表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_1_YAVER` | 近12个月表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_12_MONTH` | 近12个月表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_12_MONTH` | 近12个月表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_12_MONTH` | 近4个自然年表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_4_YAVER` | 近4个自然年表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_4_YAVER` | 近4个自然年表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_4_YAVER` | 累计表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_TOT` | 累计表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_TOT` | 累计表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_TOT` | 累计现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_1_YAVER` | 当年表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_1_YAVER` | 当年表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_1_YAVER` | 当年表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_12_MONTH` | 近12个月表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_12_MONTH` | 近12个月表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_12_MONTH` | 近12个月表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_4_YAVER` | 近4个自然年表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_4_YAVER` | 近4个自然年表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_4_YAVER` | 近4个自然年表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_TOT` | 累计表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_TOT` | 累计表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_TOT` | 累计表外现金清收本息合计 | DECIMAL |  |  |
| `DAT_SOR_CD` | 数据来源代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `FORM_NO` | 凭证编号 | VARCHAR | 是 |  |
| `CTRT_NO` | 合同编号 | VARCHAR |  |  |
| `CUST_NO` | 客户编码 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `LN_FORM_ORI_NO` | 借款凭证原始号码 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  |  |
| `LN_USE_CD` | 借款用途 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `GRTE_CTRT_NO` | 担保合同编号 | VARCHAR |  |  |
| `LN_USE_CLS_CD` | 借款用途分类 | VARCHAR |  |  |
| `LN_CMPHSV_CLS_CD` | 贷款综合分类 | VARCHAR |  |  |
| `LN_IVST_DIRE_OCPCLS_CD` | 贷款投向行业分类 | VARCHAR |  |  |
| `LN_IVDIR_NATECO_OCPCLS_CD` | 贷款投向国民经济行业分类 | VARCHAR |  |  |
| `PBC_ARGI_LN_CLS_CD` | 人行涉农贷款分类 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险业务 | VARCHAR |  |  |
| `RSK_BUS_CTG` | 低风险业务类别 | VARCHAR |  |  |
| `CYC_LN_IND` | 是否可循环贷款 | VARCHAR |  |  |
| `SUBSD_INTS_LN_IND` | 是否贴息贷款 | VARCHAR |  |  |
| `SUBSD_INTS_END_DAT` | 贴息截止日期 | VARCHAR |  |  |
| `SUBSD_INTS_RATE` | 贴息率 | DECIMAL |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `ADJ_MATU_DAT` | 调整后到期日 | VARCHAR |  |  |
| `ACTNG_ENT_ACCT_DAT` | 会计入账日期 | VARCHAR |  |  |
| `RNEW_APTMT_IND` | 展期约期标识 | VARCHAR |  |  |
| `RNEW_MATU_DAT` | 展期到期日 | VARCHAR |  |  |
| `RPAY_MOD_CD` | 还款方式 | VARCHAR |  |  |
| `CCY_CD` | 币种 | VARCHAR |  |  |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `LN_AMT` | 借款金额 | DECIMAL |  |  |
| `LN_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `FORM_BAL` | 凭证余额 | DECIMAL |  |  |
| `FORM_BAL_RMB` | 凭证余额折人民币 | DECIMAL |  |  |
| `IN_BLNC_ARREA_INTS` | 表内欠息 | DECIMAL |  |  |
| `OFF_BLNC_ARREA_INTS` | 表外欠息 | DECIMAL |  |  |
| `RSK_CLS_CD` | 风险分类 | VARCHAR |  |  |
| `INTL_GRD_CLS_CD` | 内部评级分类 | VARCHAR |  |  |
| `YEAR_AVER_RPAMT` | 年化平均还款额 | DECIMAL |  |  |
| `FST_FORM_NO` | 首笔凭证编号 | VARCHAR |  |  |
| `FST_FORM_PRVD_DAT` | 首笔凭证发放日期 | VARCHAR |  |  |
| `ABIS_BRCH_NO` | ABIS机构编码 | VARCHAR |  |  |
| `ABIS_BUS_BREED` | ABIS业务品种 | VARCHAR |  |  |
| `LN_ACCT_NO` | 贷款账号 | VARCHAR |  |  |
| `RPAY_TYP_CD` | 还款类型 | VARCHAR |  |  |
| `WON_AUTO_DDCT_CAP` | 是否自动扣收本金 | VARCHAR |  |  |
| `AUTO_DDCT_CAP_STRT_AMT` | 自动扣收本金起点金额 | DECIMAL |  |  |
| `CLTN_ACCT_NO` | 收款账号 | VARCHAR |  |  |
| `RPAY_ACCT_NO_1` | 还款账号1 | VARCHAR |  |  |
| `RPAY_ACCT_NO_2` | 还款账号2 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO` | 自由还账号 | VARCHAR |  |  |
| `SELF_RPAY_ACCT_NO_RETQUOT` | 自由还账号留存额度 | DECIMAL |  |  |
| `PRGS_TLMT_MSG_DAT` | 诉讼时效提示日期 | VARCHAR |  |  |
| `DISB_FLOW_STS_CD` | 放款流程状态标志 | VARCHAR |  |  |
| `FORM_STS_CD` | 凭证状态 | VARCHAR |  |  |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_ORG_COD` | 放款机构C4机构编码 | VARCHAR |  |  |
| `DISB_ORG_COD_STD` | 放款机构EIMO机构编码 | VARCHAR |  |  |
| `REG_MAGR_CD` | 建档客户经理代码 | VARCHAR |  |  |
| `MAGR_CD` | 首贷客户经理代码 | VARCHAR |  |  |
| `OPR_ORG_COD` | 操作机构C4机构编码 | VARCHAR |  |  |
| `OPR_EIMO_ORG_COD` | 操作机构EIMO机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `FST_OPR_DAT` | 首次操作日期 | VARCHAR |  |  |
| `FST_OPR_TIME` | 首次操作时间 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `AGENT_CTG_CD` | 委托人类别 | VARCHAR |  |  |
| `DPRT_FTR_CLS_CD` | 部门特色分类 | VARCHAR |  |  |
| `FRN_EXCH_PLGE_LN_CLS_CD` | 外汇保证贷款分类 | VARCHAR |  |  |
| `CLTN_PSN_ISBN` | 收款人代码 | VARCHAR |  |  |
| `MARG_CTRL_IND` | 是否控制保证金 | VARCHAR |  |  |
| `MARG_CTRL_MOD_CD` | 保证金控制方式 | VARCHAR |  |  |
| `MARG_CTRL_PPTN` | 保证金控制比例 | DECIMAL |  |  |
| `MARG_FIX_QUOT` | 保证金固定额度 | DECIMAL |  |  |
| `MARG_CCY_CD` | 保证金币种 | VARCHAR |  |  |
| `SELF_LOWT_RPAY_QUOT` | 自由还最低还款额度 | DECIMAL |  |  |
| `SELF_HGST_RPAY_QUOT` | 自由还最高还款额度 | DECIMAL |  |  |
| `FNC_PROD_CLS_CD` | 信贷产品分类 | VARCHAR |  |  |
| `PAY_MOD_CD` | 支付方式代码 | VARCHAR |  |  |
| `NTRL_DSTR_EFCT_CD` | 自然灾害影响代码 | VARCHAR |  |  |
| `EXD_DAT` | 逾期日期 | VARCHAR |  |  |
| `EXD_DAYS` | 逾期天数 | INT |  |  |
| `EXD_TYP` | 逾期类型 | VARCHAR |  |  |
| `BASE_DAY_DAT` | 证券化基准日日期 | VARCHAR |  |  |
| `BASE_JP_GOLD_BAL_RMB` | 证券化本金 | DECIMAL |  |  |
| `BASE_DAY_INTS_RMB` | 证券化利息 | DECIMAL |  |  |
| `CAN_ACTNG_DAT` | 核销会计日期 | VARCHAR |  |  |
| `CAN_STS_CD` | 核销状态代码 | VARCHAR |  |  |
| `CAN_CAP` | 核销本金 | DECIMAL |  |  |
| `CAN_INTS` | 核销利息 | DECIMAL |  |  |
| `CHG_CAP_1_YAVER` | 当年表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_1_YAVER` | 当年表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_1_YAVER` | 近12个月表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_12_MONTH` | 近12个月表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_12_MONTH` | 近12个月表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_12_MONTH` | 近4个自然年表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_4_YAVER` | 近4个自然年表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_4_YAVER` | 近4个自然年表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_4_YAVER` | 累计表内现金清收本金 | DECIMAL |  |  |
| `CHG_CAP_TOT` | 累计表内现金清收利息 | DECIMAL |  |  |
| `CHG_INTS_TOT` | 累计表内现金清收本息合计 | DECIMAL |  |  |
| `CHG_AMT_TOT` | 累计现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_1_YAVER` | 当年表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_1_YAVER` | 当年表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_1_YAVER` | 当年表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_12_MONTH` | 近12个月表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_12_MONTH` | 近12个月表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_12_MONTH` | 近12个月表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_4_YAVER` | 近4个自然年表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_4_YAVER` | 近4个自然年表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_4_YAVER` | 近4个自然年表外现金清收本息合计 | DECIMAL |  |  |
| `CHG_OFF_BLNC_CAP_TOT` | 累计表外现金清收本金 | DECIMAL |  |  |
| `CHG_OFF_BLNC_INTS_TOT` | 累计表外现金清收利息 | DECIMAL |  |  |
| `CHG_OFF_BLNC_AMT_TOT` | 累计表外现金清收本息合计 | DECIMAL |  |  |
| `DAT_SOR_CD` | 数据来源代码 | VARCHAR | 是 |  |

### `B_00DT_CYC_QUOT_INFO_H`（循环额度信息历史，47 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体编号 | VARCHAR | 是 |  |
| `LN_CTRT_NO` | 借款合同编号 | VARCHAR | 是 |  |
| `ABIS_FNCG_CARD_NO` | ABIS理财卡号/账号 | VARCHAR |  |  |
| `QUOT_CLS` | 额度种类 | VARCHAR |  |  |
| `CYC_QUOT` | 循环额度 | DECIMAL |  |  |
| `QUOT_StartDt` | 额度开始日期 | VARCHAR |  |  |
| `QUOT_MATU_DAT` | 额度到期日期 | VARCHAR |  |  |
| `SGGT_LN_LNGST_TERM` | 单笔贷款最长期限 | VARCHAR |  |  |
| `SGGT_AD_LN_LNGST_TERM` | 单笔自助贷款最长期限 | VARCHAR |  |  |
| `SGGT_AD_LN_SHTST_TERM` | 单笔自助贷款最短期限 | VARCHAR |  |  |
| `SGGT_LN_LAST_MATU_DAT` | 单笔贷款最后到期日期 | VARCHAR |  |  |
| `ONE_ANNL_ABV_LN_RPAY_MOD` | 一年以上贷款还款方式 | VARCHAR |  |  |
| `ONE_ANNL_ABV_RPAY_TYP` | 一年以上还款类型 | VARCHAR |  |  |
| `ONE_ANNL_WITHIN_LN_RPAY_MOD` | 一年以内贷款还款方式 | VARCHAR |  |  |
| `ONE_ANNL_WITHIN_RPAY_TYP` | 一年以内还款类型 | VARCHAR |  |  |
| `ONE_ANNL_DAY_WITHIN_LN_ITST_BRNG_MOD` | 一年期以内贷款计息方式 | VARCHAR |  |  |
| `ONE_ANNL_DAY_ABV_LN_ITST_BRNG_MOD` | 一年期以上贷款计息方式 | VARCHAR |  |  |
| `NML_RATE_FLT_MOD` | 正常利率浮动方式 | VARCHAR |  |  |
| `NML_RATE_FLT_RGE` | 正常利率浮动幅度 | DECIMAL |  |  |
| `EXP_RATE_FLT_MOD` | 超期利率浮动方式 | VARCHAR |  |  |
| `EXP_RATE_FLT_RGE` | 超期利率浮动幅度 | DECIMAL |  |  |
| `ONE_ANNL_WITHIN_LN_INTS_PERD` | 一年以内贷款结息周期 | VARCHAR |  |  |
| `RPAY_PERD` | 还款周期 | VARCHAR |  |  |
| `SETL_INTS_PERD` | 结息周期 | VARCHAR |  |  |
| `ONE_ANNL_WITHIN_LN_INTS_DAY` | 一年以内贷款定期结息日 | VARCHAR |  |  |
| `ONE_ANNL_ABV_LN_RPDAY` | 一年以上贷款还款日 | VARCHAR |  |  |
| `AD_IND` | 自助标志 | VARCHAR |  |  |
| `AD_QUOT` | 自助额度 | DECIMAL |  |  |
| `AD_QUOT_OCCP_IND` | 自助额度可占用标志 | VARCHAR |  |  |
| `USG_AD_QUOT` | 已用自助额度 | DECIMAL |  |  |
| `AVL_AD_QUOT` | 可用自助额度 | DECIMAL |  |  |
| `WON_BUND_CLTN` | 是否绑定收款方 | VARCHAR |  |  |
| `STRT_BASE_AMT` | 起贷基础金额 | DECIMAL |  |  |
| `LN_AMPL_BASE_NUM` | 贷款增幅基础数 | DECIMAL |  |  |
| `SSUB_ACCT_NO_QUOT_PPTN` | 专用子账户额度比例 | DECIMAL |  |  |
| `QUOT_STS` | 额度状态 | VARCHAR |  |  |
| `CTRT_GRP_NO` | 合同组编号 | VARCHAR |  |  |
| `SIGD_ABIS_BRCH_NO` | ABIS签约机构编码 | VARCHAR |  |  |
| `OPR_ORG_COD` | 操作机构编码 | VARCHAR |  |  |
| `OPR_ORG_COD_EIMO` | 操作EIMO机构编码 | VARCHAR |  |  |
| `OPT_CD` | 操作员代码 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `SYS_SOR_CD` | 系统来源代码 | VARCHAR | 是 |  |
| `StartDt` | 开始日期 | DATE | 是 |  |
| `EndDt` | 结束日期 | DATE |  |  |
| `ValidDt` | 有效日期 | DATE |  |  |
| `Timestamp` | 时间戳 | DATETIME |  |  |

### `G_00PF_IDV_LN_CTRT_DV`（个人贷款合同全量拼接表，66 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `FNCL_ENT_NO` | 金融实体代码 | VARCHAR | 是 |  |
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `LN_CTRT_NO` | 合同编号 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR |  |  |
| `REQSI_NO` | 申请书编号 | VARCHAR |  |  |
| `APR_BAT_NO` | 审批批次号 | INT |  |  |
| `CORE_LN_CTRT_NO` | 合同正本编号 | VARCHAR |  |  |
| `COPRT_BREED_NO` | 合作品种编号 | VARCHAR |  |  |
| `LN_PROP_CLS_CD` | 贷款性质分类 | VARCHAR |  |  |
| `LN_TERM_CLS_CD` | 贷款期限分类 | VARCHAR |  | 1-短期贷款
2-中期贷款
3-长期贷款
101-短期流动资金贷款
102-其他 |
| `LN_USG` | 借款用途 | VARCHAR |  |  |
| `COPRT_ITEM_NO` | 合作项目编号 | VARCHAR |  |  |
| `COPRT_ITEM_NAM` | 合作项目名称 | VARCHAR |  |  |
| `BUS_BREED_CD` | 业务品种 | VARCHAR |  |  |
| `BUS_ATCH_BAR_LINE_CD` | 部门归属 | VARCHAR |  | 1-公司类
2-零售类
3-三农类
4-机构类
5-资产处置类
6-信用卡中心
 |
| `CTRT_CLS_CD` | 合同种类 | VARCHAR |  |  |
| `GRTE_MOD_CD` | 担保方式 | VARCHAR |  |  |
| `TGTR_APR_IND` | 是否一并审批 | VARCHAR |  |  |
| `LOW_RSK_BUS_IND` | 是否低风险 | VARCHAR |  |  |
| `LOW_RSK_BUS_CTG_CD` | 低风险业务类别 | VARCHAR |  |  |
| `CYC_LN_IND` | 是否可循环贷款 | VARCHAR |  |  |
| `WON_HAVE_COM_BROW` | 是否有共同借款人 | VARCHAR |  |  |
| `SUBSD_INTS_LN_IND` | 是否贴息贷款 | VARCHAR |  |  |
| `SUBSD_INTS_RATE` | 贴息率 | DECIMAL |  |  |
| `SUBSD_INTS_END_DAT` | 贴息截止日期 | VARCHAR |  |  |
| `CCY_CD` | 币种 | VARCHAR |  | 01-人民币
12-英镑
13-港币
14-美元
27-日元
29-澳元
38- |
| `CCY_CD_STD` | 币种_标准化 | VARCHAR |  |  |
| `PRVD_LN_MMNT_EXCG` | 发放贷款时汇率 | DECIMAL |  |  |
| `CYC_QUOT` | 循环额度 | DECIMAL |  |  |
| `QUOT_STARTDT` | 循环额度开始日期 | VARCHAR |  |  |
| `QUOT_MATU_DAT` | 循环额度到期日期 | VARCHAR |  |  |
| `CTRT_AMT` | 借款金额 | DECIMAL |  |  |
| `CTRT_AMT_RMB` | 借款金额折人民币 | DECIMAL |  |  |
| `USG_AMT` | 已用金额 | DECIMAL |  |  |
| `CUST_CAN_AMT` | 客户撤销金额 | DECIMAL |  |  |
| `AVL_AMT` | 可用金额 | DECIMAL |  |  |
| `DWN_PAMT_AMT` | 首付款 | DECIMAL |  |  |
| `DWN_PAMT_AMT_PPTN` | 首付款比例 | DECIMAL |  |  |
| `CTRT_NONSQUA_VCH_CNT` | 合同下未结清凭证数 | INT |  |  |
| `CTRT_NONSQUA_RSK_VCH_CNT` | 合同下未结清风险凭证数 | INT |  |  |
| `CTRT_HGST_CR_USE_AMT` | 合同历史最高用信金额 | DECIMAL |  |  |
| `CTRT_TOT_CR_USE_NUM` | 合同累计用信笔数 | INT |  |  |
| `LN_DAT` | 借款日期 | VARCHAR |  |  |
| `MATU_DAT` | 到期日期 | VARCHAR |  |  |
| `PRVD_TRMN_DAT` | 发放终止日期 | VARCHAR |  |  |
| `TOLE_MOD_CD` | 宽限方式 | VARCHAR |  |  |
| `TOLE_TERM` | 宽限期数 | INT |  |  |
| `PPERD_RPDAY` | 每期还款日 | VARCHAR |  |  |
| `RPAY_MOD_CD` | 还款方式 | VARCHAR |  | 1-一次性利随本清还款
2-一次性还本按约还息
3-自订计划分期还款
4-等额本 |
| `ITST_BRNG_MOD_CD` | 计息方式 | VARCHAR |  | G-宽限计息
N-免息
U-无条件计息 |
| `DIV_DAY_RPAY_PERD_CD` | 分期还款周期标志 | VARCHAR |  |  |
| `CTRT_CNT` | 合同份数 | INT |  |  |
| `SIGD_DAT` | 签约日期 | VARCHAR |  |  |
| `CTRT_STS_CD` | 合同状态 | VARCHAR |  | 01-已登记
02-生效
03-自动冻结
04-手工冻结
05-变更中
06-履 |
| `DEL_IND` | 删除标志 | VARCHAR |  |  |
| `DISB_FLOW_STS_IND` | 放款流程状态标志 | VARCHAR |  |  |
| `CUST_REG_BNK` | 申请人开户银行 | VARCHAR |  |  |
| `DISB_ORG_NO` | 经营机构编码 | VARCHAR |  |  |
| `DISB_ORG_NO_STD` | 经营机构编码_标准化 | VARCHAR |  |  |
| `MAGR_NO` | 客户经理代码 | VARCHAR |  |  |
| `OPR_ORG_NO` | 操作机构编码 | VARCHAR |  |  |
| `OPR_ORG_NO_STD` | 操作机构编码_标准化 | VARCHAR |  |  |
| `OPT_NO` | 操作员代码 | VARCHAR |  |  |
| `FST_OPR_DAT` | 首次操作日期 | VARCHAR |  |  |
| `OPR_DAT` | 操作日期 | VARCHAR |  |  |
| `DAT_SOR_CD` | 数据来源代码 | VARCHAR | 是 |  |

### `G_00PF_PEAS_LN_FMLY_SITU_INFO`（农户贷款客户家庭村居情况信息表，10 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `DATA_DAT` | 数据日期 | VARCHAR | 是 |  |
| `CUST_NO` | 客户编号 | VARCHAR | 是 |  |
| `ID_CARD_NO` | 身份证号码 | VARCHAR |  |  |
| `MRGE_STS` | 婚姻状况 | VARCHAR |  |  |
| `OWN_RURA_ID` | 所属村编号 | VARCHAR |  |  |
| `ADMI_RURA_ATCH_ORG_NO` | 行政村归属机构C4机构编码 | VARCHAR |  |  |
| `ADMI_RURA_ATCH_EIMO_ORG_NO` | 行政村归属机构EIMO机构编码 | VARCHAR |  |  |
| `VALD_PEAS_LN_CUST_CNT` | 所属村持有效农贷合同的客户数 | INT |  |  |
| `ATCH_MAGR_CRT_CUST_CNT` | 所属建档客户经理当天建档客户数 | INT |  |  |
| `ATCH_MAGR_12_CRT_CUST_CNT` | 所属建档客户经理当天建档且建档一年内有合同的客户数 | INT |  |  |

### `P_00FAS_GFAS_VAF_LOAN_MANAGE`（联村带户贷款信息状态明细，46 字段）

| 字段 | 中文名 | 类型 | 主键 | 取值信息 |
|---|---|---|---|---|
| `SERNO` | 流水号 | VARCHAR |  |  |
| `APPLICANT_ID` | 申请书编号 | VARCHAR |  |  |
| `IDCARD` | 身份证号 | VARCHAR |  |  |
| `NAME` | 名称 | VARCHAR |  |  |
| `MOBILE_NUM` | 移动电话 | VARCHAR |  |  |
| `RESIDENT_ADDR` | 常住地址 | VARCHAR |  |  |
| `VG_ID` | 所属村编号 | VARCHAR |  |  |
| `VG_NAME` | 所属村名称 | VARCHAR |  |  |
| `COLLECT_CHANNEL` | 采集渠道 | VARCHAR |  |  |
| `APPLY_AMT_BASE` | 申请金额 | DECIMAL |  |  |
| `APPLY_DATE` | 申请日期 | VARCHAR |  |  |
| `PRODUCT_WILL` | 意向产品 | VARCHAR |  |  |
| `STATU` | 状态 | VARCHAR |  |  |
| `INVEST_METHOD` | 调查方式 | VARCHAR |  |  |
| `CHECK_STATUS` | 抽查情况 | VARCHAR |  |  |
| `WF_STATUS` | 流程状态 | VARCHAR |  |  |
| `MANAGER_ID` | 管户经理 | VARCHAR |  |  |
| `MANAGER_NAME` | 管户经理姓名 | VARCHAR |  |  |
| `CLAIM_BRANCH_CODE` | 指派给所属机构id | VARCHAR |  |  |
| `CLAIM_BRANCH_NAME` | 指派给所属机构名称 | VARCHAR |  |  |
| `CLAIM_TIME` | 认领时间 | VARCHAR |  |  |
| `OPR_ID` | 操作员（主管客户经理）代码 | VARCHAR |  |  |
| `OPR_NAME` | 操作员名称 | VARCHAR |  |  |
| `OPR_DATE` | 操作日期 | VARCHAR |  |  |
| `OPR_TIME` | 操作时间 | VARCHAR |  |  |
| `OPR_INST_ID` | 操作机构代码 | VARCHAR |  |  |
| `OPR_INST_NAME` | 操作机构名称 | VARCHAR |  |  |
| `OPR_RINSTCODE` | 操作人所属行代码 | VARCHAR |  |  |
| `OPR_RINSTNAME` | 操作人所属行名称 | VARCHAR |  |  |
| `OPRT_TYPE` | 操作类型 | VARCHAR |  |  |
| `DATA_IN_DATE` | 入库时间 | VARCHAR |  |  |
| `AREA_CODE` | 行政区划 | VARCHAR |  |  |
| `INST_ADDR` | 机构地址 | VARCHAR |  |  |
| `INST_PHONE` | 机构电话 | VARCHAR |  |  |
| `MANAGER_PHONE` | 管户经理电话 | VARCHAR |  |  |
| `CONTNO` | 合同号 | VARCHAR |  |  |
| `PERIOD` | 贷款期限 | DECIMAL |  |  |
| `IS_SAVED` | 是否已保存 | VARCHAR |  |  |
| `C4_STATUS` | C4审批状态 | VARCHAR |  |  |
| `C4_STATUS_UPDDATE` | C4审批状态更新日期 | VARCHAR |  |  |
| `C4_STATUS_UPDTIME` | C4审批状态更新时间 | VARCHAR |  |  |
| `AUTHORITY_TYPE` | 授权类型 | VARCHAR |  |  |
| `AUTHORITY_STATU` | 授权状态 | VARCHAR |  |  |
| `AUTHORITY_TIME` | 授权时间 | VARCHAR |  |  |
| `PROD_FEATURE` | 农户特色标识 | VARCHAR |  |  |
| `addfielddate` | 有效日期 | VARCHAR |  |  |

---

## 五、新增 13 张表关联关系分析（2026-11-06 补录）

> 数据文件由 49 张扩至 **61 张**（+12 张全新 +1 张更名 `B_00DT_CORP_GX_ALTER_DTAL_FXB`）。
> **关键结论：所有新增表的 64 位哈希键与现有 49 张表同体系（SHA-256），可直接 JOIN。**
> 关联键统一 64 位哈希：CUST_NO / ID_CARD_NO / FORM_NO / CUST_CD / CUST_ID / PCT_CSTMNO / PCT_VCHNO / CERT_NO / CERTNO / AST_NO / ENTID_GX 全部同体系。
> 机构键为明文短码：C4_ORG_NO(12位) / ORG_NO(6位) / FNCL_ENT_NO(4位) / EIMO_ORG_NO(6位)。

### 5.1 新增表清单与关联键

| 表名 | 中文名 | 规模 | 主关联键 | 可关联的现有表（键） | 关联结果 |
|---|---|---|---|---|---|
| `B_00DT_APLO_GOHV_ECR_WHT_NAM_FORM_H` | 惠农e贷白名单历史 | 189MB | CUST_ID, CERT_NO | 建档档案 CUST_NO（CUST_ID 命中3202/3万）✅；FAS证件 ID_CARD_NO（CERT_NO 命中8974/5万）✅ | 白名单客户/证件双通道可关联 |
| `B_00DT_CORP_GX_ALTER_DTAL_FXB` | 国信企业历史变更明细（更名） | 4MB | ENTID_GX | 国信企业基本信息 ENTID_GX（同体系）✅ | 企业内部变更明细 |
| `B_00DT_CORP_GX_BASIC_H` | 国信企业基本信息历史 | 90MB | ENTID_GX, CREDITCODE | FAS个体经营 B_00DT_FAS_IDV_BUS_INFO_H（证件/企业名间接）⚠️ | 企业维度，与个人客户弱关联 |
| `B_00DT_FNC_CUST_AST_CERT_PAPR_IN_H` | 押品权证信息历史 | 1MB | AST_NO | 押品产权人 B_00DT_FNC_CUST_AST_AND_PROP_OWNR_RLN_H AST_NO（命中2158/2174）✅ | 押品→权证 1:1 关联 |
| `B_00DT_IDV_RULE_CLUE_H` | 个人规则线索历史 | 166MB | CUST_CD, BUS_NO, LAW_NO | 建档档案 CUST_NO（CUST_CD 命中2868/3万）✅；风险线索处置 BUS_NO/LAW_NO（命中89/29）✅ | 个人规则线索，客户级 |
| `B_00DT_MNG_INFO_CLUE_H` | 个人信贷客户规则线索管理历史 | 65MB | CUST_CD, LAW_NO | 建档档案 CUST_NO（CUST_CD 命中71/3千）✅ | 线索管理，客户级 |
| `G_00PF_COM_ORG_TREE_DV` | 数据中台通用机构树拼接表 | 47MB | ORG_NO | C4机构树 B_00DT_C4_ORG_TREE_H EIMO_ORG_NO（命中612/6671）✅ | 机构树：通用ORG_NO ↔ C4的EIMO_ORG_NO |
| `G_00PF_PEAS_LN_RSK_LINE_DPSE_PROC_INFO` | 农户贷款风险线索处置全过程信息表 | 343MB | CUST_CD, BUS_NO, LAW_NO | 建档档案 CUST_NO（CUST_CD 命中931交集）✅；线索表 BUS_NO/LAW_NO（命中89/29）✅ | 风险线索全过程，客户级 |
| `G_00PL_PEAS_LN_ADDR_CHEK_DV` | 农户贷款客户地址交叉检验信息表 | 155MB | CUST_NO, ID_CARD_NO | 建档档案 CUST_NO（命中3271/3万）✅ | 地址风险，客户+证件双键 |
| `P_00CIE_CPS_INDECATE_COMPLIATEPROCESS` | 个人客户信用报告-复杂加工P3指标 | 97MB | CERTNO | FAS证件 ID_CARD_NO（CERTNO 命中482/1299≈37%，覆盖部分）⚠️ | 征信指标，证件级 |
| `P_00CIE_CPS_INDECATE_DIRECTEXTRA` | 个人客户信用报告-直接提取P1指标 | 104MB | CERTNO | FAS证件 ID_CARD_NO（同上）⚠️ | 征信指标，证件级 |
| `P_00CIE_CPS_INDECATE_SIMPLEPROCESS` | 个人客户信用报告-简单加工P2指标 | 273MB | CERTNO | FAS证件 ID_CARD_NO（同上）⚠️ | 征信指标，证件级 |
| `P_00PMC_PMC_P_CALLTASK` | 个人属地电话催收任务明细 | 697MB | PCT_CSTMNO, PCT_CONTNO, PCT_BECONTNO | 建档档案 CUST_NO（PCT_CSTMNO 命中143/1198）✅；合同 LN_CTRT_NO（PCT_CONTNO 命中183/1754）✅；逾期借据 ARG_NO（PCT_BECONTNO 命中159/2662）✅ | 电话催收，客户+合同+借据三键 |

> ⚠️ 说明：P_00CIE 三表 CERTNO 与 ID_CARD_NO 命中率约 37%（482/1299 抽样），因为征信报告仅覆盖有征信记录的客户子集，**键体系相同但覆盖范围不同**，JOIN 时用 INNER JOIN 取交集即可。

### 5.2 新增表之间的内部关联

| 关联对 | 键 | 结果 |
|---|---|---|
| IDV_RULE_CLUE_H ↔ RSK_LINE_DPSE_PROC_INFO | CUST_CD / BUS_NO / LAW_NO | ✅（命中 52/89/29） |
| IDV_RULE_CLUE_H ↔ MNG_INFO_CLUE_H | CUST_CD | ✅（命中 71） |
| GOHV白名单 ↔ 电话催收 | CUST_ID ↔ PCT_CSTMNO | ✅（命中 73） |
| CIE信用报告 ↔ GOHV白名单 | CERTNO ↔ CERT_NO | ⚠️ 部分（48/390） |
| CORP_GX_BASIC_H ↔ CORP_GX_ALTER_DTAL_FXB | ENTID_GX | ✅ 同体系 |
| COM_ORG_TREE_DV ↔ C4_ORG_TREE_H | ORG_NO ↔ EIMO_ORG_NO | ✅（命中 612） |

### 5.3 特殊关联发现（深挖/SQL 时注意）

1. **`PCT_VCHNO` ≠ 凭证号 FORM_NO**：电话催收的 PCT_VCHNO 与 G_00PF_PEAS_LN_VCH_DV / G_00PF_IDV_LN_VCH_DV 的 FORM_NO **无交集**（0 命中）——不要用 PCT_VCHNO 关联凭证表。
2. **电话催收的正确关联通道**：PCT_CONTNO ↔ 合同 LN_CTRT_NO、PCT_BECONTNO ↔ 逾期 ARG_NO、PCT_CSTMNO ↔ CUST_NO。
3. **上门催收/处置任务/电话催收三张催收类表**：上门(B_00FT_PMC_P_DOORTASK_DTAL)与处置(B_00FT_PEAS_LN_DPSE_TASK_DTAL)已有 CUST_NO 64位；电话催收新增 PCT_CSTMNO 同体系，**可按 CUST_NO 三表合并分析催收力度**。
4. **机构桥接**：通用机构树 ORG_NO（6位）↔ C4机构树 EIMO_ORG_NO（6位）可关联，用于把 S_00PF_PEAS_*_C4 机构级风险表按 ORG_NO 映射到通用机构维度。
5. **押品权证链**：AST_NO 可在 押品产权人 ↔ 权证 之间 1:1 关联（2158/2174 高度重叠），补充押品权证有效期/登记信息。
6. **征信三表（P_00CIE）**：按 CERTNO ↔ ID_CARD_NO JOIN 后，可把 P1/P2/P3 指标（贷记卡特殊交易、单位性质、负债等）拼入客户宽表，是**新客户资质深挖的重要数据源**。
7. **企业表弱关联**：CORP_GX_BASIC_H 是国信企业维度，需通过 FAS_IDV_BUS_INFO_H（个体经营信息，含证件号）间接关联个人客户，不建议直接 JOIN。
