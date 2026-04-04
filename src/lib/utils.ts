function isFiniteNumber(value: number | null | undefined): value is number {
    return typeof value === "number" && Number.isFinite(value);
}

export function normalizeStockCode(value: string): string {
    const digits = value.replace(/\D/g, "");
    if (!digits) return value;
    return digits.length >= 6 ? digits.slice(-6) : digits.padStart(6, "0");
}

export function formatNumber(value: number | null | undefined): string {
    if (!isFiniteNumber(value)) return "-";
    return new Intl.NumberFormat("ko-KR").format(value);
}

export function formatCurrency(value: number | null | undefined): string {
    if (!isFiniteNumber(value)) return "-";
    return `${formatNumber(value)}원`;
}

export function formatPercent(
    value: number | null | undefined,
    digits = 1,
): string {
    if (!isFiniteNumber(value)) return "-";
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(digits)}%`;
}

export function formatPercentPoint(
    value: number | null | undefined,
    digits = 1,
): string {
    if (!isFiniteNumber(value)) return "-";
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(digits)}%p`;
}

export function formatDate(value: string | null | undefined): string {
    if (!value) return "-";

    const trimmed = value.trim();
    if (!trimmed) return "-";

    if (/^\d{4}-\d{2}-\d{2}/.test(trimmed)) {
        return trimmed.slice(0, 10);
    }

    const date = new Date(trimmed);
    if (Number.isNaN(date.getTime())) {
        return trimmed;
    }

    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, "0");
    const day = `${date.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
}

export function normalizeExternalUrl(
    value: string | null | undefined,
): string | null {
    if (!value) return null;

    const trimmed = value.trim().replace(/^\/+/, "");
    if (!trimmed) return null;

    if (/^https?:\/\//i.test(trimmed)) {
        return trimmed;
    }

    return `https://${trimmed}`;
}