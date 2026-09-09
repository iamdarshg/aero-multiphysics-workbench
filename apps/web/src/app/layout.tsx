import type { Metadata } from 'next';
import './styles.css';

export const metadata: Metadata = {
  title: 'Aero Workbench',
  description: 'Coupled engineering workbench UI',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
