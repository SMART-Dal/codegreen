import git
import os

def get_repo_metadata(repo_dir):
  metadata = {}
  
  try:

    repo = git.Repo(repo_dir)

    # Project name
    metadata["project_name"] = os.path.basename(repo_dir)

    # Project repository 
    metadata["project_repository"] = repo.remote().url

    # Project owner
    metadata["project_owner"] = repo.remote().url.split("/")[-2]

    # Project branch
    metadata["project_branch"] = repo.active_branch.name

    # Project commit
    metadata["project_commit"] = repo.head.commit.hexsha

    # Project commit date
    metadata["project_commit_date"] = repo.head.commit.committed_datetime.isoformat()

    # Script path - would need to pass this explicitly
    metadata["script_path"] = None

    # API call line - would need to parse files to get this
    metadata["api_call_line"] = None

  except git.InvalidGitRepositoryError:
    print(f"{repo_dir} is not a Git repository, so git metadata cannot be retrieved.")

  return metadata

def get_script_path(script_name, method_level_python_scripts):
    for script_path in method_level_python_scripts:
        if script_name in script_path:
            return script_path
    return None