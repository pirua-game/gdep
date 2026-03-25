# gdep-mcp — 游戏代码库分析 MCP 服务器

让 Claude Desktop、Cursor 等 AI Agent 通过 [gdep](https://github.com/pirua-game/gdep)
分析游戏项目（Unity、UE5、C++、C#）的 MCP 服务器。

**其他语言版本：**
[English](./README.md) · [한국어](./README_KR.md) · [日本語](./README_JA.md) · [繁體中文](./README_ZH_TW.md)

---

## ⚡ 快速安装

### 通过 npm 安装（推荐 — 无需 git clone）

```bash
npm install -g gdep-mcp
```

自动同时安装 `gdep` 和 `mcp[cli]` Python 包。

在 AI Agent 配置中添加：

```json
{
  "mcpServers": {
    "gdep": {
      "command": "gdep-mcp"
    }
  }
}
```

> 每次工具调用时通过参数传入 `project_path`，无需在配置中指定项目路径。

### 通过 pip 手动安装

```bash
pip install gdep "mcp[cli]"
```

**Claude Desktop 配置** (`claude_desktop_config.json`)：

```json
{
  "mcpServers": {
    "gdep": {
      "command": "/path/to/gdep-cli/.venv/bin/python",
      "args": ["/path/to/gdep-cli/gdep_mcp/server.py"],
      "cwd": "/path/to/gdep-cli"
    }
  }
}
```

---

## 🛠 工具列表（19个）

### 上下文工具

| 工具 | 说明 |
|------|------|
| `get_project_context` | **会话开始时首先调用** — 项目整体概览 |

### 高层意图工具（9个）

| 工具 | 说明 |
|------|------|
| `analyze_impact_and_risk` | 修改类前的影响范围 + 代码检查。`detail_level="summary"` 快速摘要；`query=` 过滤结果 |
| `explain_method_logic` | 单个方法内部控制流摘要 — Guard/Branch/Loop/Always 5~10 行 |
| `trace_gameplay_flow` | 方法调用链追踪 + 源代码 |
| `inspect_architectural_health` | 耦合度/循环引用/死代码/反模式 |
| `explore_class_semantics` | 类结构 + AI 三行摘要 |
| `suggest_test_scope` | 修改类后需运行的测试文件自动推算（支持 CI JSON 输出） |
| `suggest_lint_fixes` | lint 问题 + 代码修复建议（dry-run，不修改文件） |
| `summarize_project_diff` | 从架构角度汇总 git diff — 循环引用增减、高耦合警告 |
| `get_architecture_advice` | scan+lint+impact 综合 → 结构化报告或 LLM 架构建议 |

### Raw CLI 访问

| 工具 | 说明 |
|------|------|
| `execute_gdep_cli` | 直接访问所有 gdep CLI 功能 |

### Axmol / Cocos2d-x 专用

| 工具 | 说明 |
|------|------|
| `analyze_axmol_events` | EventDispatcher/Scheduler 绑定映射 — 事件注册/处理主体提取 |

### Unity 专用

| 工具 | 说明 |
|------|------|
| `find_unity_event_bindings` | Unity Inspector 绑定方法检测 |
| `analyze_unity_animator` | .controller → Layer/State/BlendTree 结构 |

### UE5 专用

| 工具 | 说明 |
|------|------|
| `analyze_ue5_gas` | GA/GE/AS 类 + GameplayTag + ASC 使用处 |
| `analyze_ue5_behavior_tree` | BT_* .uasset → Task/Decorator/Service |
| `analyze_ue5_state_tree` | ST_* .uasset → Task/AIController 连接 |
| `analyze_ue5_animation` | ABP 状态机 + Montage 分段/插槽/GAS Notify |
| `analyze_ue5_blueprint_mapping` | C++ 类 → Blueprint 实现映射 |

---

*[主仓库](https://github.com/pirua-game/gdep)*
