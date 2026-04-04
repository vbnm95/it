interface SummaryCardProps {
    label: string;
    value: string;
    subtext?: string;
}

export default function SummaryCard({
    label,
    value,
    subtext,
}: SummaryCardProps) {
    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-medium text-slate-500">{label}</p>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                {value}
            </p>
            {subtext ? (
                <p className="mt-2 text-sm text-slate-500">{subtext}</p>
            ) : null}
        </div>
    );
}