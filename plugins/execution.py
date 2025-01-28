from semantic_kernel.functions.kernel_function_decorator import kernel_function
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_agentchat.agents import CodeExecutorAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

class ExecutorPlugin:
    """A plugin for executing code within a container"""
    
    @kernel_function
    async def run_code_executor_agent(self, code: str, repo_name: str) -> str:
        """
        Executes the provided code in the given Repo. Can be used to run created pytest files.
        
        Args:
            code (str): The commands to run in the container
            repo_name (str): the name of the repository

        Returns:
            str: The result of the execution
        """
        docker_executor = DockerCommandLineCodeExecutor(work_dir=f"coding/{repo_name}", auto_remove=True)
        # Create a code executor agent that uses a Docker container to execute code.
        await docker_executor.start()
        code_executor_agent = CodeExecutorAgent("code_executor", code_executor=docker_executor)
        # Run the agent with a given code snippet.
        task = TextMessage(
            content=code,
            source="user",
        )
        print("DOCKER EXECUTION running...")
        response = await code_executor_agent.on_messages([task], CancellationToken())

        # Stop the code executor.
        await docker_executor.stop()
        print("DOCKER EXECUTION finished.")
        return response.chat_message.__str__
    
    # @kernel_function
    # async def write_file(self, repository_name: str, file_path: str, content: str) -> str:
    #     """
    #     Writes content to a file (overwrites existing content).

    #     Args:
    #         repository_name (str): The name of the repository.
    #         file_path (str): Path to the file.
    #         content (str): Content to write.

    #     Returns:
    #         str: Success message.
    #     """
    #     file_path = f"./coding/{repository_name}/{file_path}"
    #     try:
    #         with open(file_path, "w") as file:
    #             print(f"WRITE FILE {file_path}")
    #             file.write(content)
    #         return f"File {file_path} written successfully."
    #     except Exception as e:
    #         return f"An error occurred while writing to the file: {e}"