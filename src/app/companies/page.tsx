"use client";

import { useMemo, useState } from "react";
import PageContainer from "@/components/layout/PageContainer";
import CompanyCard from "@/components/companies/CompanyCard";
import { mockCompanies } from "@/data/mockCompanies";

type MarketFilter = "ALL" | "KOSPI" | "KOSDAQ";
type SortOption = "LATEST" | "RETURN_DESC" | "RETURN_ASC" | "OWNERSHIP_DESC";

export default function CompaniesPage() {
    const [search, setSearch] = useState("");
    const [marketFilter, setMarketFilter] = useState<MarketFilter>("ALL");
    const [sortOption, setSortOption] = useState<SortOption>("LATEST");

    const filteredCompanies = useMemo(() => {
        let items = [...mockCompanies];

        if (search.trim()) {
            const q = search.trim().toLowerCase();
            items = items.filter(
                (company) =>
                    company.companyName.toLowerCase().includes(q) ||
                    company.stockCode.includes(q)
            );
        }

        if (marketFilter !== "ALL") {
            items = items.filter((company) => company.marketType === marketFilter);
        }

        if (sortOption === "RETURN_DESC") {
            items.sort((a, b) => b.returnSinceIpo - a.returnSinceIpo);
        } else if (sortOption === "RETURN_ASC") {
            items.sort((a, b) => a.returnSinceIpo - b.returnSinceIpo);
        } else if (sortOption === "OWNERSHIP_DESC") {
            items.sort(
                (a, b) => Math.abs(b.keyShareholdersChangePct) - Math.abs(a.keyShareholdersChangePct)
            );
        } else {
            items.sort((a, b) => b.listingDate.localeCompare(a.listingDate));
        }

        return items;
    }, [search, marketFilter, sortOption]);

    const filterButtonClass = (active: boolean) =>
        `rounded-2xl px-4 py-2 text-sm font-medium transition ${active
            ? "bg-slate-900 text-white shadow-sm"
            : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900"
        }`;

    return (
        <PageContainer>
            <section>
                <p className="text-sm font-medium text-slate-500">Companies</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
                    최근 1년 신규상장 기업 목록
                </h1>
                <p className="mt-4 text-base leading-7 text-slate-600">
                    회사명, 시장구분, 상장 후 수익률, 주요주주 지분율 변화를 기준으로 빠르게 탐색할 수 있습니다.
                </p>
            </section>

            <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
                    <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700">
                            검색
                        </label>
                        <input
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="회사명 또는 종목코드 검색"
                            className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-slate-400"
                        />
                    </div>

                    <div>
                        <p className="mb-2 text-sm font-medium text-slate-700">시장 필터</p>
                        <div className="flex flex-wrap gap-2">
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
                </div>

                <div className="mt-5">
                    <p className="mb-2 text-sm font-medium text-slate-700">정렬</p>
                    <div className="flex flex-wrap gap-2">
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
                            주요주주 변화 큰순
                        </button>
                    </div>
                </div>
            </section>

            <section className="mt-8">
                <div className="mb-4 flex items-center justify-between gap-3">
                    <h2 className="text-lg font-semibold text-slate-900">기업 목록</h2>
                    <p className="text-sm text-slate-500">{filteredCompanies.length}개 결과</p>
                </div>

                <div className="space-y-4">
                    {filteredCompanies.map((company) => (
                        <CompanyCard key={company.stockCode} company={company} />
                    ))}
                </div>
            </section>
        </PageContainer>
    );
}
