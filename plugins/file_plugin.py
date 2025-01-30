from semantic_kernel.functions.kernel_function_decorator import kernel_function
from typing import Annotated
import os
class FilePlugin:
    """A plugin for manipulating files"""

    def __init__(self):
        pass
    
    @kernel_function(name="write_file",
                    description="Writes the provided content string to the specified file path within the repository wth repository_name (overwrites existing content).")
    def write_file(self, 
                   repository_name: Annotated[str, "The name of the repository"], 
                   file_path: Annotated[str, "Path to the file."], 
                   content: Annotated[str, "content to write to the file"]
                ) -> Annotated[str, "Success/Error Message"]:
        file_path = f"./coding/{repository_name}/{file_path}"
        try:
            with open(file_path, "w") as file:
                print(f"WRITE FILE {file_path}")
                file.write(content)
            return f"File {file_path} written successfully."
        except Exception as e:
            return f"An error occurred while writing to the file: {e}"

    @kernel_function
    def list_files_in_repository(self, repo: str) -> list[str]:
        """
        Lists all files in a given repository directory recursively.

        Returns:
            list: A list of file paths relative to the repository root, or an error message.
        """
        repo_path = f"./coding/{repo}"
        try:
            if not os.path.exists(repo_path):
                return [f"Error: Repository path '{repo_path}' does not exist."]
            
            file_list = []
            for root, _, files in os.walk(repo_path):
                for file in files:
                    # Construct the relative file path
                    relative_path = os.path.relpath(os.path.join(root, file), repo_path)
                    file_list.append(relative_path)
            
            return file_list
        except Exception as e:
            return [f"Error: An error occurred while listing files: {e}"]
        
    @kernel_function(name="read_file",
                    description="Read a file within the repository using file_path and repository_name")
    def read_file(self, file_path: str, repo: str) -> str:
        """
        Reads the content of a file and returns it as a string.

        Args:
            file_path (str): Path to the file to be read.
            repo (str): Name of the Repository.

        Returns:
            str: Content of the file or an error message.
        """
        file_path = f"./coding/{repo}/{file_path}"
        try:
            with open(file_path, "r") as file:
                print(f"READ FILE {file_path}")
                return file.read()
        except FileNotFoundError:
            return f"Error: File '{file_path}' not found."
        except Exception as e:
            return f"Error: An error occurred while reading the file: {e}"