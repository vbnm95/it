export const dynamic = "force-dynamic";

import PageContainer from "@/components/layout/PageContainer";
import CompaniesExplorer from "@/components/companies/CompaniesExplorer";
import { getCompanies } from "@/lib/it-data";

export default async function CompaniesPage() {
    const companies = await getCompanies();

    return (
        <PageContainer>
            <CompaniesExplorer companies={companies} />
        </PageContainer>
    );
}