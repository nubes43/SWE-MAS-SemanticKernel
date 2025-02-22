import asyncio
import os
import agentops
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, AgentGroupChat
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import (
    KernelFunctionSelectionStrategy,
)
from semantic_kernel.agents.strategies.termination.kernel_function_termination_strategy import (
    KernelFunctionTerminationStrategy,
)
from semantic_kernel.functions.kernel_function_from_prompt import KernelFunctionFromPrompt
from dotenv import load_dotenv
from sk_prompts import *
from plugins.github import GitHubPlugin, GitHubSettings
from plugins.file_plugin import FilePlugin
from plugins.execution import ExecutorPlugin
import pyarrow.parquet as pq
import random
import re


agentops.init(api_key="<AGENTOPS PROJECT KEY>")
load_dotenv()

def create_kernel_with_chat_completion(service_id: str, model = "gpt-4o-mini") -> Kernel:
    """Creates a new Kernel with Chat Completion Method"""
    kernel = Kernel()
    kernel.add_service(
        OpenAIChatCompletion(
            service_id=service_id,
            ai_model_id=model,
            api_key=os.environ["OPENAI_API_KEY"]
            )
    )
    return kernel

async def main():
    """Main"""

    issue_analyzer_id = "issue_analyzer"
    issue_analyzer_kernel = create_kernel_with_chat_completion(issue_analyzer_id)
    analyzer_settings = issue_analyzer_kernel.get_prompt_execution_settings_from_service_id(service_id=issue_analyzer_id)
    analyzer_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    issue_analyzer_kernel.add_plugin(
        GitHubPlugin(settings=GitHubSettings(token=os.environ["GITHUB_TOKEN"])),
        plugin_name="GitHubPlugin",
    )

    issue_analyzer_agent = ChatCompletionAgent(
        service_id=issue_analyzer_id,
        kernel=issue_analyzer_kernel,
        name=ANALYZER_NAME,
        instructions=GITHUB_PROMPT,
        execution_settings=analyzer_settings,
        agentops_name="IssueAnalyzer",
    )

    coder_id = "coder"
    coder_kernel = create_kernel_with_chat_completion(coder_id)
    coder_settings = coder_kernel.get_prompt_execution_settings_from_service_id(service_id=coder_id)
    coder_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    coder_agent = ChatCompletionAgent(
        service_id=coder_id,
        kernel=coder_kernel,
        name=CODER_NAME,
        instructions=PROMPT_CODE_GEN,
        execution_settings=coder_settings,
        agentops_name="Programmer",
    )

    file_id = "file"
    file_kernel = create_kernel_with_chat_completion(file_id)

    file_kernel.add_plugin(FilePlugin(), plugin_name="FilePlugin")
    file_settings = file_kernel.get_prompt_execution_settings_from_service_id(service_id=file_id)
    file_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    file_agent = ChatCompletionAgent(
        service_id=file_id,
        kernel=file_kernel,
        name=FILE_MANI_NAME,
        instructions=PROMPT_FILE_MANIPULATOR,
        execution_settings=file_settings,
        agentops_name="FileManager",
    )

    tester_id = "tester"
    tester_kernel = create_kernel_with_chat_completion(tester_id)
    tester_kernel.add_plugin(ExecutorPlugin(), plugin_name="ExecutorPlugin")
    tester_kernel.add_plugin(FilePlugin(), plugin_name="FilePlugin")

    tester_settings = tester_kernel.get_prompt_execution_settings_from_service_id(service_id=tester_id)
    tester_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    tester_agent = ChatCompletionAgent(
        service_id=tester_id,
        kernel=tester_kernel,
        name=TESTER_NAME,
        instructions=CODE_PREP,
        execution_settings=tester_settings,
        agentops_name="Tester",
    )

    selection_function = KernelFunctionFromPrompt(
        function_name="selection",
        prompt=SELECTION_PROMPT,
    )

    termination_function = KernelFunctionFromPrompt(
        function_name="termination",
        prompt=TERMINATION_PROMPT,
    )

    selection_kernel = create_kernel_with_chat_completion("selection")
    termination_kernel = create_kernel_with_chat_completion("termination")

    group_chat = AgentGroupChat(
        agents=[issue_analyzer_agent, coder_agent, file_agent, tester_agent],
        selection_strategy=KernelFunctionSelectionStrategy(
            function=selection_function,
            kernel=selection_kernel,
            result_parser=lambda result: str(result.value[0]) if result.value is not None else CODER_NAME,
            agent_variable_name="agents",
            history_variable_name="history",
        ),
        termination_strategy=KernelFunctionTerminationStrategy(
            agents=[tester_agent],
            function=termination_function,
            kernel=termination_kernel,
            result_parser=lambda result: TERMINATION_KEYWORD in str(result.value[0]).lower(),
            history_variable_name="history",
            maximum_iterations=10,
        ),
    )


    table = pq.read_table('.\\swebench\\test-00000-of-00001.parquet')

    data_dict = table.to_pydict()
    columns = data_dict.keys()
    rows = [{col: data_dict[col][i] for col in columns} for i in range(len(next(iter(data_dict.values()))))]

    random.seed(30)
    random.shuffle(rows)
    log = open('./swebench/log.txt', "a")

    for row in rows[21:30]:
        repo = row["repo"]
        print(repo)
        issue = int(re.search(r'\d+', row["instance_id"]).group())
        print(issue)
        commit = row["base_commit"]
        issue_detail = row["problem_statement"]
        print(commit)
        try:
            await group_chat.add_chat_message(ChatMessageContent(role=AuthorRole.USER, content=f"{repo}/{issue} with base commit {commit} ISSUE Description: {issue_detail}"))

            async for response in group_chat.invoke():
                print(f"# {response.role} - {response.name or '*'}: '{response.content}'")
                log.write(f"# {response.role} - {response.name or '*'}: '{response.content}'")
                    
                
        except Exception as e:
            with open('./swebench/failures.txt', "a") as f:
                f.write(str(e))
                f.close()
                agentops.end_session('Failure')
    
        agentops.end_session('Success')
        
    log.close()
        


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
