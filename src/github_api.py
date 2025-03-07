import requests
from typing import List, Dict, Any, Optional
import time
import json
import os
from datetime import datetime


def fetch_github_issues(owner: str, repo: str, token: Optional[str] = None, 
                        state: str = "all", per_page: int = 100) -> List[Dict[Any, Any]]:
    """
    Fetch all issues from a GitHub repository including their comments.
    
    Args:
        owner: GitHub repository owner (username or organization)
        repo: Repository name
        token: GitHub personal access token for authentication (optional but recommended to avoid rate limits)
        state: Issue state to fetch ('open', 'closed', or 'all')
        per_page: Number of issues to fetch per request (max 100)
        
    Returns:
        List of dictionaries containing issue data with comments
    """
    issues = []
    page = 1
    headers = {}
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    while True:
        # Fetch issues
        issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "sort": "created",
            "direction": "asc"
        }
        
        response = requests.get(issues_url, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch issues: {response.status_code} - {response.text}")
        
        batch = response.json()
        if not batch:
            break
            
        # For each issue, fetch its comments
        for issue in batch:
            # Skip pull requests (they're also returned by the issues API)
            if "pull_request" in issue:
                continue
                
            # Fetch comments for this issue
            comments_url = issue["comments_url"]
            comments_response = requests.get(comments_url, headers=headers)
            
            if comments_response.status_code == 200:
                issue["comment_data"] = comments_response.json()
            else:
                issue["comment_data"] = []
                
            issues.append(issue)
            
            # Respect GitHub API rate limits
            time.sleep(0.5)
        
        page += 1
        
        # Check if we've reached the last page
        if len(batch) < per_page:
            break
            
        # Respect GitHub API rate limits
        time.sleep(1)
    
    return issues


def extract_issue_qa(issues: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
    """
    Extract question-answer pairs from GitHub issues.
    
    Args:
        issues: List of GitHub issues with comments
        
    Returns:
        List of dictionaries with question-answer pairs
    """
    qa_pairs = []
    
    for issue in issues:
        # Skip pull requests
        if "pull_request" in issue:
            continue
            
        # The issue body is the question
        question = issue["title"] + "\n\n" + (issue["body"] or "")
        
        # Comments are potential answers
        comments = issue.get("comment_data", [])
        
        if not comments:
            # If there are no comments, create a QA pair with empty answer
            # This can be useful for unanswered questions
            qa_pairs.append({
                "question": question,
                "answers": [],
                "issue_number": issue["number"],
                "issue_url": issue["html_url"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "state": issue["state"],
                "labels": [label["name"] for label in issue["labels"]],
                "has_accepted_answer": False
            })
        else:
            # Extract all answers
            answers = []
            issue_owner = issue["user"]["login"]
            
            for comment in comments:
                commenter = comment["user"]["login"]
                answer_text = comment["body"]
                
                # Skip empty comments
                if not answer_text.strip():
                    continue
                    
                answer = {
                    "author": commenter,
                    "author_url": comment["user"]["html_url"],
                    "content": answer_text,
                    "created_at": comment["created_at"],
                    "updated_at": comment["updated_at"],
                    # Consider a comment from the issue author as a clarification rather than an answer
                    "is_clarification": commenter == issue_owner,
                    # Consider the last comment from a repo owner/maintainer as potentially accepted
                    "is_from_maintainer": comment.get("author_association") in ["OWNER", "MEMBER", "COLLABORATOR"]
                }
                answers.append(answer)
            
            # Determine if there's an accepted answer
            # Heuristic: if issue is closed and last comment is from maintainer
            has_accepted_answer = False
            if issue["state"] == "closed" and answers and answers[-1]["is_from_maintainer"]:
                has_accepted_answer = True
                answers[-1]["is_accepted"] = True
            
            qa_pairs.append({
                "question": question,
                "answers": answers,
                "issue_number": issue["number"],
                "issue_url": issue["html_url"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "state": issue["state"],
                "labels": [label["name"] for label in issue["labels"]],
                "has_accepted_answer": has_accepted_answer
            })
    
    return qa_pairs


def organize_issue_discussions(issues: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
    """
    Organize each issue into a structured format with topic and individual responses.
    
    Args:
        issues: List of GitHub issues with comments
        
    Returns:
        List of dictionaries with organized issue discussions
    """
    organized_issues = []
    
    for issue in issues:
        # Skip pull requests
        if "pull_request" in issue:
            continue
            
        # Extract basic issue information
        issue_data = {
            "issue_number": issue["number"],
            "issue_url": issue["html_url"],
            "title": issue["title"],
            "created_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "closed_at": issue["closed_at"],
            "state": issue["state"],
            "labels": [label["name"] for label in issue["labels"]],
            "topic": {
                "author": issue["user"]["login"],
                "author_url": issue["user"]["html_url"],
                "content": issue["body"] or "",
                "created_at": issue["created_at"]
            },
            "responses": []
        }
        
        # Extract comments/responses
        comments = issue.get("comment_data", [])
        for comment in comments:
            response = {
                "author": comment["user"]["login"],
                "author_url": comment["user"]["html_url"],
                "content": comment["body"] or "",
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"]
            }
            issue_data["responses"].append(response)
        
        organized_issues.append(issue_data)
    
    return organized_issues


def export_to_json(data: Any, filepath: str, pretty: bool = True) -> str:
    """
    Export data to a JSON file.
    
    Args:
        data: Data to export (issues or QA pairs)
        filepath: Path to save the JSON file
        pretty: Whether to format the JSON with indentation for readability
        
    Returns:
        Path to the saved JSON file
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    
    # Write to JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False)
    
    return filepath


def export_issues_to_json(issues: List[Dict[Any, Any]], 
                          output_dir: str = "data", 
                          filename: Optional[str] = None) -> str:
    """
    Export GitHub issues to a JSON file.
    
    Args:
        issues: List of GitHub issues
        output_dir: Directory to save the JSON file
        filename: Custom filename (default: github_issues_YYYY-MM-DD.json)
        
    Returns:
        Path to the saved JSON file
    """
    if not filename:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"github_issues_{date_str}.json"
    
    filepath = os.path.join(output_dir, filename)
    return export_to_json(issues, filepath)


def export_qa_pairs_to_json(qa_pairs: List[Dict[str, Any]], 
                           output_dir: str = "data", 
                           filename: Optional[str] = None) -> str:
    """
    Export question-answer pairs to a JSON file.
    
    Args:
        qa_pairs: List of question-answer pairs
        output_dir: Directory to save the JSON file
        filename: Custom filename (default: github_qa_YYYY-MM-DD.json)
        
    Returns:
        Path to the saved JSON file
    """
    if not filename:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"github_qa_{date_str}.json"
    
    filepath = os.path.join(output_dir, filename)
    return export_to_json(qa_pairs, filepath)


def export_organized_issues_to_json(organized_issues: List[Dict[str, Any]],
                                   output_dir: str = "data",
                                   filename: Optional[str] = None) -> str:
    """
    Export organized issue discussions to a JSON file.
    
    Args:
        organized_issues: List of organized issue discussions
        output_dir: Directory to save the JSON file
        filename: Custom filename (default: github_discussions_YYYY-MM-DD.json)
        
    Returns:
        Path to the saved JSON file
    """
    if not filename:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"github_discussions_{date_str}.json"
    
    filepath = os.path.join(output_dir, filename)
    return export_to_json(organized_issues, filepath)


def load_json_data(filepath: str) -> Any:
    """
    Load data from a JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Loaded data (issues or QA pairs)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


if __name__ == "__main__":
    # Example usage
    owner = "tensorflow"
    repo = "tensorflow"
    
    # It's better to use a token to avoid rate limits
    # token = "your_github_token"
    token = None
    
    try:
        # Fetch only a few issues for demonstration
        issues = fetch_github_issues(owner, repo, token, per_page=5)
        qa_pairs = extract_issue_qa(issues)
        
        # Organize issues by topic and responses
        organized_issues = organize_issue_discussions(issues)
        
        print(f"Fetched {len(issues)} issues and extracted {len(qa_pairs)} QA pairs")
        print(f"Organized {len(organized_issues)} issue discussions")
        
        # Export to JSON
        issues_file = export_issues_to_json(issues)
        qa_file = export_qa_pairs_to_json(qa_pairs)
        discussions_file = export_organized_issues_to_json(organized_issues)
        
        print(f"Issues exported to: {issues_file}")
        print(f"QA pairs exported to: {qa_file}")
        print(f"Organized discussions exported to: {discussions_file}")
        
        # Example of loading the data back
        loaded_issues = load_json_data(issues_file)
        print(f"Loaded {len(loaded_issues)} issues from JSON file")
        
    except Exception as e:
        print(f"Error: {e}") 