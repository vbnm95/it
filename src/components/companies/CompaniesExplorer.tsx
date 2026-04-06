"use client";

import { useMemo, useState } from "react";

import CompanyCard from "@/components/companies/CompanyCard";
import type { Company, MarketType } from "@/types/company";

type MarketFilter = "ALL" | MarketType;
type SortOption = "LATEST" | "RETURN_DESC" | "RETURN_ASC" | "OWNERSHIP_DESC";

interface CompaniesExplorerProps {
    companies: Company[];
}

function getReturnSortValue(value: number | null, direction: "asc" | "desc") {
    if (value === null) {
        return direction === "asc"
            ? Number.POSITIVE_INFINITY
            : Number.NEGATIVE_INFINITY;
    }

    return value;
}

function getOwnershipSortValue(value: number | null) {
    if (value === null) {
        return Number.NEGATIVE_INFINITY;
    }

    return value;
}

export default function CompaniesExplorer({
    companies,
}: CompaniesExplorerProps) {
    const [search, setSearch] = useState("");
    const [marketFilter, setMarketFilter] = useState<MarketFilter>("ALL");
    const [sortOption, setSortOption] = useState<SortOption>("LATEST");

    const filteredCompanies = useMemo(() => {
        let items = [...companies];

        if (search.trim()) {
            const q = search.trim().toLowerCase();
            const numericQuery = search.replace(/\D/g, "");

            items = items.filter(
                (company) =>
                    company.companyName.toLowerCase().includes(q) ||
                    company.stockCode.includes(numericQuery || q),
            );
        }

        if (marketFilter !== "ALL") {
            items = items.filter((company) => company.marketType === marketFilter);
        }

        if (sortOption === "RETURN_DESC") {
            items.sort(
                (a, b) =>
                    getReturnSortValue(b.returnSinceIpo, "desc") -
                    getReturnSortValue(a.returnSinceIpo, "desc"),
            );
        } else if (sortOption === "RETURN_ASC") {
            items.sort(
                (a, b) =>
                    getReturnSortValue(a.returnSinceIpo, "asc") -
                    getReturnSortValue(b.returnSinceIpo, "asc"),
            );
        } else if (sortOption === "OWNERSHIP_DESC") {
            items.sort(
                (a, b) =>
                    getOwnershipSortValue(b.keyShareholdersChangePct) -
                    getOwnershipSortValue(a.keyShareholdersChangePct),
            );
        } else {
            items.sort((a, b) => b.listingDate.localeCompare(a.listingDate));
        }

        return items;
    }, [companies, marketFilter, search, sortOption]);

    const filterButtonClass = (active: boolean) =>
        `rounded-2xl px-4 py-2 text-sm font-medium transition ${active
            ? "bg-slate-900 text-white shadow-sm"
            : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900"
        }`;

    return (
        <>
            <p className="text-sm font-medium text-slate-500">Companies</p>

            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
                최근 신규상장 기업 목록
            </h1>

            <p className="mt-4 text-base leading-7 text-slate-600">
                회사명, 시장구분, 상장 후 수익률, IPO 당시 주요 주주 지분율 합계를
                기준으로 빠르게 탐색할 수 있습니다.
            </p>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div>
                    <label className="text-sm font-medium text-slate-700">검색</label>
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="회사명 또는 종목코드 검색"
                        className="mt-3 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-slate-400"
                    />
                </div>

                <div className="mt-6">
                    <p className="text-sm font-medium text-slate-700">시장 필터</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => setMarketFilter("ALL")}
                            className={filterButtonClass(marketFilter === "ALL")}
                        >
                            전체
                        </button>
                        <button
                            type="button"
                            onClick={() => setMarketFilter("KOSPI")}
                            className={filterButtonClass(marketFilter === "KOSPI")}
                        >
                            코스피
                        </button>
                        <button
                            type="button"
                            onClick={() => setMarketFilter("KOSDAQ")}
                            className={filterButtonClass(marketFilter === "KOSDAQ")}
                        >
                            코스닥
                        </button>
                    </div>
                </div>

                <div className="mt-6">
                    <p className="text-sm font-medium text-slate-700">정렬</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => setSortOption("LATEST")}
                            className={filterButtonClass(sortOption === "LATEST")}
                        >
                            최근 상장순
                        </button>
                        <button
                            type="button"
                            onClick={() => setSortOption("RETURN_DESC")}
                            className={filterButtonClass(sortOption === "RETURN_DESC")}
                        >
                            수익률 높은순
                        </button>
                        <button
                            type="button"
                            onClick={() => setSortOption("RETURN_ASC")}
                            className={filterButtonClass(sortOption === "RETURN_ASC")}
                        >
                            수익률 낮은순
                        </button>
                        <button
                            type="button"
                            onClick={() => setSortOption("OWNERSHIP_DESC")}
                            className={filterButtonClass(sortOption === "OWNERSHIP_DESC")}
                        >
                            IPO 당시 주요 주주 지분율 합계 큰순
                        </button>
                    </div>
                </div>
            </section>

            <section className="mt-8">
                <div className="flex items-end justify-between">
                    <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                        기업 목록
                    </h2>
                    <p className="text-sm text-slate-500">{filteredCompanies.length}개 결과</p>
                </div>

                {filteredCompanies.length ? (
                    <div className="mt-6 grid gap-4 lg:grid-cols-2">
                        {filteredCompanies.map((company) => (
                            <CompanyCard key={company.id} company={company} />
                        ))}
                    </div>
                ) : (
                    <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
                        조건에 맞는 기업이 없습니다.
                    </div>
                )}
            </section>
        </>
    );
}