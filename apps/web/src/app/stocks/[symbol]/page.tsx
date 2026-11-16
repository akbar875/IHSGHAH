import { notFound } from 'next/navigation';
import StockDetail from './stock-detail';
import DailyStockDetail from './daily-stock-detail';

export default async function Page({ params, searchParams }: { params: Promise<{ symbol: string }>; searchParams: Promise<{ source?: string }> }) {
  const { symbol } = await params;
  if (!/^[A-Z][A-Z0-9.]{0,11}$/.test(symbol)) notFound();
  if ((await searchParams).source === 'daily') {
    if (!/^[A-Z][A-Z0-9]{1,7}$/.test(symbol)) notFound();
    return <DailyStockDetail symbol={symbol} />;
  }
  return <StockDetail symbol={symbol} />;
}
