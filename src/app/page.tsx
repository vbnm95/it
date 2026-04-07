import Link from "next/link";

import PageContainer from "@/components/layout/PageContainer";
import { getCompanies } from "@/lib/it-data";

export const dynamic = "force-dynamic";

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatSignedPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "0.00%";
  }

  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatDateDot(value: string): string {
  if (!value) return "-";

  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value;

  const [, year, month, day] = match;
  return `${year}. ${month}. ${day}.`;
}

function getReturnColor(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "text-slate-500";
  }

  if (value > 0) return "text-emerald-500";
  if (value < 0) return "text-rose-500";
  return "text-slate-500";
}

function getReturnSortValue(value: number | null): number {
  return value ?? Number.NEGATIVE_INFINITY;
}

export default async function HomePage() {
  const companies = await getCompanies();

  const total = companies.length;
  const kospi = companies.filter((c) => c.marketType === "KOSPI").length;
  const kosdaq = companies.filter((c) => c.marketType === "KOSDAQ").length;

  const validReturns = companies
    .map((c) => c.returnSinceIpo)
    .filter(
      (value): value is number =>
        typeof value === "number" && Number.isFinite(value),
    );

  const gainers = validReturns.filter((value) => value > 0);
  const losers = validReturns.filter((value) => value < 0);

  const overallAvg = average(validReturns);
  const gainersAvg = average(gainers);
  const losersAvg = average(losers);

  const topFive = [...companies]
    .sort(
      (a, b) =>
        getReturnSortValue(b.returnSinceIpo) -
        getReturnSortValue(a.returnSinceIpo),
    )
    .slice(0, 5);

  const newestFive = [...companies]
    .sort((a, b) => b.listingDate.localeCompare(a.listingDate))
    .slice(0, 5);

  return (
    <PageContainer>
      <section className="rounded-[28px] border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <h1 className="text-[20px] font-semibold tracking-tight text-slate-900">
          IPO Trace?
        </h1>
        <p className="mt-3 text-[15px] leading-8 text-slate-600">
          IPO Trace는 공모를 통해 신규상장한 기업을 대상으로, 공모가와 IPO 당시
          주요 주주 정보, 그리고 상장 후 가격 흐름을 구조화해서 보여주는 <br />
          데이터 기반 웹앱입니다.
        </p>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <p className="text-[15px] font-medium text-slate-400">추적 기업 수</p>
          <p className="mt-4 text-[32px] font-semibold tracking-tight text-slate-900">
            {total}개
          </p>
          <p className="mt-3 text-[15px] text-slate-500">현재 추적 대상 기업 기준</p>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <p className="text-[15px] font-medium text-slate-400">KOSPI</p>
          <p className="mt-4 text-[32px] font-semibold tracking-tight text-slate-900">
            {kospi}개
          </p>
          <p className="mt-3 text-[15px] text-slate-500">현재 추적 대상 기업 수</p>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <p className="text-[15px] font-medium text-slate-400">KOSDAQ</p>
          <p className="mt-4 text-[32px] font-semibold tracking-tight text-slate-900">
            {kosdaq}개
          </p>
          <p className="mt-3 text-[15px] text-slate-500">현재 추적 대상 기업 수</p>
        </div>
      </section>

      <section className="mt-4 grid gap-4 md:grid-cols-3">
        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <p className="text-[15px] font-medium text-slate-400">전체 평균 수익률</p>
          <p
            className={`mt-4 text-[32px] font-semibold tracking-tight ${getReturnColor(
              overallAvg,
            )}`}
          >
            {formatSignedPercent(overallAvg)}
          </p>
          <p className="mt-3 text-[15px] text-slate-500">현재 추적 대상 기업 기준</p>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[15px] font-medium text-slate-400">기업 수</p>
              <p className="mt-4 text-[32px] font-semibold tracking-tight text-slate-900">
                {gainers.length}개
              </p>
            </div>

            <div className="text-right">
              <p className="text-[15px] font-medium text-slate-400">평균 수익률</p>
              <p className="mt-4 text-[32px] font-semibold tracking-tight text-emerald-500">
                {formatSignedPercent(gainersAvg)}
              </p>
            </div>
          </div>

          <p className="mt-3 text-[15px] text-slate-500">공모가 대비 상승 기업 수</p>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[15px] font-medium text-slate-400">기업 수</p>
              <p className="mt-4 text-[32px] font-semibold tracking-tight text-slate-900">
                {losers.length}개
              </p>
            </div>

            <div className="text-right">
              <p className="text-[15px] font-medium text-slate-400">평균 손실률</p>
              <p className="mt-4 text-[32px] font-semibold tracking-tight text-rose-500">
                {formatSignedPercent(losersAvg)}
              </p>
            </div>
          </div>

          <p className="mt-3 text-[15px] text-slate-500">공모가 대비 하락 기업 수</p>
        </div>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-6">
            <h2 className="text-[20px] font-semibold tracking-tight text-slate-900">
              상장 후 수익률 상위 5개
            </h2>
            <p className="mt-2 text-[15px] leading-7 text-slate-600">
              추적 중인 기업 중 상장 후 수익률이 높은 종목을 먼저 보여줍니다.
            </p>
          </div>

          <div className="divide-y divide-slate-200">
            {topFive.length ? (
              topFive.map((company, index) => (
                <Link
                  key={company.id}
                  href={`/companies/${company.stockCode}`}
                  className="flex items-center justify-between gap-5 px-6 py-6 transition hover:bg-slate-50"
                >
                  <div className="flex min-w-0 items-center gap-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                      {index + 1}
                    </div>

                    <div className="min-w-0">
                      <div className="truncate text-[18px] font-semibold tracking-tight text-slate-900">
                        {company.companyName}
                      </div>
                      <div className="mt-2 truncate text-[15px] text-slate-500">
                        {company.marketType} · {company.stockCode}
                      </div>
                    </div>
                  </div>

                  <div className="shrink-0 text-right">
                    <div className="text-[15px] font-medium text-slate-400">
                      상장 후 수익률
                    </div>
                    <div
                      className={`mt-2 text-[18px] font-semibold tracking-tight ${getReturnColor(
                        company.returnSinceIpo,
                      )}`}
                    >
                      {formatSignedPercent(company.returnSinceIpo)}
                    </div>
                  </div>
                </Link>
              ))
            ) : (
              <div className="px-6 py-12 text-center text-sm text-slate-500">
                아직 표시할 기업 데이터가 없습니다.
              </div>
            )}
          </div>
        </div>

        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-6">
            <h2 className="text-[20px] font-semibold tracking-tight text-slate-900">
              신규 등록된 기업 5개
            </h2>
            <p className="mt-2 text-[15px] leading-7 text-slate-600">
              가장 최근에 상장된 순으로 보여줍니다.
            </p>
          </div>

          <div className="divide-y divide-slate-200">
            {newestFive.length ? (
              newestFive.map((company, index) => (
                <Link
                  key={company.id}
                  href={`/companies/${company.stockCode}`}
                  className="flex items-center justify-between gap-5 px-6 py-6 transition hover:bg-slate-50"
                >
                  <div className="flex min-w-0 items-center gap-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                      {index + 1}
                    </div>

                    <div className="min-w-0">
                      <div className="truncate text-[18px] font-semibold tracking-tight text-slate-900">
                        {company.companyName}
                      </div>
                      <div className="mt-2 truncate text-[15px] text-slate-500">
                        {company.marketType} · {company.stockCode}
                      </div>
                    </div>
                  </div>

                  <div className="shrink-0 text-right">
                    <div className="text-[15px] font-medium text-slate-400">
                      상장일
                    </div>
                    <div className="mt-2 text-[18px] font-semibold tracking-tight text-slate-900">
                      {formatDateDot(company.listingDate)}
                    </div>
                  </div>
                </Link>
              ))
            ) : (
              <div className="px-6 py-12 text-center text-sm text-slate-500">
                아직 표시할 기업 데이터가 없습니다.
              </div>
            )}
          </div>
        </div>
      </section>
    </PageContainer>
  );
}