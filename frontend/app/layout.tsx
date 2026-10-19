import type { Metadata } from "next";

export const metadata: Metadata = { title: "Hydrus 1D" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#f6f7f4" }}>{children}</body>
    </html>
  );
}
