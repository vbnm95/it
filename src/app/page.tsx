import Link from "next/link";
import PageContainer from "@/components/layout/PageContainer";
import SummaryCard from "@/components/dashboard/SummaryCard";
import { mockCompanies } from "@/data/mockCompanies";

export default function HomePage() {
  const total = mockCompanies.length;
  const kospi = mockCompanies.filter((c) => c.marketType === "KOSPI").length;
  const kosdaq = mockCompanies.filter((c) => c.marketType === "KOSDAQ").length;

  const topFive = [...mockCompanies]
    .sort((a, b) => b.returnSinceIpo - a.returnSinceIpo)
    .slice(0, 5);

  return (
    <PageContainer>
      <section>
        <p className="text-sm font-medium text-slate-500">IT · IPO Trace</p>

        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          최근 1년 신규상장 기업의
          <br />
          주가 흐름과 지분율 변화를 추적합니다.
        </h1>

        <p className="mt-5 text-base leading-7 text-slate-600 sm:text-lg">
          코스피·코스닥 신규상장 기업을 대상으로 상장 이후 가격 흐름, 최근 공시,
          최대주주 및 특수관계인 지분율 변화를 한 화면에서 확인하는 웹앱 MVP입니다.
        </p>
      </section>

      <section className="mt-10 grid gap-4 md:grid-cols-3">
        <SummaryCard
          label="최근 1년 신규상장 기업 수"
          value={`${total}개`}
          subtext="더미 데이터 기준"
        />
        <SummaryCard
          label="코스피"
          value={`${kospi}개`}
          subtext="최근 1년 신규상장"
        />
        <SummaryCard
          label="코스닥"
          value={`${kosdaq}개`}
          subtext="최근 1년 신규상장"
        />
      </section>

      <section className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
              상장 후 수익률 상위 5개
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              최근 1년 신규상장 기업 중 상장 이후 수익률이 높은 종목을 먼저 보여줍니다.
            </p>
          </div>

          <Link
            href="/companies"
            className="inline-flex items-center justify-center rounded-2xl border border-slate-300 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-100 hover:text-slate-900"
          >
            전체 기업 보기
          </Link>
        </div>

        <div className="mt-6 space-y-3">
          {topFive.map((company, index) => (
            <Link
              key={company.stockCode}
              href={`/companies/${company.stockCode}`}
              className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 px-4 py-4 transition hover:bg-slate-50"
            >
              <div className="flex min-w-0 items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">
                  {index + 1}
                </div>

                <div className="min-w-0">
                  <p className="truncate text-base font-semibold text-slate-900">
                    {company.companyName}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    {company.marketType} · {company.stockCode} · {company.industry}
                  </p>
                </div>
              </div>

              <div className="shrink-0 text-right">
                <p className="text-xs text-slate-500">상장 후 수익률</p>
                <p
                  className={`mt-1 text-lg font-semibold ${company.returnSinceIpo > 0
                      ? "text-emerald-600"
                      : company.returnSinceIpo < 0
                        ? "text-rose-600"
                        : "text-slate-600"
                    }`}
                >
                  {company.returnSinceIpo > 0 ? "+" : ""}
                  {company.returnSinceIpo.toFixed(1)}%
                </p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </PageContainer>
  );
}
