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


export async function getPRFiles(repoUrl: string, prId: number): Promise<string[]> {
    const octokit = await app.getInstallationOctokit(49844178)

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

export async function leavePRComment(repoUrl: string, prId: number) {
    const octokit = await app.getInstallationOctokit(49844178)

    await octokit.request('POST /repos/{owner}/{repo}/issues/{issue_number}/comments', {
        owner: getRepoOwnerFromUrl(repoUrl),
        repo: getRepoNameFromUrl(repoUrl),
        issue_number: prId,
        body: 'Me too',
        headers: {
            'X-GitHub-Api-Version': '2022-11-28'
        }
    })
}
