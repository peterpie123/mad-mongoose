import { createClient } from "@/utils/supabase/server";

export async function insertPendingTestRun(stubRun: any): Promise<number> {
    const supabase = createClient();
    const { data, error } = await supabase
        .from("testrun")
        .insert(stubRun)
        .select();

    if (!data) {
        console.log(error);
        throw error;
    }
    return data[0].id;
}
