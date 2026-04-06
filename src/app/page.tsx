import Link from "next/link";

import PageContainer from "@/components/layout/PageContainer";
import { getCompanies } from "@/lib/it-data";
import { formatPercent } from "@/lib/utils";

export const dynamic = "force-dynamic";

function getReturnSortValue(value: number | null) {
  return value ?? Number.NEGATIVE_INFINITY;
}

export default async function HomePage() {
  const companies = await getCompanies();

  const total = companies.length;
  const kospi = companies.filter((c) => c.marketType === "KOSPI").length;
  const kosdaq = companies.filter((c) => c.marketType === "KOSDAQ").length;

  const topFive = [...companies]
    .sort(
      (a, b) =>
        getReturnSortValue(b.returnSinceIpo) -
        getReturnSortValue(a.returnSinceIpo),
    )
    .slice(0, 5);

  return (
    <PageContainer>
      <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium text-slate-500">IT · IPO Trace</p>

        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-5xl">
          신규 상장 기업의
          <br />
          상장 후 주가 흐름을 추적합니다.
        </h1>

        <p className="mt-6 max-w-3xl text-base leading-7 text-slate-600">
          IPO Trace는 공모를 통해 신규상장한 기업을 대상으로, 공모가와 IPO 당시
          주요 주주 정보, 그리고 상장 후 가격 흐름을 구조화해서 보여주는
          데이터 기반 웹앱입니다.
        </p>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-400">추적 기업 수</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{total}개</p>
          <p className="mt-2 text-sm text-slate-500">현재 추적 대상 기업 기준</p>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-400">KOSPI</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">{kospi}개</p>
          <p className="mt-2 text-sm text-slate-500">현재 추적 대상 기업 수</p>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-400">KOSDAQ</p>
          <p className="mt-3 text-3xl font-semibold text-slate-900">
            {kosdaq}개
          </p>
          <p className="mt-2 text-sm text-slate-500">현재 추적 대상 기업 수</p>
        </div>
      </section>

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
            상장 후 수익률 상위 5개
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            현재 추적 중인 기업 중 상장 이후 수익률이 높은 종목을 먼저 보여줍니다.
          </p>
        </div>

        <div className="mt-6 space-y-5">
          {topFive.length ? (
            topFive.map((company, index) => {
              const returnValue = company.returnSinceIpo;
              const returnColor =
                returnValue !== null && returnValue > 0
                  ? "text-emerald-600"
                  : returnValue !== null && returnValue < 0
                    ? "text-rose-600"
                    : "text-slate-600";

              return (
                <Link
                  key={company.id}
                  href={`/companies/${company.stockCode}`}
                  className="flex items-center justify-between gap-6 rounded-[28px] border border-slate-200 bg-white px-5 py-5 transition hover:border-slate-300 hover:bg-slate-50"
                >
                  <div className="flex min-w-0 items-center gap-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                      {index + 1}
                    </div>

                    <div className="min-w-0">
                      <div className="truncate text-xl font-semibold tracking-tight text-slate-900">
                        {company.companyName}
                      </div>
                      <div className="mt-2 truncate text-sm text-slate-500">
                        {company.marketType} · {company.stockCode}
                      </div>
                    </div>
                  </div>

                  <div className="shrink-0 text-right">
                    <div className="text-xs font-medium text-slate-400">
                      상장 후 수익률
                    </div>
                    <div className={`mt-2 text-3xl font-semibold ${returnColor}`}>
                      {formatPercent(returnValue)}
                    </div>
                  </div>
                </Link>
              );
            })
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 px-6 py-12 text-center text-sm text-slate-500">
              아직 표시할 기업 데이터가 없습니다.
            </div>
          )}
        </div>
      </section>
    </PageContainer>
  );
}