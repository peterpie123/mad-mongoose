import { getInstallationId, getPRFiles, leavePRComment, updatePRComment } from "./github-utils";
import { getOrCreateRepo, insertPendingTestRun, invokeLambda, updateTestRun } from "./utils";

/** Called by the GitHub webhook for an opened PR. */
export async function POST(request: Request) {
    const json = await request.json();

    if (!["opened", "reopened", "synchronize"].includes(json.action)) {
        return new Response("Not interested in these changes.", {
            headers: { "content-type": "text/plain" },
        });
    }

    let testRun = {
        repo_url: json.pull_request.head.repo.html_url,
        clone_url: json.pull_request.head.repo.clone_url,
        pullrequest_id: json.number,
        branch_name: json.pull_request.head.ref,
    };
    const repo = await getOrCreateRepo(testRun.repo_url);
    let id = await insertPendingTestRun(testRun);

    let changedFiles = (await getPRFiles(testRun.repo_url, testRun.pullrequest_id, repo.installation_id)).filter((file) => file.endsWith(".py")
        && !file.includes("/tests/") &&
        !file.includes("__init__.py"));
    invokeLambda({ ...testRun, id }, changedFiles);
    let commentId = await leavePRComment(testRun.repo_url, testRun.pullrequest_id,
        `Generating and running tests for PR ${testRun.pullrequest_id}.\n\nIn the meantime why don't you touch grass.`, repo.installation_id);
    await updateTestRun(id, { comment_id: commentId });

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
    const repo = await getOrCreateRepo(result.repo_url);
    await updatePRComment(result.repo_url, result.comment_id,
        `Tests run: ${json.tests_run}, Tests failed: ${json.tests_failed}.`, repo.installation_id);


    return new Response(JSON.stringify(result), {
        headers: { "content-type": "application/json" },
    });
}