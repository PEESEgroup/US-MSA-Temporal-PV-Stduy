# Building–RPV Stock–Flow Study：分析与论文工作议程

> 用途：作为后续 analysis agent、paper agent 和人工研究者的共同交接文档。  
> 状态：研究议程，不是最终统计结果或预注册方案。  
> 数据入口：[`results/major_results_index.json`](results/major_results_index.json) 及其列出的不可变城市级产物；Miami与Minneapolis条目已更新为complete-2×2-context修复产物。  
> 更新日期：2026-09-03。  
> 核心修正：主分析从PV/Building数量提升为PV union area与透明的DC-capacity-equivalent情景；数量保留为风险分母和对照。Results以三个可证伪的scientific conclusions而不是metrics组织。

## 1. 修正后的论文主线

本文的主问题不再是“哪条路径产生更多PV事件”，而是“哪条路径承载更多容量相关的PV面积，以及这种容量流由风险集规模、事件强度还是单次系统尺度驱动”。冻结影像库存没有nameplate kWdc字段，因此主可观测量是anchor-year PV polygon-union area；装机容量只以显式功率密度情景换算为`MWdc-equivalent`，不得称为实测装机容量。

> **Most observed rooftop-PV additions occur on existing buildings, but this retrofit dominance reflects the interaction between the size of the existing building stock and city-specific adoption intensity—not necessarily a greater propensity of existing buildings to adopt solar.**
>
> 屋顶光伏增量主要发生在既有建筑上，但这种“改造主导”是庞大建筑存量与城市特定安装强度共同作用的结果，并不意味着既有建筑的单位安装倾向必然高于新增建筑。

面积加权后的主结论更进一步：

> **Newly observed Buildings yield larger PV footprints and more PV area per risk unit, but the inherited Building stock still carries most observed PV area.**
>
> 既有建筑存量承载了绝大多数已观测PV面积，但新增建筑在每个风险单位上产生的PV footprint更大。

更有力度的论文问题是：

> **Why is new construction tightly coupled with rooftop PV in some cities, while solar transitions elsewhere still depend mainly on the slow conversion of the existing building stock?**

论文应分开识别三个乘法机制：

1. **Stock-size effect**：既有建筑风险集巨大，因此在单位安装率不高时仍可贡献大多数PV。
2. **Adoption-intensity effect**：在同一城市和观测期内，新增或既有建筑具有更高的条件PV事件强度。
3. **System-size effect**：发生严格PV事件后，新增与既有路径宿主上的anchor PV union area是否不同。

政策含义不再依赖“旧建筑更容易安装”这一未经支持的前提。full-AOI描述性结果显示，新增路径的单次PV footprint显著更大，且单位风险PV面积产出高于既有路径；但每期新建流量远小于既有存量，因此仅依赖new-build coupling仍无法替代既有建筑转换。这里的容量含义来自面积及情景换算，不是permit/PTO实测nameplate。

## 2. 数据基础与当前证据状态

### 2.1 冻结结果索引中的已验证总量

15个城市的final release均已通过release QA；2026-09-01刷新的索引包含：

- 6,461,782个in-scope Building targets；
- 440,128个anchor-year PV targets；
- 397,181个resolved Building–PV relationships；
- 42,947个unavailable relationships；
- 396,334栋unique paired Buildings。

这些总量来自刷新后的冻结结果索引。Miami与Minneapolis重跑没有改变Building/PV target identity、PV onset或Stage 9 cardinality，因此上述总量不变；改变的是Building时间状态、Building onset和Building–PV时间关系。6,461,782个Building targets不是15城完整建筑总量；release QA通过也不等于后续stock–flow风险面板已通过专项科学QA。

两城当前索引条目通过non-mutating release-evidence wrapper绑定到：

- Miami：release profile为`/home/ec2-user/rpv-work/runs/miami-final-release-evidence-complete-context-v1-20260901/final_output_profile.yaml`，source repair run为`/home/ec2-user/rpv-work/runs/miami-building-context-repair-complete-2x2-v1-20260831`；Stage 9 QA通过，Building unknown observations从1,705,787降至1,830，interval-censored Building onsets从3,291增至61,802。
- Minneapolis：release profile为`/home/ec2-user/rpv-work/runs/minneapolis-final-release-evidence-complete-context-v1-20260901/final_output_profile.yaml`，source repair run为`/home/ec2-user/rpv-work/runs/minneapolis-building-context-repair-complete-2x2-v1-20260831`；Stage 9 QA通过，Building unknown observations从374,331降至459，interval-censored Building onsets从38增至13,502，PV-before-Building conflicts从67降至13。

### 2.2 面积/容量等值主证据（REPRODUCED）

`data_high_level/area_weighted_results_manifest.json`将现有面积轨迹与canonical relationship area、unique-host lineage及15城full-AOI raw-known风险面板连接，并逐项重生数量版的风险分母和事件数。全部440,128个PV targets的anchor PV union area总计28.496 km²；其中397,181个resolved PV targets对应25.828 km²，42,947个unavailable targets对应2.667 km²。每个源PV polygon identity在城内只出现一次，resolved source-target area与396,334栋unique paired hosts上的聚合面积精确对账。

面积加权带来四个主结果：

- 在各城市各自的area denominator内汇总，83.73%的anchor PV area在baseline之后进入onset路径，而Building SAM3 roof-mask area只有8.04%在baseline之后进入。相应数量份额为94.09%和10.87%，说明较早观察到的PV targets平均更大；area与count是互补而非可替换的时间构成。
- 在resolved PV-target area中，85.55%为`building_before_pv`、13.44%为`same_first_present_cohort`、1.01%为`pv_before_building_conflict`。相较target counts的92.91%、6.85%和0.24%，面积权重提高了同期与冲突大目标的可见度；冲突仍只作为QA诊断。
- full-AOI严格首次事件共承载20.348 km² anchor PV area，其中93.84%归于existing-Building route；按0.20 kWdc m⁻²的名义情景约为4.070 GWdc-equivalent，0.16–0.211情景范围为3.256–4.284 GWdc-equivalent。这些不是实测nameplate values。
- 新增路径的平均宿主PV面积为128.83 m²，existing route为54.59 m²；因此`mean area retrofit/new=0.424`。尽管existing risk exposure是new flow的33.36倍，且数量事件强度略高，新增路径的大系统尺度将pooled area-yield ratio推至`(A_new/N_new)/(A_retrofit/N_stock)=2.19`。existing route仍以15.23:1的总面积贡献占优。

