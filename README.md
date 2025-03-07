# GitHub 知识库

从 GitHub 问题构建知识库的工具。

## 特点

- 从 GitHub 存储库获取所有问题
- 从问题及其评论中提取问题-答案对
  - 支持每个问题的多个答案
  - 识别接受的答案和澄清
- 按主题和个体响应组织问题
- 支持分页和速率限制
- 将问题和问题-答案对导出为 JSON，方便存储和加载
- 使用 LLM 从讨论中提取高质量问题-答案对
  - 支持任意 LiteLLM 兼容的模型（OpenAI、火山引擎等）

## 项目结构

查看 [项目结构文档](docs/project_structure.md) 了解详细的项目组织和各模块功能。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

项目提供了一个便捷的运行脚本，可以直接从 GitHub 仓库 URL 获取 issues 并生成知识库：

```bash
# 基本用法
python run.py --url https://github.com/username/repo

# 使用 GitHub 令牌（推荐，避免 API 速率限制）
python run.py --url https://github.com/username/repo --token YOUR_GITHUB_TOKEN

# 使用 LLM 处理（需要设置相应的 API 密钥环境变量）
python run.py --url https://github.com/username/repo --use-llm --model gpt-3.5-turbo

# 使用火山引擎模型
export VOLCENGINE_API_KEY="your_volcengine_api_key"
python run.py --url https://github.com/username/repo --use-llm --model volcengine/<ENDPOINT_ID>

# 限制获取的 issues 数量
python run.py --url https://github.com/username/repo --max-issues 50

# 指定输出目录
python run.py --url https://github.com/username/repo --output-dir my_knowledge_base

# 从已有的 JSON 文件继续 LLM 处理（跳过获取 issues 步骤）
python run.py --json data/github_issues_2023-07-25.json --model gpt-3.5-turbo
```

脚本会自动：
1. 获取指定仓库的 issues（或从 JSON 文件加载）
2. 提取问答对
3. 组织讨论
4. 生成基本的 Markdown 知识库
5. 如果启用 LLM，还会生成经过 LLM 处理的高质量知识库

所有输出文件都会保存在指定的输出目录中（默认为 `output/`）。

## GitHub API 令牌

为了避免从 GitHub 获取数据时的速率限制，建议使用个人访问令牌：

1. 进入你的 GitHub 账户设置：https://github.com/settings/tokens
2. 点击"生成新令牌"（经典）
3. 为你的令牌取一个描述性的名字
4. 选择以下范围：
   - `repo`（如果访问私有存储库）
   - `read:org`（如果访问组织存储库）
   - 对于公共存储库，你可以只使用 `public_repo`
5. 点击"生成令牌"
6. 立即复制令牌（你将无法再次看到它）

出于安全考虑，永远不要将你的令牌提交到版本控制。考虑使用环境变量：

```python
import os
token = os.environ.get("GITHUB_TOKEN")
```

## 使用

```python
from src.github_api import (
    fetch_github_issues, 
    extract_issue_qa, 
    organize_issue_discussions,
    export_issues_to_json, 
    export_qa_pairs_to_json,
    export_organized_issues_to_json,
    load_json_data
)

# 设置你的存储库详情
owner = "username"
repo = "repository"

# 可选：GitHub 令牌进行身份验证（建议以避免速率限制）
token = "your_github_token"  # 或 None

# 获取问题
issues = fetch_github_issues(owner, repo, token)

# 导出问题为 JSON（默认保存到 data/github_issues_YYYY-MM-DD.json）
issues_file = export_issues_to_json(issues)
print(f"问题已导出到：{issues_file}")

# 提取问题-答案对
qa_pairs = extract_issue_qa(issues)

# 导出问题-答案对为 JSON（默认保存到 data/github_qa_YYYY-MM-DD.json）
qa_file = export_qa_pairs_to_json(qa_pairs)
print(f"问题-答案对已导出到：{qa_file}")

# 按主题和个体响应组织问题
organized_issues = organize_issue_discussions(issues)

# 导出组织讨论为 JSON
discussions_file = export_organized_issues_to_json(organized_issues)
print(f"组织讨论已导出到：{discussions_file}")

# 以后从 JSON 文件加载数据
loaded_issues = load_json_data(issues_file)
loaded_qa = load_json_data(qa_file)
loaded_discussions = load_json_data(discussions_file)

# 使用问题-答案对构建你的知识库
with open("qa.md", "w") as f:
    for qa in qa_pairs:
        f.write(f"## 问题\n{qa['question']}\n\n")
        if not qa['answers']:
            f.write("*暂无答案*\n\n")
        else:
            for i, answer in enumerate(qa['answers'], 1):
                prefix = "**接受的答案**" if answer.get('is_accepted') else f"**答案 {i}**"
                author_info = f"由 [{answer['author']}]({answer['author_url']}) 提供"
                f.write(f"{prefix} {author_info}\n\n{answer['content']}\n\n")
        f.write(f"[在 GitHub 上查看]({qa['issue_url']})\n\n---\n\n")
```

## LLM 处理

该项目使用 LiteLLM 从 GitHub 问题中提取高质量问答对。LiteLLM 支持多种模型提供商，只需设置相应的环境变量：

### 基本用法

