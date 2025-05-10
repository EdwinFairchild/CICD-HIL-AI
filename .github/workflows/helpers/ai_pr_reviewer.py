# .github/workflows/helpers/ai_pr_reviewer.py
import os
import requests
import google.generativeai as genai
import sys

# Configuration
# Max characters of the diff to send to Gemini. Adjust if needed based on token limits and typical PR size.
# gemini-pro has a 32k token limit (input). ~4 chars/token. 25000 chars ~ 6250 tokens.
MAX_DIFF_CHARS = 25000 
GEMINI_MODEL = 'gemini-1.5-flash-latest' # Use flash for speed and cost-effectiveness for this task

def fetch_pr_diff(diff_url, github_token):
    """Fetches the diff content of a PR."""
    headers = {
        "Authorization": f"Bearer {github_token}", # Use Bearer for GITHUB_TOKEN
        "Accept": "application/vnd.github.v3.diff"
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
        diff_content = diff_content[:MAX_DIFF_CHARS] + "\n\n... (diff truncated due to length)"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = (
        "You are an expert code reviewer for embedded systems, particularly STM32 C/C++ projects.\n"
        "You are reviewing a Pull Request. The following is a unified diff of the changes.\n"
        "Your task is to:\n"
        "1. Identify potential bugs, logical errors, or anti-patterns.\n"
        "2. Check for violations of embedded C/C++ best practices (e.g., resource management, "
        "volatile correctness, interrupt safety if inferable).\n"
        "3. Look for areas where code could be optimized for performance or clarity.\n"
        "4. Provide constructive feedback and suggested improvements.\n"
        "5. If everything looks good, say so clearly.\n\n"
        "Here is the diff:\n"
        f"{diff_content}"
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"::error::AI review failed: {e}", file=sys.stderr)
        return "AI_REVIEW_FAILED"

if __name__ == "__main__":
    # First, try environment variables (GitHub Actions mode)
    gemini_api_key = os.getenv("GEMINI_API_KEY_SECRET")
    pr_diff_url = os.getenv("PR_DIFF_URL")
    github_token = os.getenv("GITHUB_TOKEN_SECRET")

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
        print(review_comment)

    else:
        # Local CLI mode: python ai_pr_reviewer.py <API_KEY> <diff_file>
        if len(sys.argv) != 3:
            print("Usage: python ai_pr_reviewer.py <API_KEY> <diff_file>", file=sys.stderr)
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
