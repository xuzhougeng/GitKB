#!/usr/bin/env python3
"""
快速运行脚本，用于从 GitHub 仓库获取 issues 并生成知识库
使用方法: python run.py https://github.com/username/repo [--token TOKEN] [--model MODEL]
         python run.py --json issues.json [--model MODEL]
"""

import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

# 导入项目模块
try:
    from src.github_api import (
        fetch_github_issues,
        extract_issue_qa,
        organize_issue_discussions,
        export_issues_to_json,
        export_qa_pairs_to_json,
        export_organized_issues_to_json,
        load_json_data
    )
    from src.llm import process_github_qa, export_qa_to_markdown
except ImportError:
    print("错误: 无法导入项目模块。请确保您在项目根目录中运行此脚本。")
    sys.exit(1)

def parse_github_url(url):
    """从 GitHub URL 中提取用户名和仓库名"""
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"无效的 GitHub URL: {url}")
    return match.group(1), match.group(2)

def ensure_directory(directory):
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)

def main():
    parser = argparse.ArgumentParser(description="从 GitHub 仓库获取 issues 并生成知识库")
    
    # 创建互斥组，用户必须提供 repo_url 或 json_file 其中之一
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", dest="repo_url", help="GitHub 仓库 URL，例如 https://github.com/username/repo")
    group.add_argument("--json", dest="json_file", help="已有的 issues JSON 文件路径，跳过获取 issues 步骤")
    
    parser.add_argument("--token", help="GitHub API 令牌")
    parser.add_argument("--output-dir", default="output", help="输出目录")
    parser.add_argument("--use-llm", action="store_true", help="使用 LLM 处理问答对")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="LLM 模型名称，例如 gpt-3.5-turbo 或 volcengine/<ENDPOINT_ID>")
    parser.add_argument("--max-issues", type=int, default=None, help="最多获取的 issues 数量")
    
    args = parser.parse_args()
    
    try:
        # 确保输出目录存在
        output_dir = args.output_dir
        ensure_directory(output_dir)
        
        # 处理流程分支：从 URL 获取 issues 或从 JSON 文件加载
        if args.repo_url:
            # 从 URL 获取 issues
            owner, repo = parse_github_url(args.repo_url)
            print(f"正在处理仓库: {owner}/{repo}")
            
            # 获取 issues
            print(f"正在获取 issues...")
            issues = fetch_github_issues(owner, repo, args.token)
            
            # 如果设置了最大 issues 数量，则截取
            if args.max_issues and len(issues) > args.max_issues:
                issues = issues[:args.max_issues]
                
            print(f"获取到 {len(issues)} 个 issues")
            
            # 导出原始 issues
            issues_file = export_issues_to_json(issues, output_dir=output_dir)
            print(f"原始 issues 已导出到: {issues_file}")
            
            # 提取问答对
            qa_pairs = extract_issue_qa(issues)
            qa_file = export_qa_pairs_to_json(qa_pairs, output_dir=output_dir)
            print(f"问答对已导出到: {qa_file}")
            
            # 组织讨论
            organized_issues = organize_issue_discussions(issues)
            discussions_file = export_organized_issues_to_json(organized_issues, output_dir=output_dir)
            print(f"组织的讨论已导出到: {discussions_file}")
            
            # 生成基本 Markdown 知识库
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            basic_md_file = os.path.join(output_dir, f"knowledge_base_{timestamp}.md")
            
            with open(basic_md_file, "w", encoding="utf-8") as f:
                f.write(f"# {repo} 知识库\n\n")
                f.write(f"从 GitHub 仓库 [{owner}/{repo}]({args.repo_url}) 生成的知识库\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                
                for qa in qa_pairs:
                    f.write(f"## {qa['issue_number']}. {qa.get('question', '').split('\\n')[0]}\n\n")
                    
                    if not qa.get('answers', []):
                        f.write("*暂无答案*\n\n")
                    else:
                        for i, answer in enumerate(qa['answers'], 1):
                            prefix = "**接受的答案**" if answer.get('is_accepted') else f"**答案 {i}**"
                            author_info = f"由 [{answer['author']}]({answer['author_url']}) 提供"
                            f.write(f"{prefix} {author_info}\n\n{answer['content']}\n\n")
                    
                    f.write(f"[在 GitHub 上查看]({qa['issue_url']})\n\n---\n\n")
            
            print(f"基本知识库已生成: {basic_md_file}")
            
        else:
            # 从 JSON 文件加载 issues
            issues_file = args.json_file
            print(f"从文件加载 issues: {issues_file}")
            
            if not os.path.exists(issues_file):
                raise FileNotFoundError(f"找不到文件: {issues_file}")
                
            # 验证是否为有效的 JSON 文件
            try:
                issues = load_json_data(issues_file)
                print(f"成功加载 {len(issues)} 个 issues")
            except Exception as e:
                raise ValueError(f"无法加载 JSON 文件: {str(e)}")
        
        # LLM 处理（无论是从 URL 获取还是从 JSON 加载）
        if args.use_llm or args.json_file:  # 如果使用 --json 参数，默认进行 LLM 处理
            try:
                print(f"正在使用 LLM ({args.model}) 处理问答对...")
                
                # 检查是否设置了相关环境变量
                if "openai" in args.model.lower() and "OPENAI_API_KEY" not in os.environ:
                    print("警告: 未设置 OPENAI_API_KEY 环境变量")
                elif "volcengine" in args.model.lower() and "VOLCENGINE_API_KEY" not in os.environ:
                    print("警告: 未设置 VOLCENGINE_API_KEY 环境变量")
                
                # 处理问答对
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                qa_data, llm_json_file = process_github_qa(
                    issues_file=issues_file,
                    model=args.model,
                    output_file=os.path.join(output_dir, f"llm_qa_{timestamp}.json")
                )
                
                # 导出为 Markdown
                llm_md_file = os.path.join(output_dir, f"llm_knowledge_base_{timestamp}.md")
                export_qa_to_markdown(qa_data, llm_md_file)
                
                print(f"LLM 处理的知识库已生成: {llm_md_file}")
                
            except Exception as e:
                print(f"LLM 处理时出错: {str(e)}")
                print("跳过 LLM 处理步骤")
        
        print("\n处理完成!")
        print(f"所有输出文件已保存到目录: {output_dir}")
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 