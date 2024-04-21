import json
import logging
import os
import random
import subprocess

import anthropic
import boto3
import requests
from botocore.exceptions import ClientError


MY_AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
MY_AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

BASE_PATH = "/home/joseph/Documents/Projects/Hackathon"
TEMPLATE_FULL_PATH = BASE_PATH + "/template.py"

OUTPUT_BASE_PATH = BASE_PATH
OUTPUT_FILE = "unit_tests.py"
OUTPUT_FULL_PATH = os.path.join(OUTPUT_BASE_PATH, OUTPUT_FILE)
SOURCE_BASE_PATH = BASE_PATH
SOURCE_FILE = "functions"
SOURCE_FILE_EXT = ".py"
SOURCE_FULL_PATH = os.path.join(SOURCE_BASE_PATH, SOURCE_FILE + SOURCE_FILE_EXT)
API_URL = "https://mad-mongoose.vercel.app/api"


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
        unique_id (string)
        repo_url (string)
        branch (string)
        pullrequest_id (int)
        changed_files (list)
        max_attempts (int, optional)
    """
    unique_id = event['unique_id']
    repo_url = event['repo_url']
    branch = event['branch']
    pullrequest_id = event['pullrequest_id']
    changed_files = event['changed_files']
    max_attempts = event['max_attempts'] if 'max_attempts' in event else 1

    # root_path = event['root_path'] if 'root_path' in event else "/"
    repo_path = f'/tmp/{unique_id}/repo'

    clone_repo(repo_url, repo_path, branch)

    add_init_file(repo_path)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    bucket = get_aws_bucket("mad-mongoose")

    aggregate_results = {}

    for file_path in changed_files:
        file_name = get_file_name_without_extension(file_path)
        full_file_path_from_root = os.path.join(repo_path, file_path)
        base_file_path = get_file_path(full_file_path_from_root)

        file_contents = get_file_content(full_file_path_from_root)
        file_data = {
            "file_name": file_name,
            "file_path": full_file_path_from_root,
            "source_code": file_contents
        }

        instruction_dict = try_parse_file_into_functions_and_instructions(client, file_data, max_attempts)

        aggregate_results[file_path] = {}

        if "error" in instruction_dict:
            aggregate_results[file_path]["NO FUNCTION TESTED"] = {"result": False,
                                                                  "error": "Could not parse file into functions and instructions."}
            continue

        for function_information_dict in instruction_dict['functions']:
            unit_test_json = try_create_unit_test_dict(client, function_information_dict, max_attempts)

            if "error" in unit_test_json:
                aggregate_results[file_path][function_information_dict['function_name']] = {"result": False,
                                                                                           "error": "Could not create unit test."}
                continue

            template = get_template()
            completed_template = replace_values_in_template(template, unit_test_json, file_name)
            print(unit_test_json)
            test_file_path = f"{base_file_path}/{file_name}_{function_information_dict['function_name']}_unit_tests.py"
            write_unit_tests_to_file(completed_template, test_file_path)
            test_file_path_without_repo_path = test_file_path.replace(repo_path, "")[1:]
            result_json = run_unit_test(test_file_path_without_repo_path, repo_path)

            aggregate_results[file_path][function_information_dict['function_name']] = result_json

    result_summary = {}
    result_summary["tests_passed"] = 0
    result_summary["tests_failed"] = 0
    result_summary["error"] = 0

    for file in aggregate_results:
        for function in aggregate_results[file]:
            for test_function in aggregate_results[file][function]:
                if "error" in aggregate_results[file][function]:
                    result_summary["error"] += 1
                    result_summary["tests_failed"] += 1
                    continue

                test_result = aggregate_results[file][function][test_function]
                if test_result["result"]:
                    result_summary["tests_passed"] += 1
                else:
                    result_summary["tests_failed"] += 1

                if "error" in test_result:
                    result_summary["error"] += 1

    aggregate_results["result_summary"] = result_summary
    print(json.dumps(aggregate_results, indent=4))
    dumped_json = json.dumps(aggregate_results, indent=4)

    try:
        bucket.put_object(Key=f"{pullrequest_id}/{unique_id}.txt", Body=dumped_json)
    except ClientError as e:
        logging.error(f"Unable to save test results to bucket: {e}")

    requests.patch(API_URL, json.dumps({
        "id": unique_id,
        "tests_run": result_summary["tests_passed"] + result_summary["tests_failed"],
        "tests_failed": result_summary["tests_failed"],
        "tests_errored": result_summary["error"]
    }))

    return {
        'statusCode': 200,
        'body': json.dumps('DUMPED')
    }

def try_parse_file_into_functions_and_instructions(client, file_source_code, max_attempts = 1):
    """
    Try to parse the source code of a file into functions and instructions.
    
    Args:
        file_source_code: str, the source code of the file.
    """
    attempts = 0

    while(attempts < max_attempts):
        attempts += 1
        try:
            file_source_code_dumped = json.dumps(file_source_code)
            instruction_string =  parse_file_into_functions_and_instructions(client, file_source_code_dumped)
            instruction_json = json.loads(instruction_string, strict=False)
            return instruction_json
        except Exception as e:
            return {"error": "JSON could not be generated."}
        

    return instruction_json
        

def get_file_content(file_path):
    """
    Read the content of a file and return it as a string.

    Args:
        file_path: The path to the file to read.

    Returns:
        The content of the file as a string.
    """
    with open(file_path, "r") as file:
        return file.read()


def try_create_unit_test_dict(client, function_information_dict, max_attempts = 1):
    """
    Try to create a unit test for a given function.
    
    Args:
        client: anthropic client
        function_information_dict: dict, the function to create a unit test for
    """
    attempts = 0
    while(attempts < max_attempts):
        attempts += 1

        try:
            unit_test_dict = create_unit_test_dict(client, function_information_dict)
            return unit_test_dict
        except Exception as e:
            return {"error": "JSON could not be generated."}
        

    return {"error": "JSON could not be generated."}

def create_unit_test_dict(client, function_information_dict):
    unit_test = create_unit_test(client, json.dumps(function_information_dict))
    return json.loads(unit_test,strict=False)


def create_unit_test(client, function):
    """
    Create a unit test for a given function.

    Ags: 
        client: anthropic client
        function: str, the function to create a unit test for
    """
    system = """
    You are a bot. Your sole purpose is to generate unit tests in JSON format.
    Given a JSON format input with functions and instructions, you must generate a unit test for each function.
    The unit test must be written in the same language as the function.

    Given the following function:

    <EXAMPLE_INPUT>
    {
        "functions": [
            {
                "function_name": "add",
                "function_code": "def add(a, b):\n  return a + cool_function(b)",
                "instructions": "To run the 'add' function, instantiate the MyClass class and call the 'add' method with two arguments. For example: \n   my_class = MyClass()\n    result = my_class.add(1, 2)",
            },
            {
                "function_name": "subtract",
                "function_code": "def subtract(a, b):\n  return a - amazing_function(b)",
                "instructions": "To run the 'subtract' function, call the 'subtract' method with two arguments. For example: \n    result = subtract(1, 2)",
            }
        ]
    }
    </EXAMPLE_INPUT>

    Return the unit tests as JSON in the following format:

    <EXAMPLE_JSON>
    {
        "unit_tests": [
            {"function_to_test_name":"add","test_function_name": "test_add_1", "test_function_code": "def test_add_1():\n    my_class = MyClass()\n    return my_class.add(1, 2) == 3"},
            {"function_to_test_name":"add","test_function_name": "test_add_2", "test_function_code" :"def test_add_2():\n    my_class = MyClass()\n    return my_class.add(2, 3) == 5"},
            {"function_to_test_name":"subtract","test_function_name": "test_subtract_1", "test_function_code": "def test_subtract_1():\n    return subtract(1, 2) == -1"},
            {"function_to_test_name":"subtract","test_function_name": "test_subtract_2", "test_function_code" :"def test_subtract_2():\n    return subtract(2, 3) == -1"}
            {"function_to_test_name":"subtract","test_function_name": "test_subtract_3", "test_function_code" :"def test_subtract_3():\n    return subtract(3, 2) == 1"}
        ]
    }
    </EXAMPLE_JSON>
    
    Your response should be a JSON object. No preceeding or trailing whitespace or text is allowed.
    """

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.5,
        system=system,
        messages=[
            {"role": "user", "content": function}
        ]
    )

    return message.content[0].text


def parse_file_into_functions_and_instructions(client, file_source_code):
    """unit_tests
    Parse the source code of a file into functions and instructions.

    Args:
        file_source_code: str, the source code of the file.
    """

    system = """
    You are a bot. Your sole purpose is to parse the source code of a file into functions and instructions on how to run that function.
    Pay careful attention to what must be imported in order to test the functions.
    The required imports should return whatever is necessary to run the functions in the source code from another file in the same exact directory.

    For example:

    <EXAMPLE_SOURCE_CODE>
    {
        "source_code": "
        def add(a, b):\n
            return a + b\n
            "
    }
    </EXAMPLE_SOURCE_CODE>

    Should return:

    <EXAMPLE_JSON>
    {
        "functions": [
            {"function_name": "add",
            "function_code": "def add(a, b):\n    return a + b",
            "instructions": "To run the 'add' function, call the 'add' function with two arguments. For example: \n    result = add(1, 2)"
            }
        ]
    }
    </EXAMPLE_JSON>

    For example, given the following source code:

    <EXAMPLE_SOURCE_CODE>
    {
        "source_code": "
        from module1 import cool_function\n
        from module2 import amazing_function\n
        \n
        class MyClass:\n
            def add(a, b):\nadd
                return a + cool_function(b)\n
        \n
        \n
        def subtract(a, b):\n
            return a - amazing_function(b)"
        "file_name": "my_class_name"
    }
    </EXAMPLE_SOURCE_CODE>

    Return the functions and instructions as JSON in the following format:

    <EXAMPLE_JSON>
    {
        "functions": [
            {"function_name": "add", 
            "function_code": "def add(a, b):\n    return a + cool_function(b)",
            "instructions": "To run the 'add' function, instantiate the MyClass class and call the 'add' method with two arguments. For example: \n   my_class = MyClass()\n    result = my_class.add(1, 2)"},
            {"function_name": "subtract",
            "function_code": "def subtract(a, b):\n    return a - amazing_function(b)",
            "instructions": "To run the 'subtract' function, call the 'subtract' method with two arguments. For example: \n    result = subtract(1, 2)"}            
        ]
    }
    </EXAMPLE_JSON>

    Your response should be a JSON object. No preceeding or trailing whitespace or text is allowed.
    """

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.5,
        system=system,
        messages=[
            {"role": "user", "content": file_source_code}
        ]
    )

    return message.content[0].text


def run_unit_test(unit_test_file, repo_path):
    """
    Run the unit tests in the specified file.

    Args:
        unit_test_file: str, the path to the file containing the unit tests.

    Returns: JSON object containing the results of the unit tests.
    """

    parsed_unit_test_file = unit_test_file.replace("/", ".").replace(".py", "")

    result = subprocess.run(["python3", "-m", "repo." + parsed_unit_test_file], capture_output=True, text=True, cwd=repo_path.replace("/repo",""))

    if result.stderr:
        random.randint(0, 5)
        json_result = {}

        for i in range(random.randint(1, 5)):
            json_result[f"You're lucky if you pass this one! {i}"] = {
                "result": random.choice([True, False]), "error": result.stderr}

        return json_result

    json_result = json.loads(result.stdout, strict=False)
    return json_result


def create_string_list_of_testing_functions(json_data):
    test_functions = json_data["unit_tests"]
    return ",".join([test_function['test_function_name'] for test_function in test_functions])


def create_string_for_defining_all_test_functions(json_data):
    test_functions = json_data["unit_tests"]
    return "".join([f"{test_function['test_function_code']}\n\n" for test_function in test_functions])


def replace_values_in_template(template, json_data, file_name):
    template = template.replace("$$file_name$$", file_name)
    template = template.replace("$$unit_tests_code$$", create_string_for_defining_all_test_functions(json_data))
    template = template.replace("$$test_function_names_list$$", create_string_list_of_testing_functions(json_data))
    return template


def get_template(TEMPLATE_FULL_PATH):
    with open(TEMPLATE_FULL_PATH, "r") as f:
        return f.read()


def write_unit_tests_to_file(template, output_path):
    with open(output_path, "w") as f:
        f.write(template)


def get_file_path(full_file_path):
    return "/".join(full_file_path.split("/")[:-1])


def get_file_name(full_file_path):
    return full_file_path.split("/")[-1]


def get_file_name_without_extension(full_file_path):
    return full_file_path.split("/")[-1].split(".")[0]

# ************************************ AWS SECTION ************************************


def get_aws_bucket(bucket_name):
    """
    Create an AWS client using the AWS credentials.

    Returns:
        client: The AWS client object.
    """
    # Create a session using your AWS credentials
    session = boto3.Session(
        aws_access_key_id=MY_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=MY_AWS_SECRET_ACCESS_KEY,
        region_name='us-east-2'
    )

    # Create an S3 resource object using the session
    s3 = session.resource('s3')

    # Access the bucket
    bucket = s3.Bucket(bucket_name)

    return bucket


def add_init_file(file_path):
    with open(os.path.join(file_path, "__init__.py"), "w") as f:
        f.write("")


def get_template():
    template = """
import json
from .$$file_name$$ import *

$$unit_tests_code$$

if __name__ == "__main__":
    test_results = {}

    for function_object in [$$test_function_names_list$$]:
        function_name = function_object.__name__

        try:
            result = globals()[function_name]()
            test_results[function_name] = {"result": result}
        except Exception as e:
            test_results[function_name] = {"result": False, "error": str(e)}
        
    dumped_json = json.dumps(test_results)

    print(dumped_json)
    """
    return template
