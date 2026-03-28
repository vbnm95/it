export function formatNumber(value: number): string {
    return new Intl.NumberFormat("ko-KR").format(value);
}

export function formatPercent(value: number, digits = 1): string {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(digits)}%`;
}

export function formatPercentPoint(value: number, digits = 1): string {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(digits)}%p`;
}