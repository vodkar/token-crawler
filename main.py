import math
import re
from typing import Any, Counter, Dict, List

import openai
import requests
from ratelimit import limits, sleep_and_retry


def shannon(string_to_check: str) -> float:
    counts = Counter(string_to_check)
    frequencies = ((i / len(string_to_check)) for i in counts.values())
    return float(-sum(f * math.log(f, 2) for f in frequencies))


def check_openai_api_key(api_key: str):
    client = openai.OpenAI(api_key=api_key)
    try:
        client.models.list()
    except openai.AuthenticationError:
        return False
    else:
        return True


# Mock validator library
class Validator:
    @staticmethod
    def validate(data: str) -> str | None:
        if match := re.search(r"(sk-[\w-]{40,})", data):
            key = match.group(1)
            with open("not_valid.txt") as f:
                if key in f.read():
                    return None
            if shannon(key) > 4.5:
                if check_openai_api_key(key):
                    return key
            with open("not_valid.txt", "a") as f:
                f.write(f"{key}\n")
        return None


@sleep_and_retry
@limits(calls=1, period=5)
def search_github(
    query: str, token: str, page: int = 1, per_page: int = 50
) -> List[Dict[str, Any]]:
    """
    Search GitHub public repositories for a query string.

    Args:
        query (str): The string to search for.
        token (str): GitHub personal access token for authentication.
        page (int): The current page for paginated results.
        per_page (int): The number of results per page.

    Returns:
        List[Dict[str, Any]]: List of repository metadata from GitHub.
    """
    url = "https://api.github.com/search/code"
    headers = {"Authorization": f"token {token}"}
    params = {"q": query, "page": page, "per_page": per_page}
    response = requests.get(url, headers=headers, params=params)  # type: ignore
    response.raise_for_status()
    return response.json().get("items", [])


def search_gitlab(
    query: str, token: str, page: int = 1, per_page: int = 10
) -> List[Dict[str, Any]]:
    """
    Search GitLab public repositories for a query string.

    Args:
        query (str): The string to search for.
        token (str): GitLab personal access token for authentication.
        page (int): The current page for paginated results.
        per_page (int): The number of results per page.

    Returns:
        List[Dict[str, Any]]: List of repository metadata from GitLab.
    """
    url = "https://gitlab.com/api/v4/projects"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"search": query, "page": page, "per_page": per_page}
    response = requests.get(url, headers=headers, params=params)  # type: ignore
    response.raise_for_status()
    return response.json()


@sleep_and_retry
@limits(calls=1, period=2)
def get_code(url: str) -> str:
    file_url = url.replace("/blob/", "/").replace(
        "https://github.com", "https://raw.githubusercontent.com"
    )
    file_response = requests.get(file_url)
    file_response.raise_for_status()
    return file_response.text


def validate_and_search(query: str, github_token: str, gitlab_token: str) -> None:
    """
    Search GitHub and GitLab repositories and validate results until a successful validation.

    Args:
        query (str): The string to search for.
        github_token (str): GitHub personal access token.
        gitlab_token (str): GitLab personal access token.
    """
    validator = Validator()
    page = 1
    per_page = 50

    with open("checked_hashes.txt") as f:
        checked_hashes = set(f.read().split("\n"))

    while True:
        # Search GitHub
        print(f"Searching GitHub (Page {page})...")
        github_results = search_github(
            f"{query} language:Python", github_token, page, per_page
        )
        for result in github_results:
            if result["sha"] in checked_hashes:
                continue

            file_content = get_code(result["html_url"])
            if validator.validate(file_content):
                print(f"Validated successfully: {file_content}")
                return
            else:
                with open("checked_hashes.txt", "a") as f:
                    f.write(f"{result['sha']}\n")

        # Search GitLab
        # print(f"Searching GitLab (Page {page})...")
        # gitlab_results = search_gitlab(query, gitlab_token, page, per_page)
        # for result in gitlab_results:
        #     repo_name = result.get("name", "Unknown")
        #     repo_description = result.get("description", "")
        #     repo_url = result.get("web_url")

        #     data_to_validate = f"GitLab Repo: {repo_name} - {repo_description}"
        #     if validator.validate(data_to_validate):
        #         print(f"Validated successfully: {data_to_validate} ({repo_url})")
        #         return

        # Increment page for pagination
        page += 1

        # Exit if no more results are found
        # if not github_results and not gitlab_results:
        #     print("No more results found. Validation unsuccessful.")
        #     break


if __name__ == "__main__":
    # Replace these with your actual GitHub and GitLab tokens
    GITHUB_TOKEN = ""
    GITLAB_TOKEN = ""

    # Query string to search for
    QUERY_STRING = "sk-proj"

    # Run the script
    validate_and_search(QUERY_STRING, GITHUB_TOKEN, GITLAB_TOKEN)
