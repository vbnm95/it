export const dynamic = "force-dynamic";

import Link from "next/link";

import PageContainer from "@/components/layout/PageContainer";
import SummaryCard from "@/components/dashboard/SummaryCard";
import { getCompanies } from "@/lib/it-data";
import { formatPercent } from "@/lib/utils";

function getReturnColor(value: number | null) {
  if (value === null) return "text-slate-600";
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-rose-600";
  return "text-slate-600";
}

export default async function HomePage() {
  const companies = await getCompanies();

  const total = companies.length;
  const kospi = companies.filter((c) => c.marketType === "KOSPI").length;
  const kosdaq = companies.filter((c) => c.marketType === "KOSDAQ").length;

  const hasReturnData = companies.some((c) => c.returnSinceIpo !== null);

  const topFive = [...companies]
    .sort((a, b) => {
      if (hasReturnData) {
        const aValue = a.returnSinceIpo ?? Number.NEGATIVE_INFINITY;
        const bValue = b.returnSinceIpo ?? Number.NEGATIVE_INFINITY;
        return bValue - aValue;
      }

      return b.listingDate.localeCompare(a.listingDate);
    })
    .slice(0, 5);

  return (
    <PageContainer>
      <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium text-slate-500">IT · IPO Trace</p>

        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900">
          최근 1년 신규상장 기업의
          <br />
          주가 흐름과 지분율 변화를 추적합니다.
        </h1>

        <p className="mt-5 max-w-3xl text-base leading-7 text-slate-600">
          코스피·코스닥 신규상장 기업을 대상으로 상장 이후 가격 흐름, 최근
          공시, 최대주주 및 특수관계인 지분율 변화를 한 화면에서 확인하는 웹앱
          MVP입니다.
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <SummaryCard label="최근 1년 신규상장 기업 수" value={`${total}개`} />
          <SummaryCard label="코스피 개수" value={`${kospi}개`} />
          <SummaryCard label="코스닥 개수" value={`${kosdaq}개`} />
        </div>
      </section>

      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
              상장 후 수익률 상위 5개
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              최근 1년 신규상장 기업 중 상장 이후 수익률이 높은 종목을 먼저
              보여줍니다.
            </p>
          </div>

          <Link
            href="/companies"
            className="rounded-2xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            전체 기업 보기
          </Link>
        </div>

        {topFive.length ? (
          <div className="grid gap-4">
            {topFive.map((company, index) => (
              <Link
                key={company.id}
                href={`/companies/${company.stockCode}`}
                className="rounded-3xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                      {index + 1}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-lg font-semibold text-slate-900">
                        {company.companyName}
                      </p>
                      <p className="mt-1 truncate text-sm text-slate-500">
                        {company.marketType} · {company.stockCode} ·{" "}
                        {company.industry}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <p className="text-xs font-medium text-slate-400">
                      상장 후 수익률
                    </p>
                    <p
                      className={`mt-1 text-lg font-semibold ${getReturnColor(
                        company.returnSinceIpo,
                      )}`}
                    >
                      {formatPercent(company.returnSinceIpo)}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
            표시할 기업 데이터가 없습니다.
          </div>
        )}
      </section>
    </PageContainer>
  );
}