# .github/workflows/helpers/ai_pr_reviewer.py
import os
import requests
import google.generativeai as genai
import sys

# Configuration
# Max characters of the diff to send to Gemini. Adjust if needed based on token limits and typical PR size.
# gemini-pro has a 32k token limit (input). ~4 chars/token. 25000 chars ~ 6250 tokens.
MAX_DIFF_CHARS = 25000
GEMINI_MODEL = "gemini-1.5-flash-latest"  # Use flash for speed and cost-effectiveness for this task


def fetch_pr_comments(github_token: str, repo: str, pr_number: str):
    # Fetch review comments
    reviews_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    # Fetch issue comments (general PR comments)
    issue_comments_url = (
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    )

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    all_comments = []

    try:
        # Get review comments
        response = requests.get(reviews_url, headers=headers, params={"per_page": 100})
        response.raise_for_status()
        reviews = response.json()
        for review in reviews:
            if review.get("body"):  # General review body
                all_comments.append(
                    {
                        "user": review["user"]["login"],
                        "body": review["body"],
                        "state": review.get("state"),
                    }
                )
            # Get comments made on specific lines within a review
            review_comments_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews/{review['id']}/comments"
            r_comments_resp = requests.get(review_comments_url, headers=headers)
            r_comments_resp.raise_for_status()
            for r_comment in r_comments_resp.json():
                all_comments.append(
                    {
                        "user": r_comment["user"]["login"],
                        "body": r_comment["body"],
                        "path": r_comment.get("path"),
                        "line": r_comment.get("line"),
                    }
                )

        # Get general issue comments on the PR
        response = requests.get(
            issue_comments_url, headers=headers, params={"per_page": 100}
        )
        response.raise_for_status()
        issue_comments = response.json()
        for comment in issue_comments:
            all_comments.append(
                {"user": comment["user"]["login"], "body": comment["body"]}
            )

    except requests.exceptions.RequestException as e:
        print(f"::error::Failed to fetch PR comments: {e}")
        return []
    return all_comments


def fetch_pr_diff(diff_url, github_token):
    """Fetches the diff content of a PR."""
    headers = {
        "Authorization": f"Bearer {github_token}",  # Use Bearer for GITHUB_TOKEN
        "Accept": "application/vnd.github.v3.diff",
    }
    try:
        response = requests.get(diff_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"::error::Failed to fetch PR diff from {diff_url}: {e}", file=sys.stderr)
        return None


def get_ai_review(api_key: str, diff_content: str) -> str:
    """Gets a code review from Google Gemini."""
    if not diff_content or not diff_content.strip():
        print("::info::No diff content to review.", file=sys.stderr)
        return "NO_REVIEW"

    if len(diff_content) > MAX_DIFF_CHARS:
        warning_msg = (
            f"Diff content is large ({len(diff_content)} chars). "
            f"Truncating to {MAX_DIFF_CHARS} chars for AI review. Full context may be lost."
        )
        print(f"::warning::{warning_msg}", file=sys.stderr)
        diff_content = (
            diff_content[:MAX_DIFF_CHARS] + "\n\n... (diff truncated due to length)"
        )
        # Inside get_ai_review, before generating the prompt
    # Assume GITHUB_BOT_USERNAME is an env var or constant with your bot's GitHub username
    bot_username = "github-actions"
    pr_comments = fetch_pr_comments(
        github_token, repo, pr_number
    )  # You'd pass these args

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = (
        "You are reviewing embedded C firmware.\n"
        "You are reviewing a Pull Request. The following is a unified diff of the changes and Pr comment history.\n"
        "Your task is to:\n"
        "1. Identify potential bugs, logical errors, or anti-patterns.\n"
        "2. Check for violations of embedded C/C++ best practices (e.g., resource management, "
        "volatile correctness, interrupt safety if inferable).\n"
        "3. Look for areas where code could be optimized for performance or clarity.\n"
        "4. Provide constructive feedback and suggested improvements if applicable, be concise\n"
        "5. If everything looks good, say so clearly.\n\n"
        "6. No one wants to read a novel, so keep it short and concise. Tokens cost money!!!\n"
        "7. Consider the previous conversation when formulating your new review points.\n"
        "8. If a point you previously made appears to be addressed or discussed, acknowledge that or refine your feedback.\n"
        "9. The current version of the diff you are seeing may already address issues previously commented on, you have the latest changes."
        "10. Use bullet points to divide comments refrencing differnt files, noting the file being refrenced. Github comments accept markdown\n"
        "Here is the previous conversation:\n"
        f"{pr_comments}\n"
        "Here is the diff:\n"
        f"{diff_content}"
    )

    try:
        # print the prompt for debugging
        print(f"::debug::Prompt for AI review:\n{prompt}", file=sys.stderr)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"::error::AI review failed: {e}", file=sys.stderr)
        return "AI_REVIEW_FAILED"


def post_pr_review(github_token: str, repo: str, pr_number: str, comment: str):
    """Posts a review comment to the specified PR using the GitHub API."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "body": comment,
        "event": "COMMENT",  # General comment without approving/rejecting
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"::info::Successfully posted review comment to PR #{pr_number}")
    except requests.exceptions.RequestException as e:
        print(
            f"::error::Failed to post review comment to PR #{pr_number}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    # First, try environment variables (GitHub Actions mode)
    gemini_api_key = os.getenv("GEMINI_API_KEY_SECRET")
    pr_diff_url = os.getenv("PR_DIFF_URL")
    github_token = os.getenv("GITHUB_TOKEN_SECRET")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number = os.getenv("PR_NUMBER")
    if gemini_api_key and pr_diff_url and github_token:
        diff_text = fetch_pr_diff(pr_diff_url, github_token)

        if diff_text is None:
            print("NO_REVIEW")
            sys.exit(0)

        if not diff_text.strip():
            print("::info::Diff is empty. No review needed.", file=sys.stderr)
            print("NO_REVIEW")
            sys.exit(0)

        review_comment = get_ai_review(gemini_api_key, diff_text)
        if review_comment == "NO_REVIEW":
            comment = "AI Code Review: No review generated due to empty diff content."
        elif review_comment == "AI_REVIEW_FAILED":
            comment = "AI Code Review: Failed to generate review due to an error."
        else:
            comment = f"AI Code Review:\n\n{review_comment}"

        # Post the review as a PR comment
        post_pr_review(github_token, repo, pr_number, comment)
        print(review_comment)  # Still print for logs

    else:
        # Local CLI mode: python ai_pr_reviewer.py <API_KEY> <diff_file>
        if len(sys.argv) != 3:
            print(
                "Usage: python ai_pr_reviewer.py <API_KEY> <diff_file>", file=sys.stderr
            )
            sys.exit(1)

        gemini_api_key = sys.argv[1]
        diff_file = sys.argv[2]

        try:
            with open(diff_file, "r", encoding="utf-8") as f:
                diff_text = f.read()
        except Exception as e:
            print(f"::error::Failed to read diff file: {e}", file=sys.stderr)
            sys.exit(1)

        review_comment = get_ai_review(gemini_api_key, diff_text)
        print("\n===== AI REVIEW =====\n")
        print(review_comment)
