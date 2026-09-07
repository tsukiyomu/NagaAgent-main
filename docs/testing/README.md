# NagaAgent Testing Documentation

> **Upstream migration notice（2026-09-07）**：MIG-0～MIG-4 已完成本地迁移验收，
> 测试基线为 `981821be`。先读 [`CURRENT_PROGRESS.md`](CURRENT_PROGRESS.md) 和
> [新测试基线](architecture/upstream-testing-baseline.md)。Langfuse runtime 尚未接回，
> 新 revision 的远端 CI 未验证；旧 C0 报告仍只证明其 source revision。

本目录按“文档职责”组织，避免把稳定架构说明、阶段进度、执行结果和历史任务混在同一层。

## 目录结构

```text
docs/testing/
├── README.md
├── CURRENT_PROGRESS.md  # 当前阶段、状态、缺口与下一步的单页入口
├── architecture/   # 稳定的测试架构与各 Part 详细说明
├── plans/          # 当前进度、优先级、实施计划与 Progress Ledger
│   └── suspend/    # 暂停、重叠、已过时或后置的计划；保留但不作为当前真相源
├── reports/        # 生成报告的位置、读取方式和真实性边界
├── showcase/       # 简历、面试和项目展示材料
├── archive/        # 旧规范和已完成/历史任务
└── img/            # 文档图片
```

## 推荐阅读顺序

1. [Upstream Migration Status：当前哪些只是迁入文档，哪些已在新分支复验](MIGRATION_STATUS.md)
2. [当前进度：现在做到哪里、为什么、下一步是什么](CURRENT_PROGRESS.md)
3. [测试架构总设计](../testing_architecture.md)
4. [测试体系总览](architecture/overview.md)
5. [Upstream Migration Plan](plans/upstream-migration-plan.md)
6. [SOP Compiler / Runtime 实践路线图（暂缓）](plans/sop-compiler-runtime-practical-roadmap%28temp%20suspend%29.md)
7. 按需阅读对应 Part：
   - [Part 02：API 与 Stream](architecture/part-02-api-stream.md)
   - [Part 04：Agentic Tool Loop](architecture/part-04-agentic-tool-loop.md)
   - [Part 08：Quality Gate Summary](architecture/part-08-quality-gate-summary.md)
   - [Part 11：Golden Cases](architecture/part-11-golden-cases.md)
8. [CI / PR Gate](architecture/ci-pr-gate.md)
9. [测试报告与 Allure 结果边界](reports/README.md)

## 分类规则

| 类型 | 目录 | 应包含 | 不应包含 |
|---|---|---|---|
| 稳定说明 | `architecture/` | 模块职责、流程、测试层、真实性、断言、边界 | 逐次运行日志、临时 TODO |
| 计划与进度 | `plans/` | 优先级、checklist、状态、Progress Ledger | 重复粘贴完整模块说明 |
| 报告指引 | `reports/` | 生成位置、读取方式、证据边界 | 手工伪造的运行结果 |
| 展示材料 | `showcase/` | 简历、面试、项目介绍 | 作为覆盖或通过的事实来源 |
| 历史材料 | `archive/` | 旧规范、历史任务输入 | 当前实施状态 |

## 文档索引

### Current status

- [Testing Current Progress](CURRENT_PROGRESS.md)

### Architecture

- [当前 upstream 测试基线与边界](architecture/upstream-testing-baseline.md)
- [Overview](architecture/overview.md)
- [Part 02 API / SSE](architecture/part-02-api-stream.md)
- [Part 04 Agentic Tool Loop](architecture/part-04-agentic-tool-loop.md)
- [Part 08 Quality Gate Summary](architecture/part-08-quality-gate-summary.md)
- [Part 11 Golden Cases](architecture/part-11-golden-cases.md)
- [CI / PR Gate](architecture/ci-pr-gate.md)
- [Langfuse Observability](architecture/langfuse-observability.md)

### Plans and progress

- [NagaAgent Final Testing Plan（P3-0 未启动）](plans/nagaagent-final-testing-plan.md)
- [Upstream Migration Plan（本地范围完成）](plans/upstream-migration-plan.md)
- [Closed Loop V1 Implementation Plan](plans/closed-loop-v1-implementation-plan.md)
- [Suspended Plans Index](plans/suspend/README.md)

### Other

- [Generated Reports Guide](reports/README.md)
- [Portfolio Summary](showcase/portfolio-summary.md)
- [Legacy Document Structure](archive/document-structure-legacy.md)
- [Archived Golden Cases v1 Task](archive/tasks/golden-cases-v1.md)

## 维护约定

- `CURRENT_PROGRESS.md` 是快速了解当前阶段、工作单元、缺口和下一步的唯一单页入口；它只做摘要，不复制执行日志。
- 当前后续路线图是 `plans/nagaagent-final-testing-plan.md`；迁移执行事实见 `plans/upstream-migration-plan.md`，Closed Loop V1 作为历史前置计划保留。
- `plans/suspend/` 中的文件只保留历史、详细设计和后置方案，不作为当前实施或 Gate 状态真相源。
- 各 Part 只记录已核对的实现、测试层、真实性边界和扩展方向。
- 运行结果由 pytest、Quality Gate 和 Allure 生成；手写文档只能解释结果，不能替代执行证据。
- `LANDED / PARTIAL / XFAIL_GAP`、`PR_BLOCKING / NOT_WIRED` 等状态必须有代码、命令或 CI 配置支持。
- 历史任务完成后移入 `archive/`，不要继续作为当前计划入口。