上述stock--flow结果的用户批准图版已锁定为
`paper/figures/figure2_stock_flow/initial_v1/figure2_abcd/`。该路径是后续正文与caption写作的Figure 2视觉和数值交接点；版本状态为不可覆盖的`initial_v1`，科学证据状态仍为`REPRODUCED (descriptive)`。

面积主分析的事件归因规则必须始终随数字一起出现：同一unique host上所有resolved source PV target的anchor union areas只加总一次，并整体归因到该宿主的首次严格相邻PV事件。这估计的是“anchor时点仍存在的capacity-bearing PV footprint按首次事件路径如何分布”，不是逐cohort真实新增容量；后续扩容无法由当前首次事件表分离。

容量换算使用`data_high_level/pv_area_capacity_density_scenarios.csv`：0.16 kWdc m⁻²来自NREL对历史安装混合的module-density设定，0.211来自DOE/NREL 2024代表性400 W/1.9 m² module，0.20仅为图示名义换算。由于检测面积是plan-view polygon union而非实测module surface，只有面积本身是主可观测量；地方permit/interconnection/PTO校准完成前统一写作`DC-capacity-equivalent`。

### 2.3 路径构成数量版是composition，不是propensity（REPRODUCED）

`data_high_level/city_onset_pathway_composition.csv`现已从冻结索引逐城解析canonical `unique_pv_building_pairs`并通过hash与主键核验。在396,334栋unique paired Buildings中：

- 368,209栋（92.90%）为`building_before_pv`；
- 27,180栋（6.86%）为`same_first_present_cohort`；
- 945栋（0.24%）为`pv_before_building_conflict`。

正向分离的中位数为4个观测cohort steps，88.63%的正向分离至少为2步；它们不是年数。42,947个unavailable relationships属于relationship-row单位，单独报告，不得与unique paired Building分母相加。此前按397,181个resolved relationship rows得到的369,019、27,217与945仍是另一分析单位；主文路径构成改用与风险面板一致的unique paired Building单位，避免把多PV收敛宿主重复计数。

这些数字描述已观测PV宿主的事后路径构成，没有风险集分母，不能回答哪类建筑更容易出现PV事件。

### 2.4 分母校正与15城full-AOI数量版重生（REPRODUCED）

`data_high_level/city_stock_flow_decomposition.csv`统一合并了三个已完成、hash-bound、QA-passing的15城full-AOI raw-known风险面板。主口径在原始相邻cohort grid上要求Building `A→P`或`P→P`，PV事件要求严格相邻的已接受`A→P`，不跨`U`，并在首次合格PV事件后退出风险集：

| 分析范围与组别 | 风险集分母 | PV事件 | 每观测cohort transition粗略比例 |
|---|---:|---:|---:|
| full AOI：可确认新增建筑 | 1,062,729栋 | 9,734 | 0.916% |
| full AOI：已存在且期初尚无已链接PV | 35,451,139 building–cohort exposures | 349,793 | 0.987% |
| narrow sensitivity：可确认新增建筑 | 697,203栋 | 9,795 | 1.405% |
| narrow sensitivity：已存在且期初尚无已链接PV | 24,747,790 building–cohort exposures | 349,586 | 1.413% |

full-AOI直接计数池化的粗略RR为0.928，narrow sensitivity为0.995。二者都不是跨城主估计：它们按城市规模、transition数量和风险暴露直接加权，且描述性Wald区间未处理空间聚类。

上一版议程记录的698,130、26,571,328和359,661未能由当前三个completed raw-known runs重生，且没有paper-analysis manifest支持，现予以退役而不再作为重生目标。这个差异不应被解释为科学变化；它是旧PRELIMINARY汇总与当前明确raw-known/full-AOI口径之间的证据状态差异。当前数值的输入、哈希、行数、主键、筛选条件和输出哈希记录在`data_high_level/results_conclusion_evidence_manifest.json`。

### 2.5 数量与面积权重给出不同的城市诊断

15城full-AOI raw-known数量RR现已`REPRODUCED`：9城低于1、6城高于1。面积主结果却有13/15城的area-yield ratio高于1，只有Charlotte和Chicago低于1；7城在count RR与area-yield ratio之间跨越1。完整面积、数量、risk denominators与system-size factor见`data_high_level/city_area_weighted_stock_flow.csv`。这不是城市绩效排名，而是说明“PV事件是否发生”与“该事件承载多少PV面积”是不同系统结果。

数量版描述性DerSimonian–Laird综合的均值RR为0.896（95% CI 0.692–1.160），prediction interval为0.322–2.490，\(I^2=99.3\%\)，现移入Supplementary作为count sensitivity。area-yield不是binomial outcome，不能套用该Wald方差。C8现已由`data_high_level/area_uncertainty_manifest.json`下的city-stratified source-block bootstrap完成：Building-count-normalized area-yield的15城count/area-summed ratio为2.191（95% percentile interval 2.030–2.372），15个城市中8个区间完整高于1。该pooled行仍是观测城市的算术汇总，不是跨城市总体模型。

full-AOI指完整Anchor AOI内的Building风险集，仍不是citywide历史采用率。RR使用第4.1节raw-known规则；`narrow`仅作为target-domain sensitivity。

