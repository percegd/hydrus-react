import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Simulação de Água e Nutrientes no Solo",
  description:
    "Plataforma que modela, com rigor físico, a dinâmica da água e o transporte de nutrientes no perfil do solo.",
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/favicon_sprout_lucide.svg", type: "image/svg+xml" },
    ],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
