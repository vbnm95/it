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
    formatPercentPoint,
    normalizeExternalUrl,
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

    const homepageUrl = normalizeExternalUrl(company.homepageUrl);
    const irUrl = normalizeExternalUrl(company.irUrl);

    const offeringPriceMissing = company.offeringPrice === null;
    const returnMissing = company.returnSinceIpo === null;

    return (
        <PageContainer>
            <div className="mb-6">
                <Link
                    href="/companies"
                    className="text-sm font-medium text-slate-500 transition hover:text-slate-900"
                >
                    ← 기업 목록으로 돌아가기
                </Link>
            </div>

            <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                <p className="text-sm font-medium text-slate-500">
                    {company.marketType} · {company.stockCode} · {company.industry}
                </p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
                    {company.companyName}
                </h1>

                <p className="mt-5 max-w-4xl text-base leading-7 text-slate-600">
                    상장 이후 가격 흐름, 최근 공시, 그리고 최초 상장 시점 기준 주요
                    주주와 이후 새롭게 추가된 주요 주주의 지분율 변화를 함께 확인하는
                    상세 화면입니다.
                </p>

                {(homepageUrl || irUrl) && (
                    <div className="mt-6 flex flex-wrap gap-2">
                        {homepageUrl ? (
                            <a
                                href={homepageUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                            >
                                홈페이지
                            </a>
                        ) : null}

                        {irUrl ? (
                            <a
                                href={irUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                            >
                                IR 자료
                            </a>
                        ) : null}
                    </div>
                )}
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
                            주요 주주 지분율 변화
                        </h2>
                        <p className="mt-2 text-sm leading-6 text-slate-500">
                            최초 상장 시점의 주요 주주는 지분율이 0%가 되어도 유지해서
                            보여주고, 이후 새롭게 들어온 주요 주주는 IPO 기준 0.0%로
                            표시합니다.
                        </p>
                    </div>

                    <div className="rounded-2xl bg-slate-50 px-4 py-3">
                        <p className="text-xs font-medium text-slate-400">
                            주요주주 지분율 변화 합계
                        </p>
                        <p className="mt-2 text-lg font-semibold text-slate-900">
                            {formatPercentPoint(company.keyShareholdersChangePct)}
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
                                    <th className="border-b border-slate-200 px-4 py-3 text-right text-sm font-medium text-slate-500">
                                        IPO 기준 지분율
                                    </th>
                                    <th className="border-b border-slate-200 px-4 py-3 text-right text-sm font-medium text-slate-500">
                                        최신 지분율
                                    </th>
                                    <th className="border-b border-slate-200 px-4 py-3 text-right text-sm font-medium text-slate-500">
                                        지분율 변화
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {company.keyShareholders.map((holder) => (
                                    <tr key={holder.id}>
                                        <td className="border-b border-slate-100 px-4 py-3 text-sm text-slate-900">
                                            <div className="font-medium">{holder.holderName}</div>
                                            {holder.holderRole ? (
                                                <div className="mt-1 text-xs text-slate-500">
                                                    {holder.holderRole}
                                                </div>
                                            ) : null}
                                        </td>
                                        <td className="border-b border-slate-100 px-4 py-3 text-right text-sm text-slate-700">
                                            {formatPercent(holder.ipoBasePct)}
                                        </td>
                                        <td className="border-b border-slate-100 px-4 py-3 text-right text-sm text-slate-700">
                                            {formatPercent(holder.latestPct)}
                                        </td>
                                        <td className="border-b border-slate-100 px-4 py-3 text-right text-sm font-medium text-slate-900">
                                            {formatPercentPoint(holder.changePct)}
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

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <h2 className="text-xl font-semibold text-slate-900">최근 공시</h2>
                        <p className="mt-2 text-sm text-slate-500">
                            최근 공시일: {formatDate(company.latestDisclosureDate)}
                        </p>
                    </div>
                </div>

                {company.disclosures.length ? (
                    <div className="mt-6 grid gap-3">
                        {company.disclosures.map((item) => (
                            <div
                                key={item.id}
                                className="rounded-2xl border border-slate-200 px-4 py-4"
                            >
                                <p className="font-medium text-slate-900">{item.reportName}</p>
                                <p className="mt-1 text-sm text-slate-500">
                                    {item.reportDate} · {item.filerName}
                                </p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                        아직 최근 공시 상세 데이터가 없습니다.
                    </div>
                )}
            </section>
        </PageContainer>
    );
}