Los Angeles完成后，1,782,077个narrow身份与404,528个outside身份经状态级`P > U > A`合并、按`production_building_id`去重，得到2,151,906个full-AOI Building身份（重叠34,699个）。其raw-known full-AOI计数为\(N_{new}=172{,}554\)、\(Y_{new}=2{,}898\)、\(N_{stock}=6{,}970{,}585\)、\(Y_{retrofit}=92{,}361\)，因此\(RR_{\text{full-AOI}}=1.2675\)（表中记为1.27；描述性未聚类Wald 95% CI：1.22–1.31）。

Chicago、Seattle和Detroit采用相同的状态级`P > U > A`合并和`production_building_id`去重规则。Chicago将950,687个narrow身份与494,085个outside身份合并为1,409,461个full-AOI身份（重叠35,311个），raw-known计数为\(N_{new}=172{,}042\)、\(Y_{new}=493\)、\(N_{stock}=6{,}115{,}490\)、\(Y_{retrofit}=27{,}329\)，得到\(RR_{\text{full-AOI}}=0.6412\)（Wald 95% CI：0.59–0.70）。Seattle将174,518个narrow身份与378,920个outside身份合并为539,819个full-AOI身份（重叠13,619个），对应计数为88,028、206、1,737,884和5,372，得到\(RR_{\text{full-AOI}}=0.7571\)（95% CI：0.66–0.87）。Detroit将106,677个narrow身份与568,082个outside身份合并为666,277个full-AOI身份（重叠8,482个），对应计数为63,484、152、2,301,325和2,228，得到\(RR_{\text{full-AOI}}=2.4731\)（95% CI：2.10–2.91）。这些区间均为描述性未聚类Wald区间。

在调整估计、聚类区间和多重QA完成前，不应把这些方向转化为城市排名或确定性政策结论。描述性结果已足以把“15城共同方向”排除为工作假设，并将城市异质性提升为主要研究对象。

Miami和Minneapolis的complete-2×2-context修复均已通过Stage 7B–9 gates，两城现在都进入严格描述性主比较。当前full-AOI raw-known结果中，Minneapolis的\(N_{new}=33{,}758\)、RR为1.646；Miami的\(N_{new}=86{,}407\)、RR为1.016。两城修复没有改变PV onset evidence，因此相对旧partial-context结果的变化来自Building时间证据恢复，而不是PV事件重定义。

### 2.6 面积优势并非稳定的时间属性（REPRODUCED，descriptive）

`data_high_level/city_transition_area_weighted_stock_flow.csv`保留15城原始相邻cohort grid上的67个full-AOI transitions。23个transitions的count RR与area-yield ratio位于1的两侧，11城同时出现area-yield ratio高于和低于1的transitions。因此面积加权虽然把城市汇总整体推向new-higher，却没有产生稳定的城市类型。

Fig. 4的主图信息门槛已在首次渲染前冻结：两条路径各至少需要10个strict first-event hosts，同时要求正的PV面积分子、正的roof-area风险分母以及有限正值的三类ratio。该门槛保留55/67个full-AOI transitions并以hatch显示其余12个，而不是把它们改写为0。门槛后，roof-area-normalized (R_{roof})在Miami、Charlotte、New York City和Boston四城出现观察期方向切换；Building-count-normalized area-yield comparator在七城切换。原始67-cell结果中的11城仍是未加主图信息门槛的`REPRODUCED descriptive`统计，不能替代Fig. 4 panel a和d的roof-normalized支持集。

用户批准的Fig. 4四panel图版已在原`draft_v1`路径原位冻结：`paper/figures/figure4_transition_dynamics/draft_v1/`。该不可覆盖检查点包含vector PDF、300-dpi PNG、四个panel CSV、checks、source manifest、caption、note、精确绘图代码、信息门槛与规划快照，以及逐文件SHA-256 `freeze_manifest.json`。`draft_v1`现在是视觉版本锁，不将科学证据状态从`REPRODUCED (descriptive)`提升为`FROZEN`；任何后续改动必须使用新的同级版本目录。

这意味着主文不能把一个城市area-yield ratio写成固定的“城市类型”。更准确的结论是：capacity-bearing new-Building coupling既有跨城市差异，也有城市内部的有序观测期差异；部分切换来自事件频率，部分来自少数大系统的面积权重。C8 bootstrap进一步表明，在55个Fig. 4 gate-eligible transitions中，roof-normalized点估计低于1的单元没有任何一个95%区间完整低于1。因此四城roof switching仍是point-estimate switching，而不是区间支持的方向反转。transition结果仍受不等cohort时长、稀疏单元和右偏面积分布影响，不支持“年度波动”或政策响应的因果措辞。

### 2.7 屋顶面积风险分母改变城市诊断（REPRODUCED，descriptive）

`data_high_level/roof_area_weighted_results_manifest.json`现已将15城full-AOI
严格风险行连接到逐Building的plan-view anchor SAM3 roof-mask area，并生成
`city_roof_area_weighted_stock_flow.csv`与
`city_transition_roof_area_weighted_stock_flow.csv`。所有Building均有正面积，
narrow与outside anchor-mask identity互斥，逐Building mask cardinality与合并表
精确一致，134个scope×transition行复现原count风险分母、事件数和PV面积分子；
narrow总roof area还逐城复现Fig. 1已发布的Building area trajectory。

full-AOI count/area-summed结果中，new route的roof-area-normalized PV yield为
existing route的3.153倍。15/15个城市的城市汇总\(R_{roof}\)高于1；相对count
RR有9城跨越1，相对Building-count-normalized area-yield ratio则有Charlotte与
Chicago从低于1变为高于1。source-block bootstrap的15城算术汇总
区间为2.921--3.415；城市级区间在13/15城完整高于1，Charlotte和
Philadelphia跨越1，Boston在最粗4× cluster sensitivity下也跨越1。
因此仍不能写成城市排名、无条件普遍规律或政策效应。

## 3. Stock–flow分解与核心estimands

对城市 \(c\) 的每个可观测相邻cohort转变 \(t-1\rightarrow t\)，先保留事件数量分解：

\[
\Delta PV^{obs}_{ct}
=Y_{new,ct}+Y_{retrofit,ct}
=N_{new,ct}r_{new,ct}+N_{stock,ct}r_{retrofit,ct}.
\]

