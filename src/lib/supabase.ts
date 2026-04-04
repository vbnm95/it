import "server-only";

function getRequiredEnv(name: string, value: string | undefined): string {
    const normalized = value?.trim();

    if (!normalized) {
        throw new Error(`${name} 환경변수가 설정되지 않았습니다.`);
    }

    return normalized;
}

function normalizeProjectUrl(rawValue: string): string {
    const value = rawValue.trim().replace(/^['"]|['"]$/g, "");

    if (/^postgres(ql)?:\/\//i.test(value)) {
        throw new Error(
            "NEXT_PUBLIC_SUPABASE_URL에는 DB 연결 문자열이 아니라 Supabase Project URL을 넣어야 합니다.",
        );
    }

    if (value.includes("pooler.supabase.com")) {
        throw new Error(
            "NEXT_PUBLIC_SUPABASE_URL에 pooler 주소가 들어가 있습니다. Supabase 대시보드의 Project URL(예: https://프로젝트ID.supabase.co)로 바꿔주세요.",
        );
    }

    const withProtocol = /^https?:\/\//i.test(value) ? value : `https://${value}`;

    let parsed: URL;
    try {
        parsed = new URL(withProtocol);
    } catch {
        throw new Error(
            "NEXT_PUBLIC_SUPABASE_URL 형식이 올바르지 않습니다. 예: https://프로젝트ID.supabase.co",
        );
    }

    const cleanedPath = parsed.pathname
        .replace(/\/rest\/v1\/?$/i, "")
        .replace(/\/$/, "");

    return `${parsed.origin}${cleanedPath}`;
}

function getRestBaseUrl(): string {
    const rawProjectUrl = getRequiredEnv(
        "NEXT_PUBLIC_SUPABASE_URL",
        process.env.NEXT_PUBLIC_SUPABASE_URL,
    );

    const projectUrl = normalizeProjectUrl(rawProjectUrl);
    return `${projectUrl}/rest/v1`;
}

function getHeaders(): HeadersInit {
    const anonKey = getRequiredEnv(
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    );

    return {
        apikey: anonKey,
        Authorization: `Bearer ${anonKey}`,
        Accept: "application/json",
        "Content-Type": "application/json",
    };
}

function buildRestUrl(table: string, queryString: string): string {
    const baseUrl = getRestBaseUrl();
    const url = new URL(`${table}`, `${baseUrl}/`);
    url.search = queryString;
    return url.toString();
}

export async function supabaseSelectMany<T>(
    table: string,
    queryString: string,
): Promise<T[]> {
    const response = await fetch(buildRestUrl(table, queryString), {
        headers: getHeaders(),
        cache: "no-store",
    });

    if (!response.ok) {
        const message = await response.text();
        throw new Error(
            `Supabase 조회 실패 [${table}] (${response.status}): ${message}`,
        );
    }

    return (await response.json()) as T[];
}

export async function supabaseSelectSingle<T>(
    table: string,
    queryString: string,
): Promise<T | null> {
    const rows = await supabaseSelectMany<T>(table, `${queryString}&limit=1`);
    return rows[0] ?? null;
}