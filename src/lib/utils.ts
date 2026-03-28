export function formatNumber(value: number): string {
    return new Intl.NumberFormat("ko-KR").format(value);
}

export function formatPercent(value: number): string {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}%`;
}

export function formatPercentPoint(value: number): string {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}%p`;
}