其中：

- \(N_{new,ct}\)：Building在本期由已知`A→P`、且此前没有已链接PV事件的可确认新增建筑；
- \(Y_{new,ct}\)：上述建筑中PV同时由已知`A→P`的事件数；
- \(N_{stock,ct}\)：Building在期初与期末均为已知`P`、且此前没有已链接PV事件的building–cohort风险暴露；
- \(Y_{retrofit,ct}\)：上述存量风险集中PV本期由已知`A→P`的事件数；
- \(r_{new,ct}=Y_{new,ct}/N_{new,ct}\)，\(r_{retrofit,ct}=Y_{retrofit,ct}/N_{stock,ct}\)；
- \(A_{new,ct}\)、\(A_{retrofit,ct}\)：两条严格首次事件路径上的unique-host anchor PV union area；
- \(\bar A_{new,ct}=A_{new,ct}/Y_{new,ct}\)、\(\bar A_{retrofit,ct}=A_{retrofit,ct}/Y_{retrofit,ct}\)：每个严格事件宿主的平均PV面积。

面积/容量等值主分析使用：

\[
q_{new,ct}=\frac{A_{new,ct}}{N_{new,ct}},\qquad
q_{retrofit,ct}=\frac{A_{retrofit,ct}}{N_{stock,ct}},
\]

其中\(q\)称为“PV-area yield per risk unit”，单位分别是m² PV per newly observed Building和m² PV per existing-Building cohort exposure。它不是roof utilization，因为分母不是roof area；也不是年度容量hazard，因为cohort间隔不等。

roof-area-normalized扩展现为`REPRODUCED descriptive`。在每个city×cohort transition内定义：

\[
q^{roof}_{new,ct}=\frac{A_{new,ct}}{B^{roof}_{new,ct}},\qquad
q^{roof}_{retrofit,ct}=\frac{A_{retrofit,ct}}{B^{roof}_{stock,ct}},\qquad
R_{roof,ct}=\frac{q^{roof}_{new,ct}}{q^{roof}_{retrofit,ct}}.
\]

其中\(B^{roof}_{new,ct}\)是本transition进入可确认新增Building风险组的plan-view SAM3 roof-mask area，\(B^{roof}_{stock,ct}\)是本transition期初仍符合既有Building风险集的roof-mask area。城市汇总时，分子沿用严格首次事件路径的unique-host anchor PV union area；新增与既有roof分母分别跨原生transitions求和，因此既有分母是roof-area–cohort exposure而不是anchor时点roof stock。主文将城市级\(R_{roof}\)放入Fig. 3，并在Fig. 4报告city×native-transition版本。该指标不是可用屋顶利用率、真实覆盖率、年度hazard或逐cohort真实容量新增；数值与方向必须继续通过`city_roof_area_weighted_stock_flow.csv`、`city_transition_roof_area_weighted_stock_flow.csv`及其passing manifest引用。

主恒等式为：

\[
\frac{A_{retrofit}}{A_{new}}
=\frac{N_{stock}}{N_{new}}
\times\frac{r_{retrofit}}{r_{new}}
\times\frac{\bar A_{retrofit}}{\bar A_{new}}.
\]

这一三因子恒等式把“存量规模”“事件强度”和“单次系统尺度”对capacity-area dominance的贡献分开。主表同时报告：area composition、count composition、stock multiplier、count RR、mean-event-area ratio、area-yield ratio及三个log components。

容量等值只作单位翻译：\(K^{eq}=\rho A\)。固定\(\rho\)不会改变任何share或ratio。主图名义值为\(\rho=0.20\) kWdc m⁻²，并同时给出0.16–0.211情景范围；在permit/PTO nameplate校准前不得把\(K^{eq}\)写成measured installed capacity。

这里的\(A\)是anchor-year仍可见PV面积按宿主首次严格事件的归因，不是城市在该期间的真实逐期容量新增。对未进入canonical unique-pair表的Building，零事件表示“未观测到符合当前anchor inventory与linkage定义的PV事件”，不等于每个历史cohort都经独立证据确认PV为`A`。

## 4. Building–cohort风险面板

### 4.1 分析单位与状态规则

主分析单位是building–cohort transition，不是PV target、relationship row或单纯的unique paired Building。每城使用自身冻结的opaque cohort order：

1. 排除最早可用cohort，因为首次`P`可能左删失。
2. 主分析只使用冻结顺序中相邻的\(t-1,t\)，不跨过`U`或缺失cohort拼接事件。
3. Building风险状态和PV事件转变必须使用已知`A/P`证据；`U`不得默认为`A`。未配对Building的零事件是当前观测结局下的“无已链接事件”，不改写为逐cohort的PV `A`状态。
4. 新增组要求Building `A→P`；既有组要求Building `P→P`。
5. PV事件统一定义为同一相邻转变中的已知`A→P`。
6. 一栋建筑的首次合格PV事件后退出风险集；若多个源PV身份收敛到同一Building，使用冻结anchor linkage解析的最早onset并保留lineage。

主规则优先使用raw/known Building PAU evidence构造风险暴露，并仅用已知PV `A→P`确定事件时点；resolved persistence-imputed sequence作为敏感性分析，不得反过来。

### 4.2 描述性估计

对每个city×cohort transition输出\(N_{new}\)、\(N_{stock}\)、\(Y_{new}\)、\(Y_{retrofit}\)、\(A_{new}\)、\(A_{retrofit}\)、count RR、mean-event-area ratio、area-yield ratio及三因子恒等式。分母或面积为零时显式标记不可估，不用0、连续性校正或极端ratio代替。

不同cohort间隔不同，因此\(r\)只称为“per-observed-cohort transition proportion”，\(q\)只称为“area yield per risk unit”，都不称年度hazard。如能获得可靠影像捕获日期，再以暴露时长为offset做补充分析。

### 4.3 城市内条件比较

