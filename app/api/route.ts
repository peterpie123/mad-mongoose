import { insertPendingTestRun } from "./utils";

export async function POST(request: Request) {
    const json = await request.json();

    if (!["opened", "reopened", "synchronize"].includes(json.action)) {
        return new Response("Hello World!", {
            headers: { "content-type": "text/plain" },
        });
    }

    let stubRun = {
        repo_url: "yoyoyo",
        pullrequest_id: json.number,
    };
    let id = await insertPendingTestRun(stubRun);

    return new Response(`Created response ${id}`, {
        headers: { "content-type": "text/plain" },
    });
}
