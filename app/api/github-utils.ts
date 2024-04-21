import { App } from "octokit";

const app = new App({
    appId: 881567,
    privateKey: process.env.GITHUB_TOKEN as string,
})

function getRepoOwnerFromUrl(repoUrl: string) {
    return repoUrl.split("/")[3];
}

function getRepoNameFromUrl(repoUrl: string) {
    return repoUrl.split("/")[4];
}


export async function getPRFiles(repoUrl: string, prId: number, installationId: number): Promise<string[]> {
    const octokit = await app.getInstallationOctokit(installationId)

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

export async function leavePRComment(repoUrl: string, prId: number, body: string, installationId: number): Promise<number> {
    const octokit = await app.getInstallationOctokit(installationId)

    const result = await octokit.request('POST /repos/{owner}/{repo}/issues/{issue_number}/comments', {
        owner: getRepoOwnerFromUrl(repoUrl),
        repo: getRepoNameFromUrl(repoUrl),
        issue_number: prId,
        body: body,
        headers: {
            'X-GitHub-Api-Version': '2022-11-28'
        }
    });
    return result.data.id;
}

export async function updatePRComment(repoUrl: string, commentId: number, newBody: string, installationId: number): Promise<any> {
    const octokit = await app.getInstallationOctokit(installationId)

    const result = await octokit.request('PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}', {
        owner: getRepoOwnerFromUrl(repoUrl),
        repo: getRepoNameFromUrl(repoUrl),
        comment_id: commentId,
        body: newBody,
        headers: {
            'X-GitHub-Api-Version': '2022-11-28'
        }
    });
    return result.data;
}

export async function getInstallationId(repoUrl: string) {
    const result = await app.octokit.request('GET /repos/{owner}/{repo}/installation', {
        owner: getRepoOwnerFromUrl(repoUrl),
        repo: getRepoNameFromUrl(repoUrl),
        headers: {
            'X-GitHub-Api-Version': '2022-11-28'
        }
    });

    return result.data.id;
}
