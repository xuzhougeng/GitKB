import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import litellm
from tqdm import tqdm

def extract_qa_with_llm(issue_data: Dict[str, Any], model: str, **kwargs) -> Dict[str, Any]:
    """
    使用 LLM 从 GitHub issue 讨论中提取高质量问答对
    
    Args:
        issue_data: GitHub issue 数据
        model: 要使用的模型名称，例如 "gpt-3.5-turbo" 或 "volcengine/<ENDPOINT_ID>"
        **kwargs: 传递给 litellm.completion 的额外参数
        
    Returns:
        包含提取的问答对的字典
    """
    if not model:
        raise ValueError("必须指定模型名称，例如 'gpt-3.5-turbo' 或 'volcengine/<ENDPOINT_ID>'")
        
    # 构建提示
    title = issue_data.get("title", "")
    body = issue_data.get("body", "") or ""
    
    # 获取所有评论
    comments = issue_data.get("comment_data", [])
    comments_text = ""
    
    for i, comment in enumerate(comments, 1):
        author = comment.get("user", {}).get("login", "Unknown")
        content = comment.get("body", "")
        comments_text += f"\n\n评论 {i} (作者: {author}):\n{content}"
    
    prompt = f"""作为一个专业的知识提取专家，请从以下 GitHub issue 讨论中提取出高质量的问答对。
    
问题标题: {title}

问题描述: 
{body}

讨论评论: {comments_text}

请分析上述内容，提取出最有价值的问答信息，按以下格式输出:
1. 提取一个清晰、简洁的问题，确保问题是完整的，并包含必要的上下文
2. 提取最佳答案，如果有多个有价值的答案，请合并它们
3. 如果原始问题不清晰但从讨论中可以推断，请重新表述问题
4. 忽略无关的讨论、致谢或其他非技术内容
5. 如果没有明确的答案，请说明"没有找到明确答案"

输出格式 (JSON):
{{
  "extracted_question": "清晰、完整的问题",
  "extracted_answer": "最佳答案或合并的答案",
  "confidence": 0-1之间的数字，表示提取质量的置信度,
  "multiple_answers": true/false,
  "needs_more_info": true/false
}}

只返回 JSON 格式的结果，不要有其他文字。
"""

    try:
        # 准备模型参数
        completion_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1500
        }
        
        # 添加用户提供的额外参数
        completion_kwargs.update(kwargs)
        
        # 调用 LiteLLM
        response = litellm.completion(**completion_kwargs)
        
        # 提取 JSON 内容
        content = response.choices[0].message.content.strip()
        
        # 处理可能的非 JSON 响应
        try:
            # 尝试找到 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            result = json.loads(content)
            
            # 添加原始 issue 信息
            result["issue_number"] = issue_data.get("number")
            result["issue_url"] = issue_data.get("html_url")
            result["original_title"] = title
            
            return result
        except json.JSONDecodeError:
            return {
                "error": "无法解析 LLM 响应为 JSON",
                "raw_response": content,
                "issue_number": issue_data.get("number"),
                "issue_url": issue_data.get("html_url")
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "issue_number": issue_data.get("number"),
            "issue_url": issue_data.get("html_url")
        }

def batch_process_issues(issues: List[Dict[str, Any]], 
                         model: str,
                         batch_size: int = 10,
                         max_workers: int = 5,
                         rate_limit_pause: float = 1.0,
                         **kwargs) -> List[Dict[str, Any]]:
    """
    批量处理 GitHub issues，提取问答对
    
    Args:
        issues: GitHub issues 列表
        model: 要使用的模型名称
        batch_size: 每批处理的 issue 数量
        max_workers: 并行处理的最大线程数
        rate_limit_pause: 批次间暂停时间（秒）
        **kwargs: 传递给 litellm.completion 的额外参数
        
    Returns:
        提取的问答对列表
    """
    if not model:
        raise ValueError("必须指定模型名称，例如 'gpt-3.5-turbo' 或 'volcengine/<ENDPOINT_ID>'")
        
    results = []
    
    # 分批处理
    for i in range(0, len(issues), batch_size):
        batch = issues[i:i+batch_size]
        batch_results = []
        
        print(f"处理批次 {i//batch_size + 1}/{(len(issues) + batch_size - 1)//batch_size}，共 {len(batch)} 个 issues")
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 使用 tqdm 显示进度
            batch_results = list(tqdm(
                executor.map(lambda issue: extract_qa_with_llm(issue, model, **kwargs), batch),
                total=len(batch),
                desc="提取问答对"
            ))
            
        results.extend(batch_results)
        
        # 暂停以避免速率限制
        if i + batch_size < len(issues):
            print(f"暂停 {rate_limit_pause} 秒以避免速率限制...")
            time.sleep(rate_limit_pause)
    
    return results

