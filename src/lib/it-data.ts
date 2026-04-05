import "server-only";

import type {
    Company,
    CompanyDetail,
    CompanyRow,
    PriceDailyRow,
    ShareholderIpoBaseRow,
} from "@/types/company";
import { normalizeStockCode } from "@/lib/utils";
import { supabaseSelectMany, supabaseSelectSingle } from "@/lib/supabase";

const COMPANY_COLUMNS = [
    "id",
    "stock_code",
    "company_name",
    "market_type",
    "listing_date",
    "offering_price",
    "current_price",
    "current_price_date",
    "return_since_ipo",
    "latest_disclosure_date",
    "key_shareholders_change_pct",
    "is_active",
].join(",");

function coerceNumber(
    value: number | string | null | undefined,
): number | null {
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }

    if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    return null;
}

function computeReturnSinceIpo(
    offeringPrice: number | null,
    currentPrice: number | null,
): number | null {
    if (
        offeringPrice === null ||
        currentPrice === null ||
        offeringPrice <= 0
    ) {
        return null;
    }

    return ((currentPrice - offeringPrice) / offeringPrice) * 100;
}

function mapRowToCompany(row: CompanyRow): Company {
    const offeringPrice = coerceNumber(row.offering_price);
    const currentPrice = coerceNumber(row.current_price);
    const returnSinceIpo =
        coerceNumber(row.return_since_ipo) ??
        computeReturnSinceIpo(offeringPrice, currentPrice);

    return {
        id: row.id,
        companyName: row.company_name,
        stockCode: normalizeStockCode(row.stock_code),
        marketType: row.market_type,
        listingDate: row.listing_date,
        offeringPrice,
        currentPrice,
        returnSinceIpo,
        keyShareholdersChangePct: coerceNumber(row.key_shareholders_change_pct),
        latestDisclosureDate: row.latest_disclosure_date,
        industry: row.market_type,
        currentPriceDate: row.current_price_date,
        isActive: row.is_active,
    };
}

async function safeSelectMany<T>(
    table: string,
    params: URLSearchParams,
): Promise<T[]> {
    try {
        return await supabaseSelectMany<T>(table, params.toString());
    } catch (error) {
        console.error(`[${table}] 조회 실패`, error);
        return [];
    }
}

export async function getCompanies(): Promise<Company[]> {
    const params = new URLSearchParams({
        select: COMPANY_COLUMNS,
        is_active: "eq.true",
        order: "listing_date.desc,stock_code.asc",
    });

    const rows = await supabaseSelectMany<CompanyRow>(
        "companies",
        params.toString(),
    );

    return rows.map(mapRowToCompany);
}

export async function getCompanyDetailByStockCode(
    stockCode: string,
): Promise<CompanyDetail | null> {
    const normalizedStockCode = normalizeStockCode(stockCode);

    const companyParams = new URLSearchParams({
        select: COMPANY_COLUMNS,
        stock_code: `eq.${normalizedStockCode}`,
        is_active: "eq.true",
    });

    const companyRow = await supabaseSelectSingle<CompanyRow>(
        "companies",
        companyParams.toString(),
    );

    if (!companyRow) {
        return null;
    }

    const company = mapRowToCompany(companyRow);

    const priceParams = new URLSearchParams({
        select: "id,company_id,date,close",
        company_id: `eq.${company.id}`,
        order: "date.asc",
    });

    const shareholderParams = new URLSearchParams({
        select: "id,company_id,holder_key,holder_name,holder_role,base_pct",
        company_id: `eq.${company.id}`,
        order: "base_pct.desc,holder_name.asc",
    });

    const [priceRows, shareholderRows] = await Promise.all([
        safeSelectMany<PriceDailyRow>("price_daily", priceParams),
        safeSelectMany<ShareholderIpoBaseRow>(
            "shareholder_ipo_base",
            shareholderParams,
        ),
    ]);

    const priceHistory = priceRows
        .map((row) => ({
            date: row.date,
            close: coerceNumber(row.close),
        }))
        .filter(
            (row): row is { date: string; close: number } =>
                typeof row.close === "number" && Number.isFinite(row.close),
        );

    const keyShareholders = shareholderRows.map((row) => ({
        id: row.holder_key,
        holderName: row.holder_name,
        holderRole: row.holder_role,
        ipoBasePct: coerceNumber(row.base_pct),
        latestPct: null,
        changePct: null,
    }));

    return {
        ...company,
        priceHistory,
        disclosures: [],
        keyShareholders,
    };
}