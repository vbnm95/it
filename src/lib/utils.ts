export function normalizeStockCode(value: string | number): string {
    return String(value).padStart(6, "0");
}

export function formatCurrency(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) {
        return "-";
    }

    return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

export function formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) {
        return "-";
    }

    return value.toLocaleString("ko-KR");
}

export function formatDate(value: string | null | undefined): string {
    if (!value) return "-";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).format(date);
}

export function formatPercent(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) {
        return "-";
    }

    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
}

export function formatPercentPoint(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) {
        return "-";
    }

    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%p`;
}

export function normalizeExternalUrl(
    url: string | null | undefined,
): string | null {
    if (!url) return null;

    const trimmed = url.trim();
    if (!trimmed) return null;

    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        return trimmed;
    }

    return `https://${trimmed}`;
}