主回归在同一city×cohort transition内比较新增与既有风险暴露，避免把大城市、cohort数量和城市基线差异混入组间对比。面积主结果现采用city-stratified source-block bootstrap：每次抽中的block对所有原生transition、两条route、风险行、roof-area exposure和strict-event host area共享同一权重。数量事件模型保留为机制分解与敏感性。数量模型可使用对稀有事件稳健的Poisson pseudo-maximum likelihood：

\[
E(Y_{ibct})=\exp(\alpha_{ct}+\gamma_b+\beta_c New_{ibct}),
\]

其中\(\alpha_{ct}\)为city×cohort-transition fixed effects，\(\gamma_b\)为candidate-block fixed effects，\(\exp(\beta_c)\)为城市特定条件RR。标准误至少在block层级聚类；补充报告logit平均边际风险、RD和不含block fixed effects的规格。

Block fixed effects只能控制已入选candidate blocks内不随时间变化的邻里条件，不能消除“block因anchor PV candidate而入选”的选择。主结果必须标记为`candidate-scope conditional estimate`。

### 4.4 跨城市综合

不把简单池化area-yield ratio作为跨城主估计。C8已通过block bootstrap得到城市级\(\log qRR_c\)及方差，但15城并非城市总体的概率样本，因此暂不把random-effects synthesis解释为总体效应。保留count/area-summed pooled行仅用于观测城市的算术对账。数量RR的既有DerSimonian–Laird结果转入Supplementary，不能把其方差移植给面积ratio。

修复后的Miami和Minneapolis均可进入城市级主估计。稀疏性门槛仍应在city×cohort单元上预先固定：整城分母充足不代表每个转变期都可稳定估计，分母或事件过少的单元仍须合并、标记不可估或仅作补充性精确估计。

## 5. 优先研究问题

### RQ1：capacity-area dominance中有多少来自存量规模、事件强度和系统尺度？

- 使用第3节三因子恒等式进行city×cohort及城市级分解。
- 并列报告area composition、count composition、stock multiplier、event RR、mean-event-area ratio和area-yield ratio。
- 将count-only与`building_before_pv`构成保留为对照，不再作为容量相关耦合的核心证据。

### RQ2：为什么新建–PV耦合存在强烈城市异质性？

- 优先考察solar mandate、solar-ready/building code、建筑类型、开发强度、电价、辐照和许可制度。
- 使用城市特定估计和meta-regression，但限制城市级协变量数量，避免在15城上过度拟合。
- 使用assessor `year_built`、building permit和PV permit/PTO验证“新建”与“同期PV”的真实时间。

### RQ3：政策分别如何影响新建耦合和retrofit hazard？

这是两个不同的政策estimand，需要两套识别设计：

1. **新建耦合效应**：在完整风险面板中估计`new_building × policy`。city×cohort fixed effects会吸收城市–时期政策主效应，但仍可识别同一时期内新增组相对存量组的差异变化。
2. **Retrofit-hazard政策效应**：仅在存量风险集中建模。城市–时期政策主效应与饱和city×cohort fixed effects共线，因此必须改用具有可信处理时间和对照组的event study/DiD、边界设计或其他准实验；不能从第一个模型的交互项顺带推出。

没有可信外生变化时，只做关联性、多层模型和机制讨论，不使用因果措辞。

### RQ4：哪些建筑与社区更依赖缓慢的存量改造？

- 分析建筑年代、单户/多户、产权、屋顶面积、土地用途、收入、能源负担、租住率及其交互。
- 区分“条件于anchor-year仍有PV的安装时机不平等”与“全体建筑采用率不平等”。
- 检查`U`、unavailable relationship、candidate-scope覆盖和识别误差是否在弱势社区系统性更高。

### RQ5：candidate-scope发现能否外推到citywide adoption？

- 对non-candidate blocks按城市、建筑密度、土地用途、开发时期、收入和地理位置分层随机抽样。
- 用同一Building temporal inference或assessor/permit构造验证风险面板。
- 并列报告`observed candidate-scope estimate`、`non-candidate validation estimate`和`model-assisted citywide estimate`。

## 6. 必须保持的科学解释边界

### 6.1 时间与删失

- Cohort label是有序观测窗口，不是精确年份。
- `building_before_pv`只支持建筑先观察为存在、PV后观察为存在，不等于精确retrofit日期。
- `same_first_present_cohort`只能称为`cohort-contemporaneous`，不能直接称为建设时安装或building-integrated PV。
- `pv_before_building_conflict`是时间一致性诊断，不是真实政策路径。
- Onset是left-censored或interval-censored；cohort step不能直接转换成年。

### 6.2 目标总体与选择

当前PV历史由anchor-year仍存在的PV反向追踪，直接目标总体是：

> 到anchor year仍然存在、进入固定anchor inventory并具有可用时间证据的PV及其宿主建筑，以及同一candidate scope中的Building风险暴露。

它不包含已拆除、更换后不可识别或在anchor year已消失的历史PV。因此当前事件比例不得表述为citywide historical adoption rate。

Building模型在入选block内扫描全部建筑，但block由anchor PV candidate触发。当前设计是“PV-conditioned blocks内的完整扫描”，不是城市建筑的概率样本。约6,187,838个authoritative Building身份进入temporal output，先前建筑数加权覆盖约47.9%；城市间高度不均，不得用统一乘数外推。

C12现采用“部分验证＋明确限定”路线并已形成`REPRODUCED` bundle：15城full/narrow比较中，Building-normalized与roof-normalized area-yield的城市方向以及existing-route面积多数地位均保持；冻结的candidate-bridge敏感性将relationship覆盖从90.24%提高到95.56%，仍有19,535个anchor PV targets没有Stage 7B candidate；raw `U` observation与42,947个unavailable relationship rows按各自单位单独核算。该bundle只验证已观测anchor-triggered domain内部的稳定性与linkage availability，不能识别non-candidate PV，也不能识别anchor inventory之前已经拆除、更换或消失的历史PV。全文目标总体统一写为“in-scope, anchor-surviving PV and Buildings”，不得称为citywide historical adoption rate或complete historical PV capacity。

