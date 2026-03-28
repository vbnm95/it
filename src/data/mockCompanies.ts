import type { Company, CompanyDetail } from "@/types/company";

export const mockCompanies: Company[] = [
    {
        id: "1",
        companyName: "에이원바이오",
        stockCode: "123450",
        marketType: "KOSDAQ",
        listingDate: "2025-06-17",
        offeringPrice: 18000,
        currentPrice: 22450,
        returnSinceIpo: 24.7,
        ownershipChangePct: -1.3,
        latestDisclosureDate: "2026-03-21",
        industry: "바이오"
    },
    {
        id: "2",
        companyName: "넥스트로보틱스",
        stockCode: "234560",
        marketType: "KOSPI",
        listingDate: "2025-09-02",
        offeringPrice: 26000,
        currentPrice: 24800,
        returnSinceIpo: -4.6,
        ownershipChangePct: 0.0,
        latestDisclosureDate: "2026-03-18",
        industry: "로봇"
    },
    {
        id: "3",
        companyName: "하이브릿지AI",
        stockCode: "345670",
        marketType: "KOSDAQ",
        listingDate: "2025-11-28",
        offeringPrice: 14500,
        currentPrice: 19800,
        returnSinceIpo: 36.6,
        ownershipChangePct: -0.8,
        latestDisclosureDate: "2026-03-25",
        industry: "AI 소프트웨어"
    }
];

export const mockCompanyDetails: Record<string, CompanyDetail> = {
    "123450": {
        ...mockCompanies[0],
        priceHistory: [
            { date: "2025-06-17", close: 18100 },
            { date: "2025-07-17", close: 19200 },
            { date: "2025-08-17", close: 20500 },
            { date: "2025-09-17", close: 19850 },
            { date: "2025-10-17", close: 21000 },
            { date: "2025-11-17", close: 21800 },
            { date: "2025-12-17", close: 23000 },
            { date: "2026-01-17", close: 22150 },
            { date: "2026-02-17", close: 21900 },
            { date: "2026-03-17", close: 22450 }
        ],
        disclosures: [
            {
                id: "d1",
                reportDate: "2026-03-21",
                reportName: "사업보고서",
                filerName: "에이원바이오"
            },
            {
                id: "d2",
                reportDate: "2026-02-12",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "최대주주 외 2인"
            }
        ],
        ownership: {
            ipoBasePct: 42.1,
            latestPct: 40.8,
            changePct: -1.3
        }
    },
    "234560": {
        ...mockCompanies[1],
        priceHistory: [
            { date: "2025-09-02", close: 25800 },
            { date: "2025-10-02", close: 24500 },
            { date: "2025-11-02", close: 23900 },
            { date: "2025-12-02", close: 25000 },
            { date: "2026-01-02", close: 26100 },
            { date: "2026-02-02", close: 25200 },
            { date: "2026-03-02", close: 24800 }
        ],
        disclosures: [
            {
                id: "d3",
                reportDate: "2026-03-18",
                reportName: "정기주주총회소집공고",
                filerName: "넥스트로보틱스"
            }
        ],
        ownership: {
            ipoBasePct: 51.4,
            latestPct: 51.4,
            changePct: 0.0
        }
    },
    "345670": {
        ...mockCompanies[2],
        priceHistory: [
            { date: "2025-11-28", close: 14900 },
            { date: "2025-12-28", close: 15800 },
            { date: "2026-01-28", close: 17100 },
            { date: "2026-02-28", close: 19150 },
            { date: "2026-03-28", close: 19800 }
        ],
        disclosures: [
            {
                id: "d4",
                reportDate: "2026-03-25",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "특수관계인"
            },
            {
                id: "d5",
                reportDate: "2026-03-10",
                reportName: "사업보고서",
                filerName: "하이브릿지AI"
            }
        ],
        ownership: {
            ipoBasePct: 37.5,
            latestPct: 36.7,
            changePct: -0.8
        }
    }
};