import { getPRFiles, leavePRComment } from "./github-utils";
import { insertPendingTestRun, invokeLambda, updateTestRun } from "./utils";

export async function POST(request: Request) {
    const json = await request.json();

    if (!["opened", "reopened", "synchronize"].includes(json.action)) {
        return new Response("Hello World!", {
            headers: { "content-type": "text/plain" },
        });
    }

    let testRun = {
        repo_url: json.pull_request.head.repo.html_url,
        clone_url: json.pull_request.head.repo.clone_url,
        pullrequest_id: json.number,
        branch_name: json.pull_request.head.ref,
    };
    let id = await insertPendingTestRun(testRun);

    let changedFiles = await getPRFiles(testRun.repo_url, testRun.pullrequest_id);
    // await invokeLambda({ ...testRun, id }, changedFiles);
    leavePRComment(testRun.repo_url, testRun.pullrequest_id);


    return new Response(`Created response ${id}`, {
        headers: { "content-type": "text/plain" },
    });
}

/**
 * Accepts JSON of the form:
 * {"id", "tests_run", "tests_failed"}
 */
export async function PATCH(request: Request) {
    let json = await request.json();

    const result = await updateTestRun(json.id, json);

    return new Response(JSON.stringify(result), {
        headers: { "content-type": "application/json" },
    });
}