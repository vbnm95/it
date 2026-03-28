import PageContainer from "@/components/layout/PageContainer";

export default function AboutPage() {
    return (
        <PageContainer>
            <section>
                <p className="text-sm font-medium text-slate-500">About IT · IPO Trace</p>

                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
                    최근 1년 신규상장 기업을 좁고 깊게 추적하는 정보 분석형 웹앱
                </h1>

                <p className="mt-4 text-base leading-7 text-slate-600 sm:text-lg">
                    IPO Trace는 최근 1년 내 코스피·코스닥 신규상장 기업을 대상으로,
                    상장 이후 주가 흐름과 핵심 공시, 그리고 주요 주주의 지분율 변화를
                    한 화면에서 확인할 수 있도록 설계한 웹앱 MVP입니다.
                </p>
            </section>

            <section className="mt-10 grid gap-4 md:grid-cols-2">
                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-slate-900">왜 이 프로젝트인가</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                        일반적인 주가 서비스는 종목 범위가 넓지만, 상장 직후 기업만 따로
                        깊게 추적하기에는 불편한 경우가 많습니다. IPO Trace는 최근 상장
                        종목이라는 좁은 범위를 기준으로, 상장 후 흐름을 빠르게 비교하고
                        해석할 수 있도록 만드는 데 초점을 둡니다.
                    </p>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-slate-900">MVP 범위</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                        최근 1년 신규상장 기업 리스트, 기업 상세 화면, 상장 후 주가 흐름 차트,
                        최근 공시 목록, 주요 주주 지분율 변화 비교까지를 1차 MVP 범위로
                        설정했습니다.
                    </p>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-slate-900">데이터 방향</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                        향후에는 신규상장 목록, 공시 데이터, 주가 데이터, 주요 주주 지분율
                        스냅샷을 연결해 더미 데이터 기반 화면을 실제 데이터 기반 서비스로
                        전환하는 방향을 목표로 합니다.
                    </p>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-slate-900">포트폴리오 포인트</h2>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                        이 프로젝트는 단순 차트 앱이 아니라, 특정 비즈니스 질문에 맞춰
                        범위를 좁히고 정보를 재구성하는 UX/데이터 제품 설계 역량을 보여주는
                        포트폴리오용 웹앱으로 기획되었습니다.
                    </p>
                </div>
            </section>
        </PageContainer>
    );
}