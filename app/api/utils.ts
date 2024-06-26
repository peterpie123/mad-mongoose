import { createClient } from "@/utils/supabase/server";
import { LambdaClient, InvokeCommand, LogType } from "@aws-sdk/client-lambda";
import { getInstallationId } from "./github-utils";

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

    return data[0];
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
        InvocationType: "Event",
    });

    console.log("Invoking lambda for test run", testRun.id);
    const response = await lambda.send(command);
    return response;
}

export async function getOrCreateRepo(repoUrl: string): Promise<any> {
    const supabase = createClient();
    const { data, error } = await supabase
        .from("repository")
        .select()
        .eq("url", repoUrl);

    if (error) {
        console.log(error);
        throw error;
    }

    if (data.length === 0) {
        const { data, error } = await supabase
            .from("repository")
            .insert([{ url: repoUrl, installation_id: await getInstallationId(repoUrl) }])
            .select();

        if (error) {
            console.log(error);
            throw error;
        }

        return data[0];
    }

    return data[0];
}

