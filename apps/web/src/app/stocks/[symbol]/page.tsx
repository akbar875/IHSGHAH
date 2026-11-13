import { notFound } from 'next/navigation';
import StockDetail from './stock-detail';

export default async function Page({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  if (!/^[A-Z][A-Z0-9.]{0,11}$/.test(symbol)) notFound();
  return <StockDetail symbol={symbol} />;
}