### 6.3 允许与禁止的claim

当前数据可以支持：

- anchor-surviving PV的area-weighted temporal composition；
- resolved PV-target area中Building-before、cohort-contemporaneous与conflict的构成；
- full-AOI严格首次事件的PV-area stock–flow三因子分解；
- 同城市、同cohort中新增与既有风险单位的描述性area-yield比较；
- count与area权重造成的城市/transition方向差异以及unique-host面积分布。

当前数据不能单独支持：

- “既有建筑比新建建筑更容易安装PV”这一全城市共同结论；
- 把PV plan-view union area或情景MWdc-equivalent称为实测nameplate capacity；
- 把宿主anchor总面积归因于首次PV事件解释成该cohort的真实容量新增；
- 全城市新建或存量建筑PV安装率、全城市新建总量或未经验证的citywide hazard；
- 精确建成年、精确PV安装年或仅凭同cohort观察推断mandate compliance；
- 无可信处理时间、对照和识别假设时的政策因果效应。

## 7. 分析阶段与停止门

### Phase 0：重生描述性结果并冻结科学QA（已完成基础层）

1. 从`results/major_results_index.json`和`results/artifact_results_index.csv`解析全部15城canonical inputs；确认Miami和Minneapolis均绑定complete-2×2-context release profile，禁止回退或混入旧产物。
2. 建立单一可复现的risk-panel builder；逐城输出cohort order、状态字段、风险集流程、排除原因和恒等式对账。
3. 以当前completed raw-known runs精确重生full-AOI的1,062,729、9,734、35,451,139、349,793及15城粗略RR，并将旧PRELIMINARY窄范围汇总差异记录为已解决的evidence-status disagreement。
4. 将两城Stage 7B–9 passing gates、输入/输出哈希、release wrapper和repair-impact指标写入分析input manifest，并校验其与全局results index逐项一致。
5. 输出输入路径、SHA-256、行数、主键、筛选条件、分母和运行manifest。

### Phase A：Stock–flow描述与城市异质性

1. 生成city×cohort四个基础计数、两条路径的PV area及第3节三因子估计量。
2. 生成以stock multiplier、event intensity和mean event area共同解释capacity-area composition的主图。
3. 并列报告count RR与area-yield ratio，标记方向反转。
4. 报告缺失、`U`、左删失、极小分母、右偏面积与无法估计的city×cohort单元。

### Phase B：城市内固定效应与meta-analysis

1. 对area outcome预先规定block bootstrap或cluster-robust continuous-outcome model；数量事件模型作为机制分解。
2. 按城市输出调整后area-yield ratio、mean-event-area contrast及不确定性，再决定是否做meta-analysis。
3. 进行大系统influence、top-tail trimming、稀疏transition和leave-one-city-out分析。

### Phase C：选择、时间和目标域验证

1. 对non-candidate blocks分层抽样或接入citywide assessor frame。
2. 用assessor `year_built`/building permit验证Building onset，用PV permit/interconnection/PTO验证PV onset。
3. 按城市、cohort、PAU confidence、OSM/SAM3 source和组别分层人工判读。
4. 将时间错分、Building识别误差、anchor-survivor和candidate-block selection传播到区间。

### Phase D：政策、建筑机制与公平性

只在政策时间、建筑/社会经济数据、目标域验证和estimand明确后进入。预先冻结主要结局、处理时间、对照构造、空间聚类层级和敏感性分析。

## 8. 必做的敏感性与负控制

- **Unknown handling**：主分析严格排除`U`；补充报告resolved sequence、已知观察桥接和极端上下界，但不把桥接口径称为相邻转变。
- **Left censoring**：排除最早cohort；比较排除前两个cohort及仅保留前期明确`A`的结果。
- **Cohort duration**：不把cohort当年；若有可信capture dates，以实际间隔作offset或分层。
- **Building context/identity**：以Miami和Minneapolis的complete-2×2修复产物为canonical primary input；旧partial-context产物只用于量化修复影响，不进入主分析或与修复产物混合。另需核对OSM/SAM3 source、多源PV收敛、Building拆分/合并和边界block。
- **PV area attribution**：主分析将同一host全部resolved source-target area相加并归于首次严格事件；补充比较只取selected earliest target area、逐PV-target onset area及排除multi-source hosts。
- **Capacity translation**：固定0.16、0.20和0.211 kWdc m⁻²情景；未来以permit/PTO nameplate做city×vintage calibration并传播误差。情景范围不是统计置信区间。
- **Large-system influence**：报告median/p90/p99、Gini、top-1% area share及trim/winsorize sensitivity；分布whisker不是不确定性区间。
- **Anchor-survivor conditioning**：通过permit/PTO历史库或明确退役情景评估早期PV消失偏差。
- **Candidate selection**：报告candidate/non-candidate验证；不声称block fixed effects已解决选择偏差。
- **Spatial dependence**：主分析block-clustered SE；补充更高层空间聚类、spatial block bootstrap和替代block定义。
- **Sparse cells**：预先固定最小分母/事件门槛；对分离或零事件使用exact/Firth作补充，不用任意连续性校正制造排名。
- **Negative controls**：检查`pv_before_building_conflict`、不可能的政策前置效应和伪处理时点，诊断时间错分与预趋势。

## 9. 外部数据优先级

| 优先级 | 外部数据 | 主要用途 | 关键限制 |
|---|---|---|---|
| 1 | 地方PV permit / utility interconnection / PTO | 验证PV onset、同期安装、政策事件研究、容量 | 覆盖和字段跨城不一致 |
| 1 | Parcel assessor / building permit | `year_built`、Building类型、完整分母、目标域验证 | 年代误差，parcel与Building一对多 |
| 2 | Citywide Building/eligible-roof frame | 新增和存量分母、citywide hazard | 需定义结构与太阳能适宜性 |
| 2 | ACS 5-year、DOE LEAD | 收入、租住、住房类型、能源负担 | 空间聚合与生态推断风险 |
| 3 | 原始法规、PUC/utility档案、DSIRE、SolarAPP+ | mandate、补贴、许可、净计量和tariff时点 | 需回查原始法规，不只依赖汇总库 |
| 3 | Zoning、土地用途、LiDAR、树冠/遮阴 | 建筑适宜性和结构性障碍 | 城市间测量一致性 |
| 4 | NSRDB/PVWatts、EIA-861、eGRID/Cambium | 发电、电费与碳效益 | PV面积到容量需本地校准 |

