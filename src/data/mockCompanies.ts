import type { Company, CompanyDetail, KeyShareholder } from "@/types/company";

function sumKeyShareholderChangePct(items: KeyShareholder[]): number {
    const total = items.reduce((sum, item) => sum + item.changePct, 0);
    return Number(total.toFixed(1));
}

const detail123450Shareholders: KeyShareholder[] = [
    { id: "k1", holderName: "금창원", ipoBasePct: 18.3, latestPct: 17.0, changePct: -1.3 },
    { id: "k2", holderName: "김세환", ipoBasePct: 6.1, latestPct: 5.7, changePct: -0.4 },
    { id: "k3", holderName: "스타인베스트먼트", ipoBasePct: 5.4, latestPct: 5.1, changePct: -0.3 },
    { id: "k4", holderName: "IBK투자증권", ipoBasePct: 4.9, latestPct: 4.7, changePct: -0.2 },
    { id: "k5", holderName: "초기엔젤1호조합", ipoBasePct: 2.0, latestPct: 0.0, changePct: -2.0 },
    { id: "k6", holderName: "신규전략투자조합", ipoBasePct: 0.0, latestPct: 1.6, changePct: 1.6 },
];

const detail234560Shareholders: KeyShareholder[] = [
    { id: "k7", holderName: "박정훈", ipoBasePct: 51.4, latestPct: 51.4, changePct: 0.0 },
    { id: "k8", holderName: "넥스트인베스트먼트", ipoBasePct: 8.2, latestPct: 7.7, changePct: -0.5 },
    { id: "k9", holderName: "이선영", ipoBasePct: 6.4, latestPct: 6.1, changePct: -0.3 },
    { id: "k10", holderName: "우리사주조합", ipoBasePct: 1.0, latestPct: 0.8, changePct: -0.2 },
    { id: "k11", holderName: "신규파트너스", ipoBasePct: 0.0, latestPct: 0.4, changePct: 0.4 },
];

const detail345670Shareholders: KeyShareholder[] = [
    { id: "k12", holderName: "정민수", ipoBasePct: 37.5, latestPct: 36.7, changePct: -0.8 },
    { id: "k13", holderName: "브릿지AI 벤처펀드", ipoBasePct: 7.3, latestPct: 6.4, changePct: -0.9 },
    { id: "k14", holderName: "김하늘", ipoBasePct: 5.6, latestPct: 5.0, changePct: -0.6 },
    { id: "k15", holderName: "우리사주조합", ipoBasePct: 1.1, latestPct: 0.8, changePct: -0.3 },
    { id: "k16", holderName: "초기재무적투자자", ipoBasePct: 3.0, latestPct: 0.0, changePct: -3.0 },
    { id: "k17", holderName: "신규기관A", ipoBasePct: 0.0, latestPct: 2.5, changePct: 2.5 },
];

const detail456780Shareholders: KeyShareholder[] = [
    { id: "k18", holderName: "오성민", ipoBasePct: 22.4, latestPct: 21.9, changePct: -0.5 },
    { id: "k19", holderName: "시그널성장펀드", ipoBasePct: 8.7, latestPct: 8.1, changePct: -0.6 },
    { id: "k20", holderName: "미래기술홀딩스", ipoBasePct: 6.0, latestPct: 5.8, changePct: -0.2 },
    { id: "k21", holderName: "우리사주조합", ipoBasePct: 1.3, latestPct: 1.1, changePct: -0.2 },
    { id: "k22", holderName: "신규반도체성장펀드", ipoBasePct: 0.0, latestPct: 0.9, changePct: 0.9 },
];