```python
from src.llm import process_github_qa, export_qa_to_markdown
import os

# 设置 OpenAI API 密钥
os.environ["OPENAI_API_KEY"] = "your_openai_api_key"

# 必须指定模型名称
qa_data, output_file = process_github_qa(
    issues_file="data/github_issues.json",
    model="gpt-3.5-turbo"  # 必须参数，没有默认值
)

# 导出为 Markdown
export_qa_to_markdown(qa_data, "data/knowledge_base.md")
```

### 使用火山引擎

```python
import os

# 设置火山引擎 API 密钥
os.environ["VOLCENGINE_API_KEY"] = "your_volcengine_api_key"

# 使用火山引擎模型
qa_data, output_file = process_github_qa(
    issues_file="data/github_issues.json",
    model="volcengine/<ENDPOINT_ID>"  # 必须指定模型名称
)
```

### 命令行使用

```bash
# 首先设置环境变量
export OPENAI_API_KEY="your_openai_api_key"
# 或
export VOLCENGINE_API_KEY="your_volcengine_api_key"

# 然后运行命令（必须指定 --model 参数）
python -m src.llm --issues_file data/github_issues.json --model gpt-3.5-turbo
# 或
python -m src.llm --issues_file data/github_issues.json --model volcengine/<ENDPOINT_ID>
```

### 自定义参数

```python
# 自定义模型参数
qa_data, output_file = process_github_qa(
    issues_file="data/github_issues.json",
    model="gpt-3.5-turbo",  # 必须参数
    temperature=0.2,
    max_tokens=2000,
    top_p=0.9
)
```

LLM 处理流程：
1. 分析每个问题及其评论
2. 提取清晰、简洁的问题
3. 将有价值的答案组合成全面的响应
4. 过滤掉低质量或不完整的问答对
5. 将结果导出为 JSON 和 Markdown 格式

## JSON 导出选项

JSON 导出函数提供了几个选项：

```python
# 自定义输出目录
export_issues_to_json(issues, output_dir="custom_dir")

# 自定义文件名
export_qa_pairs_to_json(qa_pairs, filename="my_qa_data.json")

# 自定义目录和文件名
export_issues_to_json(issues, output_dir="exports", filename="repo_issues.json")

# 导出时不使用漂亮的格式（文件大小更小）
export_to_json(data, filepath="data/compact.json", pretty=False)
```

## 组织的问题结构

`organize_issue_discussions` 函数为每个问题创建了一个结构化的格式：

```json
{
  "issue_number": 123,
  "issue_url": "https://github.com/username/repo/issues/123",
  "title": "问题标题",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-02T00:00:00Z",
  "closed_at": "2023-01-03T00:00:00Z",
  "state": "closed",
  "labels": ["bug", "documentation"],
  "topic": {
    "author": "username",
    "author_url": "https://github.com/username",
    "content": "问题描述...",
    "created_at": "2023-01-01T00:00:00Z"
  },
  "responses": [
    {
      "author": "commenter1",
      "author_url": "https://github.com/commenter1",
      "content": "评论文本...",
      "created_at": "2023-01-01T12:00:00Z",
      "updated_at": "2023-01-01T12:30:00Z"
    },
    {
      "author": "commenter2",
      "author_url": "https://github.com/commenter2",
      "content": "另一个评论...",
      "created_at": "2023-01-02T10:00:00Z",
      "updated_at": "2023-01-02T10:00:00Z"
    }
  ]
}
```

这个结构使得很容易分别处理原始主题和所有响应。

## 问题-答案结构

`extract_issue_qa` 函数为每个问题创建了一个结构化的格式：

```json
{
  "question": "我如何解决这个问题？\n\n我正在尝试...",
  "answers": [
    {
      "author": "helper1",
      "author_url": "https://github.com/helper1",
      "content": "你需要尝试这种方法...",
      "created_at": "2023-01-01T12:00:00Z",
      "updated_at": "2023-01-01T12:30:00Z",
      "is_clarification": false,
      "is_from_maintainer": true,
      "is_accepted": true
    },
    {
      "author": "helper2",
      "author_url": "https://github.com/helper2",
      "content": "另一种方法可能是...",
      "created_at": "2023-01-02T10:00:00Z",
      "updated_at": "2023-01-02T10:00:00Z",
      "is_clarification": false,
      "is_from_maintainer": false
    },
    {
      "author": "original_poster",
      "author_url": "https://github.com/original_poster",
      "content": "谢谢，那个方法有效！",
      "created_at": "2023-01-03T09:00:00Z",
      "updated_at": "2023-01-03T09:00:00Z",
      "is_clarification": true,
      "is_from_maintainer": false
    }
  ],
  "issue_number": 123,
  "issue_url": "https://github.com/username/repo/issues/123",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-03T09:00:00Z",
  "state": "closed",
  "labels": ["question", "solved"],
  "has_accepted_answer": true
}
```

这个结构提供了：
- 每个问题的所有答案，而不仅仅是第一个
- 识别原始发布者的澄清
- 识别存储库维护者的答案
- 启发式检测接受的答案（当问题关闭且最后一条评论来自维护者时）
- 支持未解答的问题

## 注意事项

- GitHub API 有速率限制。建议使用令牌。
- 脚本处理分页以获取所有问题。
- 从结果中过滤掉拉取请求。