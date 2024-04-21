import { createClient } from "@/utils/supabase/server";
import { LambdaClient, InvokeCommand, LogType } from "@aws-sdk/client-lambda";
import { Provider } from "react";

const lambda = new LambdaClient();

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

export async function invokeLambda(testRun: any) {
    const command = new InvokeCommand({
        FunctionName: "MadMongooseBackend",
        Payload: JSON.stringify({
            unique_id: testRun.id,
            repo_url: testRun.clone_url,
            branch_name: testRun.branch_name,
            pullrequest_id: testRun.pullrequest_id,
        }),
        LogType: LogType.Tail,
    });
    console.log(command);

    const { Payload, LogResult } = await lambda.send(command);
    const result = Buffer.from(Payload).toString();
    const logs = Buffer.from(LogResult, "base64").toString();
    return { logs, result };
}