const detail567890Shareholders: KeyShareholder[] = [
    { id: "k23", holderName: "윤태호", ipoBasePct: 28.1, latestPct: 27.5, changePct: -0.6 },
    { id: "k24", holderName: "그린퓨처펀드", ipoBasePct: 7.8, latestPct: 7.2, changePct: -0.6 },
    { id: "k25", holderName: "에코파트너스", ipoBasePct: 5.3, latestPct: 5.0, changePct: -0.3 },
    { id: "k26", holderName: "우리사주조합", ipoBasePct: 0.9, latestPct: 0.7, changePct: -0.2 },
    { id: "k27", holderName: "초기벤처투자자", ipoBasePct: 2.5, latestPct: 0.0, changePct: -2.5 },
    { id: "k28", holderName: "신재생성장PE", ipoBasePct: 0.0, latestPct: 1.8, changePct: 1.8 },
];

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
        keyShareholdersChangePct: sumKeyShareholderChangePct(detail123450Shareholders),
        latestDisclosureDate: "2026-03-21",
        industry: "바이오",
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
        keyShareholdersChangePct: sumKeyShareholderChangePct(detail234560Shareholders),
        latestDisclosureDate: "2026-03-18",
        industry: "로봇",
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
        keyShareholdersChangePct: sumKeyShareholderChangePct(detail345670Shareholders),
        latestDisclosureDate: "2026-03-25",
        industry: "AI 소프트웨어",
    },
    {
        id: "4",
        companyName: "씨그널반도체",
        stockCode: "456780",
        marketType: "KOSPI",
        listingDate: "2025-05-12",
        offeringPrice: 32000,
        currentPrice: 41800,
        returnSinceIpo: 30.6,
        keyShareholdersChangePct: sumKeyShareholderChangePct(detail456780Shareholders),
        latestDisclosureDate: "2026-03-19",
        industry: "반도체 장비",
    },
    {
        id: "5",
        companyName: "그린에너지솔루션",
        stockCode: "567890",
        marketType: "KOSDAQ",
        listingDate: "2025-12-05",
        offeringPrice: 12000,
        currentPrice: 15150,
        returnSinceIpo: 26.3,
        keyShareholdersChangePct: sumKeyShareholderChangePct(detail567890Shareholders),
        latestDisclosureDate: "2026-03-27",
        industry: "친환경 에너지",
    },
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
            { date: "2026-03-17", close: 22450 },
        ],
        disclosures: [
            {
                id: "d1",
                reportDate: "2026-03-21",
                reportName: "사업보고서",
                filerName: "에이원바이오",
            },
            {
                id: "d2",
                reportDate: "2026-02-12",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "최대주주 외 2인",
            },
        ],
        keyShareholders: detail123450Shareholders,
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
            { date: "2026-03-02", close: 24800 },
        ],
        disclosures: [
            {
                id: "d3",
                reportDate: "2026-03-18",
                reportName: "정기주주총회소집공고",
                filerName: "넥스트로보틱스",
            },
            {
                id: "d4",
                reportDate: "2026-03-08",
                reportName: "사업보고서",
                filerName: "넥스트로보틱스",
            },
        ],
        keyShareholders: detail234560Shareholders,
    },

    "345670": {
        ...mockCompanies[2],
        priceHistory: [
            { date: "2025-11-28", close: 14900 },
            { date: "2025-12-28", close: 15800 },
            { date: "2026-01-28", close: 17100 },
            { date: "2026-02-28", close: 19150 },
            { date: "2026-03-28", close: 19800 },
        ],
        disclosures: [
            {
                id: "d5",
                reportDate: "2026-03-25",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "특수관계인",
            },
            {
                id: "d6",
                reportDate: "2026-03-10",
                reportName: "사업보고서",
                filerName: "하이브릿지AI",
            },
        ],
        keyShareholders: detail345670Shareholders,
    },

    "456780": {
        ...mockCompanies[3],
        priceHistory: [
            { date: "2025-05-12", close: 32400 },
            { date: "2025-06-12", close: 33900 },
            { date: "2025-07-12", close: 35100 },
            { date: "2025-08-12", close: 36700 },
            { date: "2025-09-12", close: 38100 },
            { date: "2025-10-12", close: 39400 },
            { date: "2025-11-12", close: 40200 },
            { date: "2025-12-12", close: 41000 },
            { date: "2026-01-12", close: 42500 },
            { date: "2026-03-12", close: 41800 },
        ],
        disclosures: [
            {
                id: "d7",
                reportDate: "2026-03-19",
                reportName: "사업보고서",
                filerName: "씨그널반도체",
            },
            {
                id: "d8",
                reportDate: "2026-02-27",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "최대주주",
            },
        ],
        keyShareholders: detail456780Shareholders,
    },

    "567890": {
        ...mockCompanies[4],
        priceHistory: [
            { date: "2025-12-05", close: 12100 },
            { date: "2026-01-05", close: 12600 },
            { date: "2026-02-05", close: 13800 },
            { date: "2026-03-05", close: 15150 },
        ],
        disclosures: [
            {
                id: "d9",
                reportDate: "2026-03-27",
                reportName: "주식등의 대량보유상황보고서",
                filerName: "주요주주",
            },
            {
                id: "d10",
                reportDate: "2026-03-11",
                reportName: "사업보고서",
                filerName: "그린에너지솔루션",
            },
        ],
        keyShareholders: detail567890Shareholders,
    },
};
