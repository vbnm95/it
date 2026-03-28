import Link from "next/link";
import type { Company } from "@/types/company";
import { formatNumber, formatPercentPoint } from "@/lib/utils";

interface CompanyCardProps {
    company: Company;
}

export default function CompanyCard({ company }: CompanyCardProps) {
    const returnColor =
        company.returnSinceIpo > 0
            ? "text-emerald-600"
            : company.returnSinceIpo < 0
                ? "text-rose-600"
                : "text-slate-600";

    return (
        <Link
            href={`/companies/${company.stockCode}`}
            className="block rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2">
                        <h3 className="text-lg font-semibold text-slate-900">
                            {company.companyName}
                        </h3>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                            {company.marketType}
                        </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                        {company.industry} · {company.stockCode}
                    </p>
                </div>

                <div className={`text-right text-lg font-semibold ${returnColor}`}>
                    {company.returnSinceIpo > 0 ? "+" : ""}
                    {company.returnSinceIpo.toFixed(1)}%
                </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                    <p className="text-xs text-slate-500">상장일</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {company.listingDate}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">공모가</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {formatNumber(company.offeringPrice)}원
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">현재가</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {formatNumber(company.currentPrice)}원
                    </p>
                </div>
                <div>
                    <p className="text-xs text-slate-500">지분율 변화</p>
                    <p className="mt-1 text-sm font-medium text-slate-900">
                        {formatPercentPoint(company.ownershipChangePct)}
                    </p>
                </div>
            </div>

            <p className="mt-4 text-sm text-slate-500">
                최근 공시일: {company.latestDisclosureDate}
            </p>
        </Link>
    );
}