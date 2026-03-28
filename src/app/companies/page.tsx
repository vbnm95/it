import PageContainer from "@/components/layout/PageContainer";
import CompanyCard from "@/components/companies/CompanyCard";
import { mockCompanies } from "@/data/mockCompanies";

export default function CompaniesPage() {
    return (
        <PageContainer>
            <section>
                <p className="text-sm font-medium text-slate-500">Companies</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
                    최근 1년 신규상장 기업
                </h1>
                <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base">
                    현재는 더미 데이터 기반 목록 화면입니다. 이후 KIND, OpenDART,
                    가격 데이터 소스를 연결할 예정입니다.
                </p>
            </section>

            <section className="mt-8 grid gap-4">
                {mockCompanies.map((company) => (
                    <CompanyCard key={company.id} company={company} />
                ))}
            </section>
        </PageContainer>
    );
}