export type MarketType = "KOSPI" | "KOSDAQ";

export interface Company {
    id: string;
    companyName: string;
    stockCode: string;
    marketType: MarketType;
    listingDate: string;
    offeringPrice: number | null;
    currentPrice: number | null;
    returnSinceIpo: number | null;
    keyShareholdersChangePct: number | null;
    latestDisclosureDate: string | null;
    industry: string;
    companyNameEng?: string | null;
    sectorName?: string | null;
    securityGroup?: string | null;
    homepageUrl?: string | null;
    irUrl?: string | null;
    currentPriceDate?: string | null;
    isActive?: boolean;
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
    disclosureUrl?: string | null;
}

export interface KeyShareholder {
    id: string;
    holderName: string;
    ipoBasePct: number | null;
    latestPct: number | null;
    changePct: number | null;
    holderRole?: string | null;
}

export interface CompanyDetail extends Company {
    priceHistory: PricePoint[];
    disclosures: DisclosureEvent[];
    keyShareholders: KeyShareholder[];
}

export interface CompanyRow {
    id: string;
    stock_code: string;
    dart_corp_code: string | null;
    company_name: string;
    company_name_eng: string | null;
    market_type: MarketType;
    security_group: string | null;
    sector_name: string | null;
    industry: string | null;
    listing_date: string;
    offering_price: number | string | null;
    homepage_url: string | null;
    ir_url: string | null;
    current_price: number | string | null;
    current_price_date: string | null;
    return_since_ipo: number | string | null;
    latest_disclosure_date: string | null;
    key_shareholders_change_pct: number | string | null;
    is_active: boolean;
}

export interface PriceDailyRow {
    id: number;
    company_id: string;
    trade_date: string;
    close_price: number | string | null;
}

export interface DisclosureRow {
    id: number;
    rcept_no: string;
    company_id: string | null;
    dart_corp_code: string | null;
    stock_code: string | null;
    rcept_dt: string;
    report_nm: string;
}

export interface KeyShareholderLatestRow {
    company_id: string;
    holder_key: string;
    holder_name: string;
    holder_role: string | null;
    ipo_base_pct: number | string | null;
    latest_pct: number | string | null;
    change_pct: number | string | null;
}