如只能优先获取一组数据，先获取**地方PV permit/utility PTO + parcel assessor/building permit**。这组数据同时验证Building时间、PV时间、完整分母和政策处理时点。

## 10. 结论驱动的Results结构与四张主图

Results不再按“trajectory / ordering / RR / context”四类metrics平铺，而按三个可以被数据支持或推翻的结论递进。每节首句直接给结论，随后用分母、分解、异质性和边界约束其含义。

### Result conclusion 1 — PV capacity was layered onto inherited roof stock

**结论句：Most PV area entered the record after most urban roof area was already present.**

在各自独立的anchor-area denominator内，83.73%的PV union area在baseline以后进入PAU onset路径，而Building SAM3 roof-mask area只有8.04%。通过冻结linkage连接后，resolved PV-target area的85.55%为`building_before_pv`，13.44%为cohort-contemporaneous，1.01%为temporal conflict。面积权重说明较早与同期目标比count version更大，但不改变solar主要叠加在既有urban fabric上的结论。

对应**Fig. 1**：15城area trajectories、post-baseline area gap及count comparator、resolved non-conflict PV-area onset composition，以及按cohort interval内部均匀分布、取区间中点估计的非累计one-year lag-bin share。Panel c显式分离Building left-censored、cohort-contemporaneous和between-cohort；panel d只对Building onset可区间解析的关系绘制interval-imputed observed lag，分母仍为all resolved PV area，因此曲线不累计到100%。unavailable onset和PV-before-Building conflict继续单独核算，不被当成0或实质路径。2026-09-02通过视觉验收的原生矢量组合版冻结于`paper/figures/figure1_city_trajectories/initial_v1/figure1_abcd/`，状态为`REPRODUCED`；正文起草所需的pooled数值、caption-ready analytical frame和措辞边界见该目录`README.md`。

### Result conclusion 2 — New-route area advantages are outweighed by inherited stock scale

**结论句：Newly observed Buildings yield larger PV footprints and more PV area per risk unit, but the inherited Building stock still carries most observed PV area.**

full-AOI严格面板中，new route的平均event-host PV footprint是existing route的2.36倍，单位风险PV-area yield是2.19倍。这两个new-route优势没有转化为总面积主导：existing route仍占97.29%的事件和93.84%的PV area；20.348 km²分类面积对应名义4.070 GWdc-equivalent，情景范围3.256–4.284 GWdc-equivalent。原因是existing exposure为new flow的33.36倍，而existing事件强度还略高约7.7%；即使existing-event的平均PV area只有new-event的42.4%，三项相乘仍使existing route的总面积为new route的15.23倍。这一结论同时否定两种误读：retrofit dominance不代表单次系统更大，new-route单位风险面积优势也不代表new construction已经足以承担总容量转换。

对应**Fig. 2**：先以二维scatter同时显示逐城与pooled的system-size和PV-area-yield，并突出两个pooled route points之间的new-route优势；再显示area versus count route shares，以逐城signed log anatomy精确分解stock/event/size三因子，最后按相同城市顺序给出area-capacity parity frontier及单独pooled行。最后一panel只计算在相同observed denominators下new route需要的PV area yield，不是政策预测或roof-potential estimate。

### Result conclusion 3 — Area weighting changes, but does not stabilize, coupling

**结论句：Newly observed Buildings yield more PV area per risk unit than event counts suggest in most cities, but that capacity advantage is temporally unstable and size-concentrated.**

pooled count RR为0.928，Building-count-normalized area-yield ratio为2.19，roof-area-normalized ratio为3.15，因为new-route host的平均PV footprint为128.83 m²，existing route为54.59 m²，且两条路径的risk roof-area构成不同。面积主结果在13/15城高于1；7城相对于count RR跨越1。roof normalization后15/15城高于1，相对count RR有9城跨越1，Charlotte与Chicago相对Building-count-normalized area yield进一步跨越1。原始67个full-AOI transitions中有23个发生count/area方向分歧，11城的area-yield direction在观察transitions间切换；这两个数字是未加Fig. 4信息门槛的released descriptors。Fig. 4按预设门槛保留55个单元，以roof-normalized switching为主、Building-count-normalized switching为对照。大系统尾部进一步放大不稳定性：existing route最大的1%严格宿主承载32.9%的该路径PV area，new route最大的1%承载21.7%；这些是分布统计而非置信区间。

对应两张图：

- **Fig. 3**：逐城roof-area-normalized ratio、count-to-Building-area-to-roof denominator shift、route-specific mean/median/p90/p99与top-1% concentration；
- **Fig. 4**：city×native-transition area-yield heatmap、count/area sign-disagreement、事件强度与system-size轨迹、direction-switch summary。

transition-level结论只能称“observed transition switching”。C8 source-block bootstrap已完成，且不使用binomial Wald区间；其结果不支持把roof-normalized below-parity点估计提升为确定方向。政策日期、pre-trends和placebos验证前仍不得把切换归因于mandate、permit reform或incentive。

### 为什么当前不设第四个Results conclusion

现有外部数据覆盖广，但跨城exact attribute linkage仅在部分城市可用，且还没有released context-to-strict-risk-panel join与预设模型。`data_high_level/context_evidence_readiness.csv`因此将所有城市的main-text context gate标为`NOT_PASSED`。此时强行加入“institutions and building stock”会得到一节变量清单，而不是独立科学结论。

