import Link from "next/link";
import PageContainer from "@/components/layout/PageContainer";
import SummaryCard from "@/components/dashboard/SummaryCard";
import { mockCompanies } from "@/data/mockCompanies";

export default function HomePage() {
  const total = mockCompanies.length;
  const kospi = mockCompanies.filter((c) => c.marketType === "KOSPI").length;
  const kosdaq = mockCompanies.filter((c) => c.marketType === "KOSDAQ").length;

  const topPerformer = [...mockCompanies].sort(
    (a, b) => b.returnSinceIpo - a.returnSinceIpo
  )[0];

  return (
    <PageContainer>
      <section className="rounded-[28px] border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium text-slate-500">IT · IPO Trace</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
          최근 1년 신규상장 기업의
          <br />
          주가 흐름과 지분율 변화를 추적합니다.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
          코스피·코스닥 신규상장 기업을 대상으로 상장 이후 가격 흐름,
          최근 공시, 최대주주 및 특수관계인 지분율 변화를 한 화면에서
          확인하는 웹앱 MVP입니다.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/companies"
            className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
          >
            기업 목록 보기
          </Link>
        </div>
      </section>

      <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="최근 1년 신규상장 기업" value={`${total}개`} />
        <SummaryCard label="코스피" value={`${kospi}개`} />
        <SummaryCard label="코스닥" value={`${kosdaq}개`} />
        <SummaryCard
          label="상장 후 수익률 상위"
          value={topPerformer.companyName}
          subtext={`${topPerformer.returnSinceIpo.toFixed(1)}%`}
        />
      </section>

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-900">현재 MVP 범위</h2>
        <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          <div className="rounded-2xl bg-slate-50 p-4">최근 1년 신규상장 기업 리스트</div>
          <div className="rounded-2xl bg-slate-50 p-4">상장 후 주가 흐름 차트</div>
          <div className="rounded-2xl bg-slate-50 p-4">최근 공시 이벤트 목록</div>
          <div className="rounded-2xl bg-slate-50 p-4">
            지분율 시작값 vs 최신값 비교
          </div>
        </div>
      </section>
    </PageContainer>
  );
}