def filter_high_quality_qa(qa_results: List[Dict[str, Any]], 
                          min_confidence: float = 0.7,
                          exclude_needs_more_info: bool = True) -> List[Dict[str, Any]]:
    """
    过滤高质量的问答对
    
    Args:
        qa_results: 从 LLM 提取的问答对列表
        min_confidence: 最小置信度阈值
        exclude_needs_more_info: 是否排除需要更多信息的问答对
        
    Returns:
        过滤后的高质量问答对列表
    """
    filtered_results = []
    
    for qa in qa_results:
        # 跳过有错误的结果
        if "error" in qa:
            continue
            
        # 检查置信度
        if qa.get("confidence", 0) < min_confidence:
            continue
            
        # 检查是否需要更多信息
        if exclude_needs_more_info and qa.get("needs_more_info", False):
            continue
            
        # 确保有问题和答案
        if not qa.get("extracted_question") or not qa.get("extracted_answer") or qa.get("extracted_answer") == "没有找到明确答案":
            continue
            
        filtered_results.append(qa)
    
    return filtered_results

def process_github_qa(issues_file: str, 
                     model: str,
                     output_file: Optional[str] = None,
                     batch_size: int = 10,
                     max_workers: int = 5,
                     min_confidence: float = 0.7,
                     **kwargs) -> Tuple[List[Dict[str, Any]], str]:
    """
    处理 GitHub 问答数据的主函数
    
    Args:
        issues_file: GitHub issues JSON 文件路径
        model: 要使用的模型名称，例如 "gpt-3.5-turbo" 或 "volcengine/<ENDPOINT_ID>"
        output_file: 输出文件路径，如果为 None 则自动生成
        batch_size: 每批处理的 issue 数量
        max_workers: 并行处理的最大线程数
        min_confidence: 过滤结果的最小置信度
        **kwargs: 传递给 litellm.completion 的额外参数
        
    Returns:
        (处理后的问答对列表, 输出文件路径)
    """
    if not model:
        raise ValueError("必须指定模型名称，例如 'gpt-3.5-turbo' 或 'volcengine/<ENDPOINT_ID>'")
        
    # 加载 issues
    with open(issues_file, 'r', encoding='utf-8') as f:
        issues = json.load(f)
    
    print(f"加载了 {len(issues)} 个 GitHub issues")
    print(f"使用模型: {model}")
    
    # 批量处理
    qa_results = batch_process_issues(
        issues, 
        model=model,
        batch_size=batch_size,
        max_workers=max_workers,
        **kwargs
    )
    
    # 过滤高质量结果
    filtered_results = filter_high_quality_qa(
        qa_results,
        min_confidence=min_confidence
    )
    
    print(f"从 {len(issues)} 个 issues 中提取了 {len(qa_results)} 个问答对")
    print(f"过滤后得到 {len(filtered_results)} 个高质量问答对")
    
    # 保存结果
    if output_file is None:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file = f"data/llm_qa_{date_str}.json"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_results, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存到 {output_file}")
    
    return filtered_results, output_file

def export_qa_to_markdown(qa_data: List[Dict[str, Any]], output_file: str = "data/qa_knowledge_base.md"):
    """
    将问答对导出为 Markdown 格式
    
    Args:
        qa_data: 问答对列表
        output_file: 输出文件路径
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# GitHub 知识库\n\n")
        f.write("*自动从 GitHub issues 提取的问答对*\n\n")
        f.write("---\n\n")
        
        for i, qa in enumerate(qa_data, 1):
            question = qa.get("extracted_question", "")
            answer = qa.get("extracted_answer", "")
            issue_url = qa.get("issue_url", "")
            
            f.write(f"## Q{i}: {question}\n\n")
            f.write(f"{answer}\n\n")
            
            if issue_url:
                f.write(f"[查看原始讨论]({issue_url})\n\n")
            
            f.write("---\n\n")
    
    print(f"Markdown 知识库已保存到 {output_file}")

if __name__ == "__main__":
    # 示例用法
    import argparse
    
    parser = argparse.ArgumentParser(description="使用 LLM 从 GitHub issues 提取高质量问答对")
    parser.add_argument("--issues_file", required=True, help="GitHub issues JSON 文件路径")
    parser.add_argument("--model", required=True, help="要使用的模型名称，例如 gpt-3.5-turbo 或 volcengine/<ENDPOINT_ID>")
    parser.add_argument("--output_file", help="输出 JSON 文件路径")
    parser.add_argument("--markdown_file", help="输出 Markdown 文件路径")
    parser.add_argument("--batch_size", type=int, default=10, help="每批处理的 issue 数量")
    parser.add_argument("--max_workers", type=int, default=5, help="并行处理的最大线程数")
    parser.add_argument("--min_confidence", type=float, default=0.7, help="过滤结果的最小置信度")
    parser.add_argument("--temperature", type=float, default=0.1, help="模型温度参数")
    parser.add_argument("--max_tokens", type=int, default=1500, help="模型最大生成令牌数")
    
    args = parser.parse_args()
    
    # 准备模型参数
    kwargs = {
        "temperature": args.temperature,
        "max_tokens": args.max_tokens
    }
    
    # 处理 GitHub 问答数据
    qa_data, output_file = process_github_qa(
        issues_file=args.issues_file,
        model=args.model,
        output_file=args.output_file,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        min_confidence=args.min_confidence,
        **kwargs
    )
    
    # 导出为 Markdown
    if args.markdown_file:
        export_qa_to_markdown(qa_data, args.markdown_file)
    else:
        markdown_file = output_file.replace(".json", ".md")
        export_qa_to_markdown(qa_data, markdown_file)
