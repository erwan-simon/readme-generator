import json
import uuid
from types import SimpleNamespace
import logging
import sys
from pathlib import Path
import click
import boto3
from datetime import datetime
from strands import Agent, tool
from strands.types.tools import ToolContext
from strands.session.file_session_manager import FileSessionManager
from strands.handlers.callback_handler import PrintingCallbackHandler
from strands_tools import file_read, file_write, use_llm


def check_root_path(root_path: str, operation_path: str):
    root_path_object = Path(root_path)
    operation_path_object = Path(operation_path)
    if not operation_path_object.resolve().is_relative_to(root_path_object.resolve()):
        error_message = "Agent is not authorized to access files outside root path. " + \
                        f"Path {operation_path} is outside given root path {root_path}"
        logging.getLogger().error(error_message)
        raise ValueError(error_message)

@tool(context=True)
def summarize_file(agent, file_path: str, additional_context: str) -> str:
    """
    Reads the content of a file and returns a summary made by an LLM call.

    Args:
        file_path (str): Path to the file to read.
        additional_context (str): Additional context to send to the LLM when summarizing the file content (usefull if you want to guide the LLM to what you are looking for or if the file needs some context to be understood).

    Returns:
        dict: Summary of the read file with following keys ("file", "category", "language_or_format", "purpose", "public_interfaces", "external_dependencies", "execution_or_config_notes", "limitations")
    """
    check_root_path(agent.state.get("root_path"), file_path)
    path = Path(file_path)
    if not path.is_file():
        error_message = f"The file '{file_path}' does not exist or is not a file."
        logging.getLogger().error(error_message)
        raise FileNotFoundError(error_message)
    print(f"Reading file {file_path}")
    file_content = path.read_text(encoding="utf-8")
    max_chars = 200_000
    truncated = False
    if len(file_content) >= max_chars:
        logging.getLogger().error(f"File {file_path} is bigger than max chars, which is {max_chars}, truncating...")
        file_content = file_content[:max_chars]
        truncated = True
    user_message = f"""
File path: {file_path}

File content:
{file_content}

Additional Context:
{additional_context}

{"NOTE: File content was truncated." if truncated else ""}
"""
    current_program_path = Path(__file__).resolve().parent
    system_prompt_file_path = current_program_path / "subagent_system_prompt.txt"
    summarizing_agent = Agent(
        model=agent.state.get("inference_profile_arn"),
        system_prompt=system_prompt_file_path.read_text(encoding="utf-8"))
    result = summarizing_agent(user_message)
    try:
        print(result.message["content"][0]["text"])
        return json.loads(result.message["content"][0]["text"])
    except json.JSONDecodeError as e:
        error_message = f"Invalid JSON returned for file {file_path}"
        logging.getLogger().error(error_message)
        raise RuntimeError(error_message) from e


@tool(context=True)
def write_readme_file(agent, readme_content: str) -> None:
    """
    Write a string in a README.md file at the root of the project.

    Args:
        readme_content (str): Content of the file

    Returns:
        None
    """
    file_path = Path(agent.state.get("root_path")) / "README.md"
    print("Writing REAMDME.md file")
    file_path.write_text(readme_content, encoding="utf-8")


@tool(context=True)
def get_tree(agent, start_path: str, recursive_ceiling: int = 5) -> dict:
    """
    Builds a nested dictionary representing the directory tree starting
    from the given directory path. Each directory is represented as a
    dictionary with its name, type, and children. Each file is represented
    as a dictionary with its name and type.

    Args:
        directory (Path): Path object pointing to the root directory to scan.

    Returns:
        dict: A nested dictionary representing the directory tree structure recursively.
        int: recursive ceiling left. If 0, it means that the recursive search was limited and will need further search if we want the exhaustie result
    """
    check_root_path(agent.state.get("root_path"), start_path)
    directory = Path(start_path)
    tree = {"name": directory.name, "type": "directory", "children": []}
    for entry in sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
        if entry.is_dir() and recursive_ceiling > 0:
            tree["children"].append(get_tree(agent, entry, recursive_ceiling - 1))
        else:
            tree["children"].append({"name": entry.name, "type": "file"})
    return tree, recursive_ceiling


