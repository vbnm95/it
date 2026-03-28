export type MarketType = "KOSPI" | "KOSDAQ";

export interface Company {
    id: string;
    companyName: string;
    stockCode: string;
    marketType: MarketType;
    listingDate: string;
    offeringPrice: number;
    currentPrice: number;
    returnSinceIpo: number;
    keyShareholdersChangePct: number;
    latestDisclosureDate: string;
    industry: string;
}

export interface PricePoint {
    date: string;
    close: number;
}

export interface DisclosureEvent {
    id: string;
    reportDate: string;
    reportName: string;
    filerName: string;
}

export interface KeyShareholder {
    id: string;
    holderName: string;
    ipoBasePct: number;
    latestPct: number;
    changePct: number;
}

export interface CompanyDetail extends Company {
    priceHistory: PricePoint[];
    disclosures: DisclosureEvent[];
    keyShareholders: KeyShareholder[];
}
