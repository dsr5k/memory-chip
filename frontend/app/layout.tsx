import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Memory Chip Web MVP',
  description: 'Web-first automatic microphone capture and learning memory pipeline',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
