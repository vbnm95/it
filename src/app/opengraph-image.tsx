import { ImageResponse } from "next/og";

export const alt = "IPO Trace Open Graph Image";
export const size = {
    width: 1200,
    height: 630,
};
export const contentType = "image/png";

export default function Image() {
    return new ImageResponse(
        (
            <div
                style={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    background:
                        "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%)",
                    color: "white",
                    padding: "64px",
                    fontFamily: "sans-serif",
                }}
            >
                <div
                    style={{
                        display: "flex",
                        fontSize: 28,
                        fontWeight: 700,
                        letterSpacing: "-0.02em",
                        opacity: 0.92,
                    }}
                >
                    IT · IPO Trace
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div
                        style={{
                            display: "flex",
                            fontSize: 72,
                            lineHeight: 1.1,
                            fontWeight: 800,
                            letterSpacing: "-0.04em",
                            maxWidth: "920px",
                        }}
                    >
                        IPO 당시 주요 주주 구조와
                        <br />
                        상장 후 주가 흐름 추적
                    </div>

                    <div
                        style={{
                            display: "flex",
                            fontSize: 30,
                            lineHeight: 1.5,
                            color: "#cbd5e1",
                            maxWidth: "980px",
                        }}
                    >
                        공모가 · 상장일 · IPO 기준 주요 주주 지분율 · 현재가 · 상장 후
                        수익률 · 일별 가격 흐름
                    </div>
                </div>

                <div
                    style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: 24,
                        color: "#94a3b8",
                    }}
                >
                    <div>Data-driven IPO tracking</div>
                    <div>ipotrace</div>
                </div>
            </div>
        ),
        {
            ...size,
        },
    );
}