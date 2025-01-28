import httpx
from pydantic import BaseModel, Field
import subprocess
import requests
import os
import base64
from pathlib import Path
from semantic_kernel.functions.kernel_function_decorator import kernel_function

class Repo(BaseModel):
    id: int = Field(..., alias="id")
    name: str = Field(..., alias="full_name")
    description: str | None = Field(None, alias="description")
    url: str = Field(..., alias="html_url")


class User(BaseModel):
    id: int = Field(..., alias="id")
    login: str = Field(..., alias="login")
    name: str | None = Field(None, alias="name")
    company: str | None = Field(None, alias="company")
    url: str = Field(..., alias="html_url")


class Label(BaseModel):
    id: int = Field(..., alias="id")
    name: str = Field(..., alias="name")
    description: str | None = Field(None, alias="description")


class Issue(BaseModel):
    id: int = Field(..., alias="id")
    number: int = Field(..., alias="number")
    url: str = Field(..., alias="html_url")
    title: str = Field(..., alias="title")
    state: str = Field(..., alias="state")
    labels: list[Label] = Field(..., alias="labels")
    when_created: str | None = Field(None, alias="created_at")
    when_closed: str | None = Field(None, alias="closed_at")


class IssueDetail(Issue):
    body: str | None = Field(None, alias="body")


# endregion


class GitHubSettings(BaseModel):
    base_url: str = "https://api.github.com"
    token: str


class GitHubPlugin:
    def __init__(self, settings: GitHubSettings):
        self.settings = settings

    #@kernel_function
    async def get_user_profile(self) -> str:#"User":
        async with self.create_client() as client:
            response = await self.make_request(client, "/user")
            return User(**response).__str__

    #@kernel_function
    async def get_repository(self, organization: str, repo: str) -> str:#"Repo":
        async with self.create_client() as client:
            response = await self.make_request(client, f"/repos/{organization}/{repo}")
            return Repo(**response).__str__

    # @kernel_function
    # async def get_issues(
    #     self,
    #     organization: str,
    #     repo: str,
    #     max_results: int | None = None,
    #     state: str = "",
    #     label: str = "",
    #     assignee: str = "",
    # ) -> list["Issue"]:
    #     async with self.create_client() as client:
    #         path = f"/repos/{organization}/{repo}/issues?"
    #         path = self.build_query(path, "state", state)
    #         path = self.build_query(path, "assignee", assignee)
    #         path = self.build_query(path, "labels", label)
    #         path = self.build_query(path, "per_page", str(max_results) if max_results else "")
    #         response = await self.make_request(client, path)
    #         return [Issue(**issue) for issue in response]

    #@kernel_function
    async def get_issue_detail(self, organization: str, repo: str, issue_id: int) -> str:#"IssueDetail":
        async with self.create_client() as client:
            path = f"/repos/{organization}/{repo}/issues/{issue_id}"
            response = await self.make_request(client, path)
            return IssueDetail(**response).__str__

    def create_client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": "request",
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.settings.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return httpx.AsyncClient(base_url=self.settings.base_url, headers=headers)

    @staticmethod
    def build_query(path: str, key: str, value: str) -> str:
        if value:
            return f"{path}{key}={value}&"
        return path

    @staticmethod
    async def make_request(client: httpx.AsyncClient, path: str) -> dict:
        print(f"REQUEST: {path}\n")
        response = await client.get(path)
        response.raise_for_status()
        return response.json()
    
    @staticmethod
    async def list_repository_files(owner: str, repository: str, branch: str = "main") -> list:
        """
        Lists all files in a repository on the specified branch.
        
        Args:
            owner (str): GitHub-Owner (e.g. Username or Organisation).
            repository (str): name of the repository.
            branch (str): name of the branch
        Returns:
            list: List of all file paths.
        """
        token = os.getenv("GITHUB_TOKEN")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        url = f"https://api.github.com/repos/{owner}/{repository}/git/trees/{branch}?recursive=1"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            tree = response.json().get("tree", [])
            return [item["path"] for item in tree if item["type"] == "blob"]
        else:
            print(f"Error listing files: {response.status_code} - {response.text}")
            return []
    
    @staticmethod
    def find_relevant_files(files: list, keywords: list) -> list:
        """
        Filters a list of files for relevance based on keywords.
        """
        relevant_files = []
        for file_path in files:
            if any(keyword.lower() in file_path.lower() for keyword in keywords):
                relevant_files.append(file_path)
        return relevant_files

    @staticmethod
    async def fetch_code_from_github(owner: str, repository: str, file_path: str, branch: str = "main") -> str:
        """
        Fetches the content of a file from GitHub.
        """
        token = os.getenv("GITHUB_TOKEN")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        url = f"https://api.github.com/repos/{owner}/{repository}/contents/{file_path}?ref={branch}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            file_content: str = response.json().get("content", "")
            return base64.b64decode(file_content).decode("utf-8")  # Decode base64 file content
        else:
            return f"Error fetching file content: {response.status_code} - {response.text}"

    @kernel_function
    async def clone_repository(self, organization: str, repository_name: str) -> str:
        """
        Clones a Git-Repository based on Owner and repository_name.
        
        Args:
            organization (str): GitHub-Owner (e.g. Username or Organisation).
            repository_name (str): name of the repository.
        Returns:
            str: Path to Repository or Error.
        """
        try:
            # Erstelle die Repository-URL
            repo_url = f"https://github.com/{organization}/{repository_name}.git"
            
            # Zielverzeichnis erstellen, falls es nicht existiert
            destination_path = Path('./coding')
            destination_path.mkdir(parents=True, exist_ok=True)
            
            # Repository-Pfad erstellen
            repo_path = destination_path / repository_name

            # Überprüfen, ob das Repository bereits existiert
            if repo_path.exists():
                return f"Repository '{repository_name}' wurde bereits geklont in {repo_path}."

            # Git-Klon-Befehl ausführen
            subprocess.run(
                ["git", "clone", "--branch", "main", repo_url, str(repo_path)],
                check=True,
            )
            return f"Repository erfolgreich geklont: {repo_path}"
        except subprocess.CalledProcessError as e:
            return f"Fehler beim Klonen des Repositorys: {e}"
    
    @kernel_function
    def checkout_commit(self, repository: str, commit_hash: str):
        """
        Checks out on a specified commit within the repository
        
        Args:
            repository (str): name of the repository.
            commit_hash (str): The commit hash of the commit to check out to
        """
        try:
            destination_path = Path('./coding')
            destination_path.mkdir(parents=True, exist_ok=True)
            
            repo_path = destination_path / repository
            
            subprocess.run(["git", "-C", repo_path, "checkout", commit_hash], check=True)
            print(f"Successfully checked out to commit: {commit_hash}")
        except subprocess.CalledProcessError as e:
            print(f"Error during checkout: {e}")
            