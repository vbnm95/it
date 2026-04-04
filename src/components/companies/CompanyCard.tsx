import Link from "next/link";

import type { Company } from "@/types/company";
import {
    formatCurrency,
    formatDate,
    formatPercent,
    formatPercentPoint,
} from "@/lib/utils";

interface CompanyCardProps {
    company: Company;
}

export default function CompanyCard({ company }: CompanyCardProps) {
    const returnColor =
        company.returnSinceIpo !== null && company.returnSinceIpo > 0
            ? "text-emerald-600"
            : company.returnSinceIpo !== null && company.returnSinceIpo < 0
                ? "text-rose-600"
                : "text-slate-600";

    return (
        <Link
            href={`/companies/${company.stockCode}`}
            className="block rounded-3xl border border-slate-200 bg-white p-6 transition hover:border-slate-300 hover:shadow-sm"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h3 className="text-xl font-semibold tracking-tight text-slate-900">
                        {company.companyName}
                    </h3>
                    <p className="mt-2 text-sm text-slate-500">
                        {company.marketType} · {company.stockCode} · {company.industry}
                    </p>
                </div>

                <div className="text-right">
                    <p className="text-xs font-medium text-slate-400">상장 후 수익률</p>
                    <p className={`mt-1 text-lg font-semibold ${returnColor}`}>
                        {formatPercent(company.returnSinceIpo)}
                    </p>
                </div>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-xs font-medium text-slate-400">상장일</p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                        {formatDate(company.listingDate)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-xs font-medium text-slate-400">공모가</p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                        {formatCurrency(company.offeringPrice)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-xs font-medium text-slate-400">현재가</p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                        {formatCurrency(company.currentPrice)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-3">
                    <p className="text-xs font-medium text-slate-400">
                        주요주주 지분율 변화
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                        {formatPercentPoint(company.keyShareholdersChangePct)}
                    </p>
                </div>
            </div>

            <div className="mt-4 rounded-2xl border border-slate-100 px-4 py-3">
                <p className="text-xs font-medium text-slate-400">최근 공시일</p>
                <p className="mt-2 text-sm font-medium text-slate-900">
                    {formatDate(company.latestDisclosureDate)}
                </p>
            </div>
        </Link>
    );
}