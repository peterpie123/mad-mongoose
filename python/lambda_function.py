import json
import subprocess

def clone_repo(repo_url, destination, branch):
  """
  Clones a Git repository from the given URL to the specified destination 
  and checks out the provided branch.

  Args:
    repo_url: The URL of the Git repository to clone.
    destination: The local directory where the repository will be cloned.
    branch: The name of the branch to checkout after cloning.
  """
  subprocess.run(["git", "clone", repo_url, destination])
  subprocess.run(["git", "checkout", branch], cwd=destination)


def lambda_handler(event, _):
    """
    Entrypoint for the lambda function.

    Event params:
        repo_url (string)
        branch (string)
        pullrequest_id (int)
    """

    clone_repo(event['repo_url'], '/tmp/repo', event['branch'])

    with open("/tmp/repo/lib/math.py", "r") as f:
       return {
        'statusCode': 200,
        'body': json.dumps('File contents ' + f.read())
       }
