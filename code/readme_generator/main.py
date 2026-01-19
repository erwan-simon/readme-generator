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
from strands.models import BedrockModel
from strands.types.tools import ToolContext
from strands.session.file_session_manager import FileSessionManager
from strands.handlers.callback_handler import PrintingCallbackHandler
from strands_tools import file_read
from botocore.config import Config as BotocoreConfig
from git import Repo

def check_root_path(root_path: str, operation_path: str):
    root_path_object = Path(root_path)
    operation_path_object = Path(operation_path)
    if not operation_path_object.resolve().is_relative_to(root_path_object.resolve()):
        error_message = "Agent is not authorized to access files outside root path. " + \
                        f"Path {operation_path} is outside given root path {root_path}"
        logging.getLogger().error(error_message)
        raise ValueError(error_message)


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
        aws_region = boto_session.region_name
        account_id = boto_session.client("sts").get_caller_identity()["Account"]
        default_inference_profile_arn = f"arn:aws:bedrock:{aws_region}:{account_id}:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0"
        logger.error(f"Did not find any inference profile with name {inference_profile_name}, using default one: {default_inference_profile_arn}")
        return default_inference_profile_arn
    print(f"Using {inference_profile_arn} as Bedrock inference profile")
    return inference_profile_arn


def get_git_diff_since_readme_update(root_path: str) -> list:
    """
    Allow to tell to the LLM which files changed since the README was modified
    """
    try:
        repo = Repo(root_path)
    except git.exc.InvalidGitRepositoryError:
        return "This project is not a git repo."
    commits = repo.iter_commits(
        paths=str(Path(root_path) / "README.md"), max_count=1)
    commit = next(commits, None)
    commit_hash_of_last_readme_update = commit.hexsha if commit else None
    if not commit_hash_of_last_readme_update:
        return "No git history was found."
    if repo.commit().hexsha == commit_hash_of_last_readme_update:
        return "The README seems updated with the git history."
    return [
        f"--- a/{diff_item.a_blob.name}\n+++ b/{diff_item.b_blob.name}\n" + \
        f"{diff_item.diff.decode('utf-8')}\n\n"
        for diff_item in repo.commit(
            commit_hash_of_last_readme_update
        ).diff(repo.commit("HEAD"), create_patch=True)
    ]


def main(logger,
         boto_session,
         project_name: str,
         domain_name: str,
         print_sub_agent_debug: bool,
         root_path: str,
         chat_mode: bool,
         additional_context_file_path: str,
         additional_context_string: str):
    inference_profile_prefix = f"{project_name}_{domain_name}"
    inference_profile_arn = get_inference_profile_arn(
        logger, boto_session, inference_profile_prefix)
    main_session_manager = FileSessionManager(
        session_id=str(uuid.uuid1())
    )
    current_program_path = Path(__file__).resolve().parent
    system_prompt_file_path = current_program_path / "system_prompt.txt"
    readme_example_file_path = current_program_path / "readme_example.md"
    system_prompt = "SYSTEM PROMPT\n" + system_prompt_file_path.read_text(encoding="utf-8") + \
        "\nUse this md file as template: \n" + \
        readme_example_file_path.read_text(encoding="utf-8")
    if additional_context_file_path:
        system_prompt += "\nORGANIZATIONAL CONTEXT:" + \
            Path(additional_context_file_path).resolve().read_text(encoding="utf-8")
    if additional_context_string:
        system_prompt += "\nFinally, the user gave you this sentence as additional context:" + \
            additional_context_string
    changes_list = get_git_diff_since_readme_update(root_path)
    system_prompt += "\n\nHere is the diff list:\n" + \
        str(changes_list)
    agent = Agent(
        model=BedrockModel(
            model_id=inference_profile_arn,
            boto_session=boto_session,
            boto_client_config=BotocoreConfig(
                read_timeout=180,  # seconds
            )
        ),
        system_prompt=system_prompt,
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
@click.option(
    "--additional-context-file-path", required=False,
    help="Path of a file providing additional context to give to the model")
@click.option(
    "--additional-context-string", required=False,
    help="String providing additional context to give to the model")
def command_line_main(
        ctx,
        project_name: str,
        root_path: str = None,
        chat_mode: bool = False,
        additional_context_file_path: str = None,
        additional_context_string: str = None) -> int:
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
    main(
        ctx.obj.logger,
        ctx.obj.boto_session,
        project_name,
        domain_name,
        True,
        root_path,
        chat_mode,
        additional_context_file_path,
        additional_context_string)

if __name__ == "__main__":
    sys.exit(command_line_main())
