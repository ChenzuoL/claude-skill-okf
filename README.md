# OKF — Open Knowledge Format 工具包

> 把随便写的 markdown 变成 AI agent 能读懂、能导航、能搜索的标准化知识。

## 什么是 Open Knowledge Format

**Open Knowledge Format (OKF)** 是 Google Cloud 在 2026 年 6 月发布的开放规范（v0.1），它的核心思想很简单：

> 知识不应该被锁在某个平台或工具里。知识应该是**可移植的、人与 AI 都能读的文件**。

一个 OKF 知识包就是：

```
只是一个装满 .md 文件的目录
只是 YAML 头部声明了 type / title / tags 等字段
只是普通的 markdown 链接把概念串成图谱
```

不需要 SDK，不需要数据库，不需要登录任何平台。用任何编辑器都能打开，放在 git 仓库里就能做版本管理，用任何搜索引擎都能建索引。

### 为什么要用 OKF

组织里的知识散落在各种地方：

- 表结构在 BigQuery 里
- 指标定义在 wiki 上
- 故障手册在共享盘里
- 经验在人脑子里

每换一个 AI agent，都要从零拼装这些碎片。OKF 提供了一个**统一格式**：

- 谁都能生产（人写、脚本生成、AI 生成）
- 谁都能消费（Claude、Codex、你的搜索工具）
- 不受任何厂商绑定

### OKF 文件的格式

每个概念就是一个 `.md` 文件，顶部有 YAML frontmatter：

```yaml
---
type: BigQuery Table          # 必填 — 概念类型
title: Orders                  # 标题
description: 每行一个已完成订单  # 一句话描述
resource: https://...          # 原始出处 URL
tags: [sales, revenue]         # 标签
timestamp: 2026-05-28T14:30:00Z # 最后更新
---

# 实际内容从这里开始
普通 markdown 正文，可以有表格、代码块、链接等等。
```

只有 `type` 是必填的，其他字段按需使用。自定义字段可以随便加。

### 预留文件名

| 文件名 | 作用 |
|:---|:---|
| `index.md` | 目录入口页，链接到该目录下的概念 |
| `log.md` | 按时间记录的变更历史 |

---

## 这个 skill 做什么

`okf` 是一个**零依赖、通用、可移植**的 OKF 工具包。八个命令覆盖知识库的完整生命周期：

| 命令 | 做什么 |
|:---|:---|
| `okf init` | 初始化知识库，生成 `.okfconfig.json` |
| `okf create "Runbook" --title "DB宕机"` | 创建带标准 frontmatter 的新概念 |
| `okf scan` | 扫描目录，告诉你每个文件适合什么 type |
| `okf migrate --apply` | 批量给旧 markdown 补上 OKF 字段 |
| `okf serve` | 一行启动可视化浏览器（零后端） |
| `okf validate` | 校验目录是否符合 OKF v0.1 规范 |
| `okf index --recursive` | 递归生成 index.md 导航 |
| `okf check file.md` | 单文件快速诊断 |

## 快速上手

```bash
# 1. 初始化
okf init ./my-knowledge --title "我的知识库"

# 2. 创建概念
okf create "Runbook" --title "数据库宕机处理" \
  --description "主库不可访问时的操作步骤" \
  --tags "incident,sre" --path ./my-knowledge/runbooks/

# 3. 扫描现有文件
okf scan ./my-knowledge/ --verbose

# 4. 批量迁移（给旧文件补 frontmatter）
okf migrate ./my-knowledge/ --apply

# 5. 校验
okf validate ./my-knowledge/

# 6. 浏览
okf serve ./my-knowledge/
# → 浏览器打开 http://localhost:3000
```

## 可视化浏览器（okf serve）

![okf serve 截图预览]

一行命令，零额外依赖（纯 Python stdlib），启动后浏览器打开就能看到：

- **左侧目录树**：按文件层级组织的所有概念
- **搜索**：实时过滤标题、类型、路径
- **概念详情**：type 徽章、元数据网格、标签、markdown 正文渲染
- **关联导航**：自动解析正文中的 `.md` 链接，展示关联概念
- **概念图谱**：力导向图展示所有概念之间的链接关系
- **按类型浏览**：首页按 type 分组，点进去看该类型的全部概念

## Type 自动检测

`okf migrate` 和 `okf scan` 会用三段式策略推导 type：

1. **从已有 frontmatter**：如果已有 `type` 就用它；如果有 `platform` 字段 → `Social Post`
2. **从正文内容**：检测到社媒链接 → `Social Post`；检测到数据库关键词 → `Database Table`
3. **从路径规则**：匹配 `.okfconfig.json` 里的 `type_rules`
4. **兜底**：用 `default_type`（默认 `Note`）

## 配置（.okfconfig.json）

```json
{
  "version": "0.1",
  "title": "我的知识库",
  "type_rules": [
    {"pattern": "runbooks/", "type": "Runbook"},
    {"pattern": "schemas/", "type": "Database Table"},
    {"pattern": "blog/", "type": "Blog Post"}
  ],
  "default_type": "Note",
  "index_dirs": ["runbooks", "schemas", "blog"]
}
```

## 和 cohub-silo 配合

OKF 的 frontmatter 字段和 cohub-silo 的 SED 格式天然映射：

```
OKF type        → silo entity_type
OKF title       → silo title  
OKF description → silo description
OKF tags        → silo tags
OKF resource    → silo source
```

用 `okf` 管理的 markdown 可以直接被 silo 索引，实现：
**okf 管格式 → silo 管检索 → Web 前端可浏览可搜索**

## 规范参考

详见 `reference/spec.md`——OKF v0.1 完整一致性标准（M1-M6 强制 + S1-S6 建议）。

---

> **核心信念：不申请、不付钱、不登录。**  
> 知识应该活在你的文件系统里，而不是某个平台的后台里。
