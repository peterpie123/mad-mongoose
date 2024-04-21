import { createClient } from "@/utils/supabase/server";
import { LambdaClient, InvokeCommand, LogType } from "@aws-sdk/client-lambda";
import { Octokit } from "octokit";

const lambda = new LambdaClient({ region: 'us-east-2' });

export async function insertPendingTestRun(testRun: any): Promise<number> {
    const supabase = createClient();
    const { data, error } = await supabase
        .from("testrun")
        .insert(testRun)
        .select();

    if (!data) {
        console.log(error);
        throw error;
    }
    return data[0].id;
}

export async function updateTestRun(id: number, testRun: any): Promise<any> {
    const supabase = createClient();
    const { data, error } = await supabase
        .from("testrun")
        .update(testRun)
        .eq("id", id).select();

    if (!data) {
        console.log(error);
        throw error;
    }

    return data;
}

export async function invokeLambda(testRun: any, changedFiles: string[]) {
    const command = new InvokeCommand({
        FunctionName: "MadMongooseBackend",
        Payload: JSON.stringify({
            unique_id: testRun.id,
            repo_url: testRun.clone_url,
            branch: testRun.branch_name,
            pullrequest_id: testRun.pullrequest_id,
            changed_files: changedFiles,
        }),
        LogType: LogType.Tail,
    });

    console.log("Invoking lambda for test run", testRun.id);
    const response = await lambda.send(command);
    return response;
}

function getRepoOwnerFromUrl(repoUrl: string) {
    return repoUrl.split("/")[3];
}

function getRepoNameFromUrl(repoUrl: string) {
    return repoUrl.split("/")[4];
}

export async function getPRFiles(repoUrl: string, prId: number): Promise<string[]> {
    const octokit = new Octokit();
    const result = await octokit.request('GET /repos/{owner}/{repo}/pulls/{pull_number}/files', {
        owner: getRepoOwnerFromUrl(repoUrl),
        repo: getRepoNameFromUrl(repoUrl),
        pull_number: prId,
        headers: {
            'X-GitHub-Api-Version': '2022-11-28'
        }
    });

    return result.data.map((file: any) => file.filename);
}
