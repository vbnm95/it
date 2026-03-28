import Link from "next/link";
import { LineChart } from "lucide-react";

export default function AppHeader() {
    return (
        <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
                <Link href="/" className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-900 text-white">
                        <LineChart size={18} />
                    </div>
                    <div>
                        <div className="text-sm font-semibold tracking-tight text-slate-900">
                            IT
                        </div>
                        <div className="text-xs text-slate-500">IPO Trace</div>
                    </div>
                </Link>

                <nav className="flex items-center gap-5 text-sm text-slate-600">
                    <Link href="/" className="hover:text-slate-900">
                        Home
                    </Link>
                    <Link href="/companies" className="hover:text-slate-900">
                        Companies
                    </Link>
                </nav>
            </div>
        </header>
    );
}