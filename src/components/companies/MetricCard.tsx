interface MetricCardProps {
    label: string;
    value: string;
    subtext?: string;
}

export default function MetricCard({
    label,
    value,
    subtext
}: MetricCardProps) {
    return (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-2 text-xl font-semibold text-slate-900">{value}</p>
            {subtext ? <p className="mt-2 text-sm text-slate-500">{subtext}</p> : null}
        </div>
    );
}