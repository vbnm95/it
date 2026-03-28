"use client";

import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer
} from "recharts";
import type { PricePoint } from "@/types/company";
import { formatNumber } from "@/lib/utils";

interface CompanyPriceChartProps {
    data: PricePoint[];
}

export default function CompanyPriceChart({ data }: CompanyPriceChartProps) {
    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4">
                <h3 className="text-lg font-semibold text-slate-900">주가 흐름</h3>
                <p className="mt-1 text-sm text-slate-500">
                    상장 이후 종가 기준 더미 데이터
                </p>
            </div>

            <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                        <YAxis
                            tick={{ fontSize: 12 }}
                            tickFormatter={(value) => `${Math.round(value / 1000)}k`}
                        />
                        <Tooltip
                            formatter={(value: number) => [`${formatNumber(value)}원`, "종가"]}
                            labelFormatter={(label) => `날짜: ${label}`}
                        />
                        <Line type="monotone" dataKey="close" strokeWidth={2} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}