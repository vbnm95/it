export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";

import PageContainer from "@/components/layout/PageContainer";
import MetricCard from "@/components/companies/MetricCard";
import CompanyPriceChart from "@/components/companies/CompanyPriceChart";
import { getCompanyDetailByStockCode } from "@/lib/it-data";
import {
    formatCurrency,
    formatDate,
    formatPercent,
} from "@/lib/utils";

interface CompanyDetailPageProps {
    params: Promise<{
        stockCode: string;
    }>;
}

function metricValueOrPending(value: string, isMissing: boolean): string {
    return isMissing ? "수집 전" : value;
}

export default async function CompanyDetailPage({
    params,
}: CompanyDetailPageProps) {
    const { stockCode } = await params;
    const company = await getCompanyDetailByStockCode(stockCode);

    if (!company) {
        notFound();
    }

    const offeringPriceMissing = company.offeringPrice === null;
    const returnMissing = company.returnSinceIpo === null;

    const ipoBasePctSum = company.keyShareholders.reduce((sum, holder) => {
        return sum + (holder.ipoBasePct ?? 0);
    }, 0);

    return (
        <PageContainer>
            <div className="mb-6">
                <Link
                    href="/companies"
                    className="inline-flex items-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
                >
                    ← 기업 목록으로 돌아가기
                </Link>
            </div>

            <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                <p className="text-sm font-medium text-slate-500">
                    {company.marketType} · {company.stockCode}
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
                    {company.companyName}
                </h1>
            </section>

            <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="상장일" value={formatDate(company.listingDate)} />
                <MetricCard
                    label="공모가"
                    value={metricValueOrPending(
                        formatCurrency(company.offeringPrice),
                        offeringPriceMissing,
                    )}
                />
                <MetricCard
                    label="현재가"
                    value={formatCurrency(company.currentPrice)}
                    subtext={
                        company.currentPriceDate
                            ? `기준일: ${formatDate(company.currentPriceDate)}`
                            : undefined
                    }
                />
                <MetricCard
                    label="상장 후 수익률"
                    value={metricValueOrPending(
                        formatPercent(company.returnSinceIpo),
                        returnMissing,
                    )}
                />
            </section>

            <section className="mt-8">
                <CompanyPriceChart data={company.priceHistory} />
            </section>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <h2 className="text-xl font-semibold text-slate-900">
                            IPO 당시 주요 주주 지분율
                        </h2>
                        <p className="mt-2 text-sm leading-6 text-slate-500">
                            IPO 당시 주요 주주의 주식의 종류와 지분율을 보여줍니다.
                        </p>
                    </div>

                    <div className="rounded-2xl bg-slate-50 px-4 py-3">
                        <p className="text-xs font-medium text-slate-400">
                            주요 주주 지분율 합계
                        </p>
                        <p className="mt-2 text-lg font-semibold text-slate-900">
                            {formatPercent(ipoBasePctSum)}
                        </p>
                    </div>
                </div>

                {company.keyShareholders.length ? (
                    <div className="mt-6 overflow-x-auto">
                        <table className="min-w-full border-separate border-spacing-0">
                            <thead>
                                <tr>
                                    <th className="border-b border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-500">
                                        주주명
                                    </th>
                                    <th className="border-b border-slate-200 px-4 py-3 text-left text-sm font-medium text-slate-500">
                                        주식의 종류
                                    </th>
                                    <th className="border-b border-slate-200 px-4 py-3 text-right text-sm font-medium text-slate-500">
                                        IPO 기준 지분율
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {company.keyShareholders.map((holder) => (
                                    <tr key={holder.id}>
                                        <td className="border-b border-slate-100 px-4 py-3 text-sm text-slate-900">
                                            <div className="font-medium">{holder.holderName}</div>
                                        </td>
                                        <td className="border-b border-slate-100 px-4 py-3 text-sm text-slate-700">
                                            {holder.holderRole ?? "-"}
                                        </td>
                                        <td className="border-b border-slate-100 px-4 py-3 text-right text-sm text-slate-700">
                                            {formatPercent(holder.ipoBasePct)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                        아직 주요 주주 상세 데이터가 없습니다.
                    </div>
                )}
            </section>
        </PageContainer>
    );
}