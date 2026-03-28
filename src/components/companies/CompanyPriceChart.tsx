"use client";

import { useEffect, useRef, useState } from "react";
import {
    CartesianGrid,
    Line,
    LineChart,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import type { PricePoint } from "@/types/company";
import { formatNumber } from "@/lib/utils";

interface CompanyPriceChartProps {
    data: PricePoint[];
}

export default function CompanyPriceChart({
    data,
}: CompanyPriceChartProps) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [chartWidth, setChartWidth] = useState(0);

    useEffect(() => {
        const element = containerRef.current;
        if (!element) return;

        const updateWidth = () => {
            const nextWidth = Math.floor(element.getBoundingClientRect().width);
            setChartWidth(nextWidth > 0 ? nextWidth : 0);
        };

        updateWidth();

        const observer = new ResizeObserver((entries) => {
            const width = Math.floor(
                entries[0]?.contentRect.width ?? element.getBoundingClientRect().width
            );
            setChartWidth(width > 0 ? width : 0);
        });

        observer.observe(element);
        window.addEventListener("resize", updateWidth);

        return () => {
            observer.disconnect();
            window.removeEventListener("resize", updateWidth);
        };
    }, []);

    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4">
                <h3 className="text-lg font-semibold text-slate-900">주가 흐름</h3>
                <p className="mt-1 text-sm text-slate-500">
                    상장 이후 종가 기준 더미 데이터
                </p>
            </div>

            <div ref={containerRef} className="w-full min-w-0 overflow-hidden">
                {chartWidth > 0 ? (
                    <LineChart
                        width={chartWidth}
                        height={320}
                        data={data}
                        margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
                    >
                        <CartesianGrid vertical={false} strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={24} />
                        <YAxis
                            tick={{ fontSize: 12 }}
                            tickFormatter={(value) => `${Math.round(Number(value) / 1000)}k`}
                            width={52}
                        />
                        <Tooltip
                            formatter={(value) => [
                                `${formatNumber(Number(value))}원`,
                                "종가",
                            ]}
                            labelFormatter={(label) => `날짜: ${label}`}
                        />
                        <Line
                            type="monotone"
                            dataKey="close"
                            stroke="#355b8c"
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </LineChart>
                ) : (
                    <div className="h-[320px]" />
                )}
            </div>
        </div>
    );
}