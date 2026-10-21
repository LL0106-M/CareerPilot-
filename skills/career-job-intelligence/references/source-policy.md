# 来源、岗位与用工分类

## 来源等级

- `S`：政府/招录机关/公司招聘官网、官方岗位详情、官方公告。
- `A`：可确认归属公司的官方 ATS 或授权招聘项目页，如企业 Moka、北森、Hotjob 页面。
- `B`：招聘聚合平台、学校就业网、可信行业平台；只作为线索，优先回到官方复核。
- `C`：社区帖子、截图或个人整理；不能作为已核验事实。

## 状态

- `active`：公开页面和投递入口有效，或明确截止时间未到。
- `expired`：明确截止、页面关闭或岗位下线。
- `unknown`：页面存在但无法确认当前是否开放。
- `unverified_lead`：只有 B/C 级线索，尚未完成官方复核。

## 单位性质 `organization_type`

- `private`：民营、外资或普通市场化企业。
- `central_soe`：中央企业及其明确归属的招聘主体。
- `local_soe`：地方国企。
- `government`：党政机关及公务员/选调招录机关。
- `public_institution`：事业单位。
- `unknown`：来源没有足够信息。不得仅根据名称猜测。

## 用工或编制 `employment_type`

- `civil_service_establishment`：公务员行政编制。
- `public_institution_establishment`：公告明确的事业编制。
- `enterprise_contract`：企业劳动合同，包括国央企市场化用工。
- `labor_dispatch`：劳务派遣或第三方合同。
- `internship`：实习关系。
- `unknown`：公告没有说明。

## 招聘类型 `recruiting_type`

推荐使用：`campus`、`social`、`internship`、`daily_internship`、
`summer_internship`、`spring_recruitment`、`fall_recruitment`、`early_batch`、
`civil_service_exam`、`selected_graduate`、`public_institution_exam`、
`soe_campus`、`soe_social`、`unknown`。

分类之间不能互相替代。例如“国考”属于招聘途径，不等于具体岗位；“央企”描述单位性质，
不自动证明存在行政或事业编制。

## 去重与时效

- 清理 URL 跟踪参数和 fragment。
- 同一来源 URL、单位、岗位名称、招聘类型和地点生成稳定身份。
- 同批重复只保留一次；内容哈希不变时只更新抓取时间。
- 截止时间、岗位状态、编制和招聘对象只能来自可追溯页面，不允许模型补全。

