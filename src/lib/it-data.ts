import "server-only";

import type {
    Company,
    CompanyDetail,
    CompanyRow,
    DisclosureRow,
    KeyShareholderLatestRow,
    PriceDailyRow,
} from "@/types/company";
import { normalizeStockCode } from "@/lib/utils";
import { supabaseSelectMany, supabaseSelectSingle } from "@/lib/supabase";

const COMPANY_COLUMNS = [
    "id",
    "stock_code",
    "dart_corp_code",
    "company_name",
    "company_name_eng",
    "market_type",
    "security_group",
    "sector_name",
    "industry",
    "listing_date",
    "offering_price",
    "homepage_url",
    "ir_url",
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

function coerceText(value: string | null | undefined): string {
    if (!value) return "-";
    const trimmed = value.trim();
    return trimmed || "-";
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
        industry:
            coerceText(row.industry) !== "-"
                ? coerceText(row.industry)
                : coerceText(row.sector_name),
        companyNameEng: row.company_name_eng,
        sectorName: row.sector_name,
        securityGroup: row.security_group,
        homepageUrl: row.homepage_url,
        irUrl: row.ir_url,
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
        select: "id,company_id,trade_date,close_price",
        company_id: `eq.${company.id}`,
        order: "trade_date.asc",
    });

    const shareholderParams = new URLSearchParams({
        select:
            "company_id,holder_key,holder_name,holder_role,ipo_base_pct,latest_pct,change_pct",
        company_id: `eq.${company.id}`,
        order: "change_pct.desc",
    });

    const disclosureByCompanyParams = new URLSearchParams({
        select: "id,rcept_no,company_id,dart_corp_code,stock_code,rcept_dt,report_nm",
        company_id: `eq.${company.id}`,
        order: "rcept_dt.desc",
        limit: "20",
    });

    const [priceRows, shareholderRows, disclosureRowsByCompany] =
        await Promise.all([
            safeSelectMany<PriceDailyRow>("price_daily", priceParams),
            safeSelectMany<KeyShareholderLatestRow>(
                "key_shareholder_latest",
                shareholderParams,
            ),
            safeSelectMany<DisclosureRow>("disclosures", disclosureByCompanyParams),
        ]);

    const disclosureRows =
        disclosureRowsByCompany.length > 0
            ? disclosureRowsByCompany
            : await safeSelectMany<DisclosureRow>(
                "disclosures",
                new URLSearchParams({
                    select:
                        "id,rcept_no,company_id,dart_corp_code,stock_code,rcept_dt,report_nm",
                    stock_code: `eq.${company.stockCode}`,
                    order: "rcept_dt.desc",
                    limit: "20",
                }),
            );

    const priceHistory = priceRows
        .map((row) => ({
            date: row.trade_date,
            close: coerceNumber(row.close_price),
        }))
        .filter(
            (row): row is { date: string; close: number } =>
                typeof row.close === "number" && Number.isFinite(row.close),
        );

    const disclosures = disclosureRows.map((row) => ({
        id: String(row.id ?? row.rcept_no),
        reportDate: row.rcept_dt,
        reportName: row.report_nm,
        filerName: "-",
        disclosureUrl: null,
    }));

    const keyShareholders = shareholderRows.map((row) => ({
        id: row.holder_key,
        holderName: row.holder_name,
        holderRole: row.holder_role,
        ipoBasePct: coerceNumber(row.ipo_base_pct),
        latestPct: coerceNumber(row.latest_pct),
        changePct: coerceNumber(row.change_pct),
    }));

    return {
        ...company,
        priceHistory,
        disclosures,
        keyShareholders,
    };
}