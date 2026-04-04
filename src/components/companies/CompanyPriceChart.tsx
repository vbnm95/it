"use client";

import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import type { PricePoint } from "@/types/company";
import { formatNumber } from "@/lib/utils";

interface CompanyPriceChartProps {
    data: PricePoint[];
}

interface CustomTooltipProps {
    active?: boolean;
    payload?: Array<{
        value?: number | string;
    }>;
    label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
    if (!active || !payload?.length) {
        return null;
    }

    const rawValue = payload[0]?.value;
    const numericValue =
        typeof rawValue === "number"
            ? rawValue
            : typeof rawValue === "string"
                ? Number(rawValue)
                : null;

    return (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-md">
            <p className="text-xs text-slate-500">날짜</p>
            <p className="text-sm font-medium text-slate-900">{label ?? "-"}</p>
            <p className="mt-3 text-xs text-slate-500">종가</p>
            <p className="text-sm font-semibold text-slate-900">
                {numericValue !== null && Number.isFinite(numericValue)
                    ? `${formatNumber(numericValue)}원`
                    : "-"}
            </p>
        </div>
    );
}

export default function CompanyPriceChart({
    data,
}: CompanyPriceChartProps) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div>
                <h2 className="text-lg font-semibold text-slate-900">주가 흐름</h2>
                <p className="mt-2 text-sm text-slate-500">
                    상장 이후 종가 기준 데이터
                </p>
            </div>

            {!data.length ? (
                <div className="mt-6 flex h-72 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
                    주가 데이터가 아직 없습니다.
                </div>
            ) : (
                <div className="mt-6 h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                            <XAxis
                                dataKey="date"
                                tick={{ fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                                minTickGap={24}
                            />
                            <YAxis
                                tick={{ fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value: number) =>
                                    `${Math.round(Number(value) / 1000)}k`
                                }
                                width={52}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Line
                                type="monotone"
                                dataKey="close"
                                stroke="#0f172a"
                                strokeWidth={2}
                                dot={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </section>
    );
}