只有在一对一context join、分层missingness、去重风险分母、city/cohort adjustment与合理聚类全部通过，或permit/PTO nameplate对area-to-capacity完成跨城校准后，才增加第四节和可选**Fig. 6**。Fig. 5现为Methods workflow。新增结论必须解释area-yield heterogeneity或证实/修正capacity translation；否则外部数据留在Supplementary coverage/validation。

### 主文整体顺序

1. **Introduction**：composition与propensity为何被城市级solar summary混淆。
2. **Data and estimands**：独立Building/PV证据、冻结linkage、严格风险集与目标总体。
3. **Result 1**：capacity-bearing PV area被叠加到先已存在的roof stock（Fig. 1）。
4. **Result 2**：new route具有system-size与单位风险面积优势，但stock scale决定总量格局（Fig. 2）。
5. **Result 3**：area weighting改变城市诊断，但capacity coupling仍在城内切换且受大系统尾部影响（Figs. 3–4）。
6. **Discussion**：建筑流量约束要求new-build coupling与existing-stock conversion并行；机制解释保持假设措辞。
7. **Limitations**：anchor survivor、first-event area attribution、capacity-equivalent calibration、candidate scope、cohort duration、`U`、区间删失、空间选择和描述性未聚类区间。

panel级数据、检查、caption contract与release gate见`paper/FIGURE_PLAN.md`。已有workflow figure作为Fig. 5放入Results和Discussion之后的Methods，不占用四张Results主图；在可编辑源文件和独立provenance bundle补齐前不原位修改当前PDF。

## 11. 后续agent的操作约束

1. 从冻结索引解析canonical input，不手工搜索并混用旧run。
2. 每项统计记录输入路径、SHA-256、行数、主键、状态序列版本、筛选条件和分母。
3. 区分Building target、building–cohort exposure、PV target、PV event、resolved relationship和unique paired Building。
4. 区分raw PAU、resolved sequence、onset bound、adjacent transition和relationship classification。
5. 不把cohort step称为年，不把`same_first_present_cohort`称为建设时安装。
6. 不把candidate-scope比例称为citywide adoption rate，不把anchor-surviving PV称为全部历史安装。
7. 不静默删除`U`、unavailable、时间冲突或无法估计的city×cohort单元。
8. 不用路径数量占比推断单位安装倾向；所有propensity/intensity claim必须有明确风险集分母。
9. 不把PV union area称为nameplate capacity；所有MWdc数值必须带`equivalent`与功率密度情景。
10. 不把宿主anchor总面积归因于首次事件解释为真实cohort容量新增；multi-source lineage必须保留并去重。
11. 任何因果陈述必须对应处理时间、对照组、识别假设、预趋势和安慰剂检验。
12. 图表必须从可复现的机器可读中间表生成，不手工复制数字。

## 12. 下一批具体交付物

已完成的本轮基础层：

1. `scripts/build_results_conclusion_evidence.py`：统一15城risk releases、canonical unique pairs、trajectory summary与external readiness audit；
2. `data_high_level/results_conclusion_evidence_manifest.json`及12个aggregate outputs：输入/输出hash、row count、primary key、filters、denominators与status；
3. `data_high_level/results_conclusion_evidence_checks.json`：15城、67个full-AOI transitions、396,334个unique paired Buildings及stock–flow恒等式QA；
4. `scripts/build_area_weighted_results.py`：流式连接PV target area、unique-host lineage和raw-known风险面板；
5. `data_high_level/area_weighted_results_manifest.json`及6个area/capacity aggregate tables：输入/输出hash、row count、primary key、filters、denominators与capacity scenarios；
6. `data_high_level/area_weighted_results_checks.json`：PV总面积、resolved/unavailable area、源polygon唯一性、host面积、count reproduction及三因子恒等式QA；
7. `paper/FIGURE_PLAN.md`：以area/capacity-equivalent为主、count为对照的三个结论section与四张Results主图合同；
8. `data_high_level/roof_area_weighted_results_manifest.json`及city/transition roof-area risk tables：将strict风险行连接到正值plan-view roof-mask area并复现count与PV-area分子；
9. `paper/figures/figure4_transition_dynamics/transition_information_gate_v1.json`与已冻结的`draft_v1/`完整bundle：首次渲染前冻结10-events-per-route门槛；用户批准图版、四panel CSV、checks、manifest、caption、note、精确代码与文档快照均由`freeze_manifest.json`锁定。

下一批按claim release gate推进：

1. **Area uncertainty bundle（已完成，REPRODUCED）**：`scripts/build_area_block_bootstrap.py`输出city、pooled与67个native-transition的footprint、Building-normalized与roof-normalized area-yield、area share、count comparator及三项log decomposition区间；同时发布block sufficient statistics、有效block数、non-estimable replicate、2×/4× cluster、seed与replicate-count敏感性、Tables S5--S6、checks和manifest；
2. **Nameplate calibration bundle**：以permit/interconnection/PTO的city×vintage kWdc校准plan-view union area并传播换算误差；未完成前保留capacity-equivalent措辞；
3. **Fig. 4 sensitivity**：`draft_v1`视觉审阅与不可覆盖版本检查点已完成；后续仅在新的同级版本目录另行生成5/20-events-per-route敏感性，不改变已冻结的主门槛或覆盖获批图版；
4. **Target-domain validation（部分完成）**：full/narrow、candidate-bridge及unknown/unavailable accounting已`REPRODUCED`；candidate/non-candidate抽样、anchor-survivor disappearance、capture-date和permit/PTO onset验证仍需外部数据；
5. **Context join bundle**：只在一对一crosswalk、去重、missingness和聚类QA通过后检验是否值得增加第四Results conclusion/Fig. 6；
6. **Manuscript macros and remaining figures**：从`data_high_level`生成数值宏、完成其余figure版本审批及caption source，禁止手抄。

area-yield的block-clustered uncertainty与C12部分验证现已`REPRODUCED`。当前最高优先级转为用局部nameplate数据校准area-to-capacity，并在可获得外部数据时补充non-candidate sampling和historical-disappearance验证；在这些边界解除前，context或政策机制仍不能成为主文独立结论。
