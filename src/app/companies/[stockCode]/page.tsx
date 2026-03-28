import { notFound } from "next/navigation";
import PageContainer from "@/components/layout/PageContainer";
import MetricCard from "@/components/companies/MetricCard";
import CompanyPriceChart from "@/components/companies/CompanyPriceChart";
import { mockCompanyDetails } from "@/data/mockCompanies";
import { formatNumber, formatPercent, formatPercentPoint } from "@/lib/utils";

interface CompanyDetailPageProps {
    params: Promise<{
        stockCode: string;
    }>;
}

export default async function CompanyDetailPage({
    params
}: CompanyDetailPageProps) {
    const { stockCode } = await params;
    const company = mockCompanyDetails[stockCode];

    if (!company) {
        notFound();
    }

    return (
        <PageContainer>
            <section className="rounded-[28px] border border-slate-200 bg-white p-8 shadow-sm">
                <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        {company.marketType}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        {company.stockCode}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                        {company.industry}
                    </span>
                </div>

                <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-900">
                    {company.companyName}
                </h1>

                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 sm:text-base">
                    상장 이후 가격 흐름, 최근 공시, 최대주주 및 특수관계인 지분율 변화를
                    확인하는 상세 화면입니다. 현재는 더미 데이터로 구성된 껍데기 버전입니다.
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

            <section className="mt-8 grid gap-8 xl:grid-cols-[1.6fr_1fr]">
                <CompanyPriceChart data={company.priceHistory} />

                <div className="space-y-4">
                    <MetricCard
                        label="IPO 기준 지분율"
                        value={formatPercent(company.ownership.ipoBasePct)}
                    />
                    <MetricCard
                        label="최신 지분율"
                        value={formatPercent(company.ownership.latestPct)}
                    />
                    <MetricCard
                        label="지분율 변화"
                        value={formatPercentPoint(company.ownership.changePct)}
                    />
                </div>
            </section>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-slate-900">최근 공시</h2>
                <div className="mt-4 space-y-3">
                    {company.disclosures.map((item) => (
                        <div
                            key={item.id}
                            className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                        >
                            <p className="text-sm font-medium text-slate-900">{item.reportName}</p>
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