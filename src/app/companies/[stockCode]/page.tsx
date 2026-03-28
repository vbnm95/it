import { notFound } from "next/navigation";
import PageContainer from "@/components/layout/PageContainer";
import MetricCard from "@/components/companies/MetricCard";
import CompanyPriceChart from "@/components/companies/CompanyPriceChart";
import { mockCompanyDetails } from "@/data/mockCompanies";
import {
    formatNumber,
    formatPercent,
    formatPercentPoint,
} from "@/lib/utils";

interface CompanyDetailPageProps {
    params: Promise<{
        stockCode: string;
    }>;
}

export default async function CompanyDetailPage({
    params,
}: CompanyDetailPageProps) {
    const { stockCode } = await params;
    const company = mockCompanyDetails[stockCode];

    if (!company) {
        notFound();
    }

    return (
        <PageContainer>
            <section>
                <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                    <span>{company.marketType}</span>
                    <span>·</span>
                    <span>{company.stockCode}</span>
                    <span>·</span>
                    <span>{company.industry}</span>
                </div>

                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
                    {company.companyName}
                </h1>

                <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
                    상장 이후 가격 흐름, 최근 공시, 그리고 최초 상장 시점 기준 주요 주주와 이후 새롭게 추가된 주요 주주의 지분율 변화를 함께 확인하는 상세 화면입니다.
                </p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <MetricCard label="상장일" value={company.listingDate} />
                    <MetricCard
                        label="공모가"
                        value={`${formatNumber(company.offeringPrice)}원`}
                    />
                    <MetricCard
                        label="현재가"
                        value={`${formatNumber(company.currentPrice)}원`}
                    />
                    <MetricCard
                        label="상장 후 수익률"
                        value={formatPercent(company.returnSinceIpo)}
                    />
                </div>
            </section>

            <section className="mt-8">
                <CompanyPriceChart data={company.priceHistory} />
            </section>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
                <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                    <div>
                        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                            주요 주주 지분율 변화
                        </h2>
                        <p className="mt-2 text-sm text-slate-500">
                            최초 상장 시점의 주요 주주는 지분율이 0%가 되어도 유지해서 보여주고, 이후 새롭게 들어온 주요 주주는 IPO 기준 0.0%로 표시합니다.
                        </p>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <div className="min-w-[760px]">
                        <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-x-6 rounded-2xl bg-slate-50 px-5 py-4 text-sm font-semibold text-slate-700">
                            <div>주주명</div>
                            <div>IPO 기준 지분율</div>
                            <div>최신 지분율</div>
                            <div>지분율 변화</div>
                        </div>

                        <div className="mt-3 divide-y divide-slate-100 rounded-2xl border border-slate-200">
                            {company.keyShareholders.map((holder) => (
                                <div
                                    key={holder.id}
                                    className="grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-x-6 px-5 py-5 text-sm text-slate-900"
                                >
                                    <div className="font-semibold text-slate-900">
                                        {holder.holderName}
                                    </div>
                                    <div>{formatPercent(holder.ipoBasePct)}</div>
                                    <div>{formatPercent(holder.latestPct)}</div>
                                    <div className="font-medium text-slate-700">
                                        {formatPercentPoint(holder.changePct)}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-slate-900">최근 공시</h2>

                <div className="mt-4 space-y-3">
                    {company.disclosures.map((item) => (
                        <div
                            key={item.id}
                            className="rounded-2xl border border-slate-200 p-4"
                        >
                            <p className="font-medium text-slate-900">{item.reportName}</p>
                            <p className="mt-1 text-sm text-slate-500">
                                {item.reportDate} · {item.filerName}
                            </p>
                        </div>
                    ))}
                </div>
            </section>
        </PageContainer>
    );
}
