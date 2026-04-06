import PageContainer from "@/components/layout/PageContainer";

export default function AboutPage() {
    return (
        <PageContainer>
            <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                <p className="text-sm font-medium text-slate-500">About IT · IPO Trace</p>

                <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-5xl">
                    신규 상장 기업의
                    <br />
                    IPO 정보와 상장 후 흐름을
                    <br />
                    구조화해서 보여주는 프로젝트
                </h1>

                <p className="mt-6 max-w-4xl text-base leading-7 text-slate-600">
                    IPO Trace는 공모를 통해 신규상장한 기업을 대상으로, IPO 당시 공모가와
                    주요 주주 정보를 저장하고 상장 후 주가 흐름을 함께 추적하기 위해 만든
                    데이터 기반 웹앱 및 수집 프로젝트입니다.
                </p>
            </section>

            <section className="mt-8 grid gap-4 lg:grid-cols-3">
                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
                    <p className="text-sm font-semibold text-slate-400">PROJECT GOAL</p>
                    <h2 className="mt-3 text-2xl font-semibold text-slate-900">
                        왜 IPO Trace를 만들었는가
                    </h2>
                    <p className="mt-4 text-base leading-7 text-slate-600">
                        일반적인 주가 서비스는 모든 종목을 넓게 다루지만, 신규 상장 기업만
                        따로 모아서 IPO 당시 구조와 상장 후 흐름을 함께 보기는 불편한 경우가
                        많습니다. IPO Trace는 이 지점을 해결하기 위해 시작되었고, 신규 상장
                        기업의 초기 정보를 구조화해서 장기적으로 추적할 수 있도록 설계된
                        프로젝트입니다.
                    </p>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-slate-900 p-6 shadow-sm">
                    <p className="text-sm font-semibold text-slate-400">CORE SUMMARY</p>
                    <p className="mt-4 text-xl font-semibold leading-8 text-white">
                        IPO 당시 정보는 정리하고,
                        <br />
                        상장 후 가격 흐름은
                        <br />
                        꾸준히 추적합니다.
                    </p>
                </div>
            </section>

            <section className="mt-8 grid gap-4 lg:grid-cols-2">
                <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                    <p className="text-sm font-semibold text-slate-400">INCLUDED</p>
                    <h2 className="mt-3 text-2xl font-semibold text-slate-900">
                        현재 포함하는 범위
                    </h2>

                    <div className="mt-6 space-y-4">
                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                신규 상장 기업 seed 적재
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                KOSPI, KOSDAQ 신규 상장 기업을 선별해서 추적 대상에 포함합니다.
                            </p>
                        </div>

                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                IPO 당시 공모 정보 저장
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                공모가, 상장일, 종목 기본정보 등 IPO 시점 핵심 정보를 저장합니다.
                            </p>
                        </div>

                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                IPO 당시 주요 주주 명단 및 지분율 파싱
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                증권발행실적보고서를 기준으로 주요 주주 명단, 주식의 종류,
                                지분율을 정리합니다.
                            </p>
                        </div>

                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                상장 후 일별 주가 이력 추적
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                상장 후 가격 흐름과 현재가, 수익률을 계속 갱신합니다.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                    <p className="text-sm font-semibold text-slate-400">NOT INCLUDED</p>
                    <h2 className="mt-3 text-2xl font-semibold text-slate-900">
                        현재 제외하는 범위
                    </h2>

                    <div className="mt-6 space-y-4">
                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                최신 주요 주주 지분변화 자동 추적
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                현재 버전은 IPO 당시 기준선에 집중하고 있으며, 최신 변동 자동
                                비교는 범위에서 제외합니다.
                            </p>
                        </div>

                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                최근 공시 목록 자동 노출
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                현재는 가격 흐름과 IPO 당시 정보에 집중하고 있어 공시 목록은
                                화면 범위에서 제외합니다.
                            </p>
                        </div>

                        <div className="rounded-2xl bg-slate-50 px-5 py-4">
                            <p className="text-base font-semibold text-slate-900">
                                IPO 이후 주요 주주 변동 비교 리포트
                            </p>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                                비교 리포트 자동 생성 기능은 이후 확장 가능성으로 남겨둔 상태입니다.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

        </PageContainer>
    );
}