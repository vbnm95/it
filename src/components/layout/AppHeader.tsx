import Image from "next/image";
import Link from "next/link";

const navItems = [
    { href: "/", label: "Home" },
    { href: "/about", label: "About" },
    { href: "/companies", label: "Companies" },
];

export default function AppHeader() {
    return (
        <header className="border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
                <Link href="/" className="flex items-center gap-3">
                    <Image
                        src="/logo-mark.png"
                        alt="IPO Trace logo"
                        width={44}
                        height={44}
                        className="h-11 w-11 rounded-2xl shadow-sm"
                        priority
                    />

                    <div>
                        <p className="text-base font-semibold tracking-tight text-slate-900">
                            IT
                        </p>
                        <p className="text-sm text-slate-500">IPO Trace</p>
                    </div>
                </Link>

                <nav className="flex items-center gap-2 text-sm font-medium text-slate-600">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className="rounded-xl px-3 py-2 transition hover:bg-slate-100 hover:text-slate-900"
                        >
                            {item.label}
                        </Link>
                    ))}
                </nav>
            </div>
        </header>
    );
}