# GitHub 知识库项目结构

本文档介绍 GitHub 知识库项目的整体结构和各个组件的功能。

## 目录结构

```
github_knowledge/
├── src/                    # 源代码目录
│   ├── github_api.py       # GitHub API 交互模块
│   └── llm.py              # LLM 处理模块
├── docs/                   # 文档目录
│   └── project_structure.md # 项目结构文档
├── data/                   # 数据存储目录（自动创建）
│   ├── github_issues_*.json # GitHub issues 原始数据
│   ├── github_qa_*.json    # 提取的问答对数据
│   ├── github_discussions_*.json # 组织的讨论数据
│   └── llm_qa_*.json       # LLM 处理后的问答数据
└── README.md               # 项目说明文档
```

## 核心模块

### github_api.py

GitHub API 交互模块，负责从 GitHub 获取数据并进行初步处理。

#### 主要功能

1. **获取 GitHub Issues**
   - `fetch_github_issues()`: 从指定仓库获取所有 issues 及其评论
   - 支持分页和速率限制
   - 过滤掉拉取请求

2. **提取问答对**
   - `extract_issue_qa()`: 从 issues 中提取结构化的问答对
   - 识别问题、多个答案、澄清和接受的答案

3. **组织讨论**
   - `organize_issue_discussions()`: 将 issues 组织为主题和响应的结构

4. **数据导出**
   - `export_issues_to_json()`: 导出原始 issues 数据
   - `export_qa_pairs_to_json()`: 导出提取的问答对
   - `export_organized_issues_to_json()`: 导出组织的讨论
   - `export_to_json()`: 通用 JSON 导出函数

5. **数据加载**
   - `load_json_data()`: 从 JSON 文件加载数据

### llm.py

LLM 处理模块，使用大型语言模型从 GitHub issues 中提取高质量问答对。

#### 主要功能

1. **LLM 问答提取**
   - `extract_qa_with_llm()`: 使用 LLM 从单个 issue 中提取问答对
   - 支持任意 LiteLLM 兼容的模型（OpenAI、火山引擎等）

2. **批量处理**
   - `batch_process_issues()`: 批量处理 issues，支持并行处理
   - 内置速率限制保护

3. **质量过滤**
   - `filter_high_quality_qa()`: 基于置信度过滤高质量问答对

4. **主处理流程**
   - `process_github_qa()`: 处理 GitHub 问答数据的主函数
   - 集成加载、处理、过滤和导出功能

5. **Markdown 导出**
   - `export_qa_to_markdown()`: 将问答对导出为 Markdown 格式

## 数据流

1. 使用 `github_api.py` 从 GitHub 获取 issues 数据
2. 可以直接使用 `extract_issue_qa()` 提取基本问答对
3. 或者使用 `llm.py` 中的 `process_github_qa()` 进行更深入的分析
4. 结果可以导出为 JSON 或 Markdown 格式

## 使用流程

1. **基本使用**
   ```python
   from src.github_api import fetch_github_issues, export_issues_to_json
   
   # 获取 issues
   issues = fetch_github_issues("username", "repo", token)
   
   # 导出 issues
   export_issues_to_json(issues)
   ```

2. **提取问答对**
   ```python
   from src.github_api import extract_issue_qa, export_qa_pairs_to_json
   
   # 提取问答对
   qa_pairs = extract_issue_qa(issues)
   
   # 导出问答对
   export_qa_pairs_to_json(qa_pairs)
   ```

3. **LLM 处理**
   ```python
   from src.llm import process_github_qa
   import os
   
   # 设置 API 密钥
   os.environ["OPENAI_API_KEY"] = "your_api_key"
   
   # 处理问答数据
   qa_data, output_file = process_github_qa(
       issues_file="data/github_issues.json",
       model="gpt-3.5-turbo"
   )
   ```

## 命令行使用

项目支持通过命令行使用 LLM 处理功能：

```bash
# 设置环境变量
export OPENAI_API_KEY="your_api_key"

# 运行 LLM 处理
python -m src.llm --issues_file data/github_issues.json --model gpt-3.5-turbo
``` 