def get_inference_profile_arn(logger, boto_session, inference_profile_name: str) -> str:
    inference_profile_list = boto_session.client("bedrock").list_inference_profiles(
        typeEquals="APPLICATION")
    inference_profile_arn = None
    available_models_list = []
    for profile in inference_profile_list['inferenceProfileSummaries']:
        if profile['inferenceProfileName'] == inference_profile_name:
            available_models_list.append(profile['inferenceProfileName'])
            if profile['inferenceProfileName'] == inference_profile_name:
                inference_profile_arn = profile['inferenceProfileArn']
    if not inference_profile_arn:
        error_message = f"Did not find any inference profile with name {inference_profile_name}."
        logger.error(error_message)
        raise ValueError(error_message)
    print(f"Using {inference_profile_arn} as Bedrock inference profile")
    return inference_profile_arn


def main(logger, boto_session, project_name: str, domain_name: str, print_sub_agent_debug: bool, root_path: str, chat_mode: bool):
    inference_profile_prefix = f"{project_name}_{domain_name}"
    inference_profile_arn = get_inference_profile_arn(
        logger, boto_session, inference_profile_prefix)
    main_session_manager = FileSessionManager(
        session_id=str(uuid.uuid1())
    )
    current_program_path = Path(__file__).resolve().parent
    system_prompt_file_path = current_program_path / "system_prompt.txt"
    readme_example_file_path = current_program_path / "readme_example.md"
    agent = Agent(
        model=inference_profile_arn,
        system_prompt=system_prompt_file_path.read_text(encoding="utf-8") + "\n Use this md file as template: \n" + readme_example_file_path.read_text(encoding="utf-8"),
        session_manager=main_session_manager,
        callback_handler=None,
        tools=[get_tree, write_readme_file, file_read])
    agent.state.set("inference_profile_arn", inference_profile_arn)
    agent.state.set("project_name", project_name)
    agent.state.set("root_path", root_path)
    print("Working...")
    user_prompt = f"Generate the readme file content and write the file for the program with root path '{root_path}'"
    agent_response = agent(user_prompt)
    print("Generated the README.md file.")
    print(agent_response.message["content"][0]["text"])
    if chat_mode:
        while True:
            print("\n\nYou can ask the model for modification or type "
                  "'exit' if you are satisfied with the result.")
            try:
                user_prompt = input("\n>>> ")
            except Exception as error:
                logger.error(f"There was an error in your prompt: {error}")
                continue
            if user_prompt == "exit":
                break
            print("Working...")
            agent_response = agent(
                "The user had something to say with the README.md "
                "you wrote at the root path, so rework it while taking "
                f"the following feedback into account: {user_prompt}")
            print("Generated the corrected README.md file.")
            print(agent_response.message["content"][0]["text"])

@click.command("readme_generator")
@click.pass_context
@click.option(
    "-p", '--project-name', required=True,
    help="Project name")
@click.option(
    "-r", "--root-path", required=False,
    help="Path of the root of the project to document")
@click.option("-c", '--chat-mode', required=False, default=False, is_flag=True, help="Mode allowing to discuss with the program to perfect the produced readme file")
def command_line_main(
        ctx, project_name: str, root_path: str = None, chat_mode: bool = False) -> int:
    domain_name = "readme_generator"
    if root_path:
        # change relative path to absolute path
        root_path = str(Path(root_path).resolve())
    else:
        root_path = str(Path.cwd())
    ctx.obj = SimpleNamespace(
        logger=logging.getLogger(),
        boto_session=boto3.session.Session(),
        project_name=project_name,
        domain_name=domain_name)
    logging.getLogger()
    logging.basicConfig(
        format="%(message)s",
    )
    main(ctx.obj.logger, ctx.obj.boto_session, project_name, domain_name, True, root_path, chat_mode)

if __name__ == "__main__":
    sys.exit(command_line_main())
