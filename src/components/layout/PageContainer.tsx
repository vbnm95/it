import { ReactNode } from "react";

interface PageContainerProps {
    children: ReactNode;
}

export default function PageContainer({ children }: PageContainerProps) {
    return (
        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
            {children}
        </main>
    );
}