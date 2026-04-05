import Link from "next/link";

import type { Company } from "@/types/company";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface CompanyCardProps {
    company: Company;
}

function formatShortDate(value: string): string {
    if (!value) return "-";

    const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return value;

    const [, year, month, day] = match;
    return `${year.slice(2)}-${month}-${day}`;
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
            className="group block rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h3 className="text-2xl font-semibold tracking-tight text-slate-900">
                        {company.companyName}
                    </h3>
                    <p className="mt-3 text-sm text-slate-500">
                        {company.marketType} · {company.stockCode} · {company.industry}
                    </p>
                </div>

                <div className="text-right">
                    <p className="text-xs font-medium text-slate-400">상장 후 수익률</p>
                    <p className={`mt-2 text-3xl font-semibold ${returnColor}`}>
                        {formatPercent(company.returnSinceIpo)}
                    </p>
                </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-2xl bg-slate-50 px-4 py-4">
                    <p className="text-xs font-medium text-slate-400">상장일</p>
                    <p className="mt-2 text-base font-semibold text-slate-900">
                        {formatShortDate(company.listingDate)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-4">
                    <p className="text-xs font-medium text-slate-400">공모가</p>
                    <p className="mt-2 text-base font-semibold text-slate-900">
                        {formatCurrency(company.offeringPrice)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-4">
                    <p className="text-xs font-medium text-slate-400">현재가</p>
                    <p className="mt-2 text-base font-semibold text-slate-900">
                        {formatCurrency(company.currentPrice)}
                    </p>
                </div>

                <div className="rounded-2xl bg-slate-50 px-4 py-4">
                    <p className="text-xs font-medium leading-5 text-slate-400">
                        주요 주주
                        <br />
                        지분율 합계
                    </p>
                    <p className="mt-2 text-base font-semibold text-slate-900">
                        {formatPercent(company.keyShareholdersChangePct)}
                    </p>
                </div>
            </div>
        </Link>
    );
}